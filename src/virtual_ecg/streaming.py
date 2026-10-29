"""Chunk-paced MIT-BIH replay and stateful ECG acquisition/processing."""

from collections import deque
from dataclasses import dataclass
import time
from typing import Callable, Iterator

import numpy as np

from virtual_ecg.data import ECGRecord
from virtual_ecg.processing import StreamingBandpass, detect_r_peaks


@dataclass(frozen=True)
class ECGChunk:
    start_sample: int
    raw: np.ndarray


def replay_chunks(
    raw: np.ndarray,
    fs: float,
    chunk_duration_s: float = 0.25,
    speed: float = 1.0,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[ECGChunk]:
    """Pace each chunk against an absolute monotonic deadline.

    A speed of zero skips waiting without changing chunk boundaries or the
    downstream processing path. The last, short chunk has its own deadline.
    """
    if fs <= 0 or chunk_duration_s <= 0 or speed < 0:
        raise ValueError("fs/chunk duration must be positive and speed nonnegative")
    raw = np.asarray(raw, dtype=float)
    if raw.ndim != 1:
        raise ValueError("raw must be one-dimensional")
    chunk_samples = max(1, int(round(fs * chunk_duration_s)))
    started = clock()
    for start in range(0, len(raw), chunk_samples):
        end = min(start + chunk_samples, len(raw))
        if speed:
            remaining = started + end / fs / speed - clock()
            if remaining > 0:
                sleeper(remaining)
        yield ECGChunk(start, raw[start:end])


class StreamingECG:
    """One lead, one causal filter, one rolling Pan-Tompkins detector."""

    def __init__(
        self,
        fs: float,
        unit: str = "mV",
        source: str = "mitdb:100",
        detector_window_s: float = 8.0,
        display_window_s: float = 6.0,
        safe_margin_s: float = 0.5,
        refractory_s: float = 0.25,
        stale_bpm_s: float = 2.0,
    ):
        if fs <= 0 or detector_window_s <= 2 or display_window_s <= 0 or safe_margin_s <= 0:
            raise ValueError("Invalid stream configuration")
        self.fs = float(fs)
        self.unit = unit
        self.source = source
        self.filter = StreamingBandpass(fs)
        self.detector_capacity = int(round(detector_window_s * fs))
        self.display_capacity = int(round(display_window_s * fs))
        self.safe_margin_samples = int(round(safe_margin_s * fs))
        self.refractory_samples = int(round(refractory_s * fs))
        self.stale_bpm_samples = int(round(stale_bpm_s * fs))
        self.filtered_buffer = np.empty(0, dtype=float)
        self.raw_detector_buffer = np.empty(0, dtype=float)
        self.wave_buffer = np.empty(0, dtype=float)
        self.processed_samples = 0
        self.committed_peaks: list[int] = []
        self.valid_rr: deque[float] = deque(maxlen=5)
        self.ibi: float | None = None
        self.bpm: float | None = None
        self.latest_value: float | None = None

    @classmethod
    def from_record(cls, ecg: ECGRecord, **kwargs) -> "StreamingECG":
        return cls(ecg.fs, ecg.unit, f"{ecg.source}:{ecg.record}/{ecg.channel}", **kwargs)

    def process_chunk(self, chunk: ECGChunk) -> dict:
        if chunk.start_sample != self.processed_samples:
            raise ValueError("Chunks must be consecutive global sample ranges")
        raw = np.asarray(chunk.raw, dtype=float)
        filtered = self.filter.process(raw)
        self.processed_samples += len(raw)
        self.latest_value = float(raw[-1])
        self.filtered_buffer = np.concatenate((self.filtered_buffer, filtered))[-self.detector_capacity:]
        self.raw_detector_buffer = np.concatenate((self.raw_detector_buffer, raw))[-self.detector_capacity:]
        self.wave_buffer = np.concatenate((self.wave_buffer, raw))[-self.display_capacity:]
        buffer_start = self.processed_samples - len(self.filtered_buffer)
        # Pan-Tompkins needs more context than one 250 ms chunk. Re-running it
        # on the rolling buffer is intentional; global indices and the gate
        # below prevent its repeated historical results from becoming events.
        if len(self.filtered_buffer) >= int(round(2 * self.fs)):
            local_peaks = detect_r_peaks(self.filtered_buffer, self.fs)
            safe_end = self.processed_samples - self.safe_margin_samples
            for local_peak in local_peaks:
                global_peak = buffer_start + int(local_peak)
                if global_peak >= safe_end:
                    continue
                # The causal filter can place its positive maximum after the
                # raw R wave. Timestamp the unchanged detector's event at the
                # nearby raw positive maximum in the same global sample space.
                raw_start = self.processed_samples - len(self.raw_detector_buffer)
                radius = int(round(0.15 * self.fs))
                left = max(raw_start, global_peak - radius)
                right = min(self.processed_samples, global_peak + radius + 1)
                raw_window = self.raw_detector_buffer[left - raw_start:right - raw_start]
                if np.ptp(raw_window) > 0:
                    global_peak = left + int(np.argmax(raw_window))
                if self.committed_peaks and global_peak <= self.committed_peaks[-1] + self.refractory_samples:
                    continue
                self._commit_peak(global_peak)
        if self.committed_peaks and self.processed_samples - self.committed_peaks[-1] > self.stale_bpm_samples:
            self.bpm = None
            self.ibi = None
        return self.snapshot()

    def _commit_peak(self, peak: int) -> None:
        if self.committed_peaks:
            rr = (peak - self.committed_peaks[-1]) / self.fs
            if 0.3 <= rr <= 2.0:
                self.valid_rr.append(rr)
                self.ibi = rr
                self.bpm = 60.0 / (sum(self.valid_rr) / len(self.valid_rr))
        self.committed_peaks.append(peak)

    def snapshot(self) -> dict:
        """JSON-compatible current state; wave and latest_value retain mV."""
        return {
            "raw": self.latest_value,
            "latest_value": self.latest_value,
            "bpm": self.bpm,
            "ibi": self.ibi,
            "beats": len(self.committed_peaks),
            "wave": self.wave_buffer.tolist(),
            "fs": self.fs,
            "display_fs": self.fs,
            "unit": self.unit,
            "source": self.source,
            "elapsed": self.processed_samples / self.fs,
            "quality": 1 if self.processed_samples else 0,
        }


def replay_record(ecg: ECGRecord, duration_s: float | None = None, speed: float = 1.0,
                  chunk_duration_s: float = 0.25) -> StreamingECG:
    """Run a record through the same chunk/filter/detector path at either speed."""
    sample_count = len(ecg.raw) if duration_s is None else min(len(ecg.raw), int(round(duration_s * ecg.fs)))
    if sample_count <= 0:
        raise ValueError("Replay duration must contain samples")
    stream = StreamingECG.from_record(ecg)
    for chunk in replay_chunks(ecg.raw[:sample_count], ecg.fs, chunk_duration_s, speed):
        stream.process_chunk(chunk)
    return stream
