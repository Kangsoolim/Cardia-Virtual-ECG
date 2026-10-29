"""Reference-backed 120 second streaming acceptance on MIT-BIH record 100."""

import numpy as np
import pytest
from requests.exceptions import ConnectionError, SSLError

from virtual_ecg.data import load_record
from virtual_ecg.processing import evaluate_peaks, process_record
from virtual_ecg.streaming import replay_record


def test_record100_streaming_matches_phase2_within_five_f1_points():
    try:
        ecg = load_record("100", duration_s=120)
    except (ConnectionError, SSLError) as exc:
        pytest.skip(f"PhysioNet unavailable: {exc}")
    stream = replay_record(ecg, speed=0)
    streaming = evaluate_peaks(ecg.beat_samples, np.asarray(stream.committed_peaks), ecg.fs)
    baseline = evaluate_peaks(ecg.beat_samples, process_record(ecg).peaks, ecg.fs)
    assert ecg.fs == 360  # Checked metadata, never a replay/filter constant.
    assert stream.processed_samples == len(ecg.raw) == 43200
    assert np.all(np.diff(stream.committed_peaks) > 0)
    assert len(stream.committed_peaks) == len(set(stream.committed_peaks))
    assert streaming.f1 >= baseline.f1 - 0.05
    assert streaming.tp > 100


def test_record118_streaming_peak_timestamps_match_annotations():
    try:
        ecg = load_record("118", duration_s=120)
    except (ConnectionError, SSLError) as exc:
        pytest.skip(f"PhysioNet unavailable: {exc}")
    stream = replay_record(ecg, speed=0)
    streaming = evaluate_peaks(ecg.beat_samples, np.asarray(stream.committed_peaks), ecg.fs)
    assert ecg.channel == "MLII" and ecg.fs == 360
    assert stream.processed_samples == len(ecg.raw) == 43200
    assert streaming.f1 >= 0.95
