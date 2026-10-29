"""Virtual replay invariants without requiring network access or wall-clock waits."""

import numpy as np
import pytest

from virtual_ecg.processing import StreamingBandpass
from virtual_ecg.streaming import StreamingECG, replay_chunks


def test_chunks_cover_every_sample_once_including_short_tail():
    chunks = list(replay_chunks(np.arange(1001), fs=360, speed=0))
    assert [len(chunk.raw) for chunk in chunks] == [90] * 11 + [11]
    assert [chunk.start_sample for chunk in chunks] == list(range(0, 1001, 90))
    assert np.concatenate([chunk.raw for chunk in chunks]).tolist() == list(range(1001))


def test_absolute_monotonic_deadlines_and_identical_chunk_processing(monkeypatch):
    class FakeTime:
        now = 17.0
        sleeps = []

        def clock(self):
            return self.now

        def sleep(self, seconds):
            self.sleeps.append(seconds)
            self.now += seconds

    raw = np.sin(np.arange(275) / 7)
    snapshots = []
    for speed in (0, 1):
        fake = FakeTime()
        stream = StreamingECG(fs=100)
        # Both speeds call the same stateful processing method and yield the
        # same global chunk ranges. Only the replay clock behavior differs.
        seen = []
        for chunk in replay_chunks(raw, 100, speed=speed, clock=fake.clock, sleeper=fake.sleep):
            seen.append((chunk.start_sample, len(chunk.raw)))
            stream.process_chunk(chunk)
        snapshots.append((seen, stream.snapshot(), stream.committed_peaks))
        if speed == 0:
            assert fake.now == 17.0 and fake.sleeps == []
        else:
            assert fake.now == pytest.approx(19.75)
            assert len(fake.sleeps) == 11
            assert fake.sleeps[-1] == pytest.approx(0.25)
    assert snapshots[0] == snapshots[1]


def test_stateful_filter_matches_one_pass_causal_filter():
    raw = np.random.default_rng(42).normal(size=1001)
    whole = StreamingBandpass(360).process(raw)
    segmented_filter = StreamingBandpass(360)
    chunks = [segmented_filter.process(chunk.raw) for chunk in replay_chunks(raw, 360, speed=0)]
    assert np.concatenate(chunks) == pytest.approx(whole, abs=1e-12)


def test_causal_filtered_event_is_timestamped_at_raw_r_maximum(monkeypatch):
    stream = StreamingECG(fs=100)
    raw = np.zeros(400)
    raw[[100, 200, 300]] = 1.0
    delayed_events = [112, 212, 312]

    def delayed_detector(buffer, fs):
        start = stream.processed_samples - len(buffer)
        return np.array([peak - start for peak in delayed_events
                         if start <= peak < stream.processed_samples])

    monkeypatch.setattr("virtual_ecg.streaming.detect_r_peaks", delayed_detector)
    for chunk in replay_chunks(raw, 100, speed=0):
        stream.process_chunk(chunk)

    assert stream.committed_peaks == [100, 200, 300]


def test_global_peaks_repeated_rolling_detections_and_committed_only_rr(monkeypatch):
    stream = StreamingECG(fs=100, unit="mV", source="fixture:lead")
    expected = [100, 200, 320, 420, 520, 540, 640, 740, 840, 940, 1040]

    def repeated_detector(buffer, fs):
        start = stream.processed_samples - len(buffer)
        return np.array([peak - start for peak in expected
                         if start <= peak < stream.processed_samples], dtype=np.int64)

    monkeypatch.setattr("virtual_ecg.streaming.detect_r_peaks", repeated_detector)
    snapshots = []
    for chunk in replay_chunks(np.zeros(1175), 100, speed=0):
        snapshots.append(stream.process_chunk(chunk))
    # The detector returns the same historical peaks on many successive calls.
    # The 20-sample event is within the 25-sample refractory gate.
    committed = [100, 200, 320, 420, 520, 640, 740, 840, 940, 1040]
    assert stream.committed_peaks == committed
    assert len(set(stream.committed_peaks)) == len(committed)
    assert np.all(np.diff(stream.committed_peaks) > 0)
    assert all(a["beats"] <= b["beats"] for a, b in zip(snapshots, snapshots[1:]))
    assert stream.valid_rr == pytest.approx([1.2, 1.0, 1.0, 1.0, 1.0])
    assert stream.ibi == pytest.approx(1.0)
    assert stream.bpm == pytest.approx(60 / np.mean([1.2, 1, 1, 1, 1]))
    assert snapshots[-1]["beats"] == len(committed)
    assert snapshots[-1]["elapsed"] == pytest.approx(11.75)
    assert snapshots[-1]["fs"] == snapshots[-1]["display_fs"] == 100
    assert snapshots[-1]["unit"] == "mV"
    assert snapshots[-1]["source"] == "fixture:lead"
    assert snapshots[-1]["raw"] == snapshots[-1]["latest_value"] == 0
    assert len(snapshots[-1]["wave"]) == 600


def test_invalid_rr_and_stale_bpm(monkeypatch):
    stream = StreamingECG(fs=100)
    peaks = [100, 200, 500, 600]  # 3 second RR is invalid; 600 resumes valid rate.

    def detector(buffer, fs):
        start = stream.processed_samples - len(buffer)
        return np.array([peak - start for peak in peaks if start <= peak < stream.processed_samples])

    monkeypatch.setattr("virtual_ecg.streaming.detect_r_peaks", detector)
    for chunk in replay_chunks(np.zeros(675), 100, speed=0):
        snapshot = stream.process_chunk(chunk)
    assert stream.committed_peaks == peaks
    assert list(stream.valid_rr) == [1.0, 1.0]
    assert snapshot["bpm"] == 60
    for chunk in replay_chunks(np.zeros(300), 100, speed=0):
        # The separate fixture segment still has consecutive global indices.
        snapshot = stream.process_chunk(type(chunk)(chunk.start_sample + 675, chunk.raw))
    assert snapshot["bpm"] is None and snapshot["ibi"] is None
