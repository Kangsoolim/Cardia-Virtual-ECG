"""Minimal offline QRS, rate, and reference evaluation logic."""

from dataclasses import dataclass

import neurokit2 as nk
import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt, sosfilt_zi

from virtual_ecg.data import ECGRecord


@dataclass(frozen=True)
class RateSeries:
    end_samples: np.ndarray
    rr_seconds: np.ndarray
    instantaneous_bpm: np.ndarray
    smoothed_bpm: np.ndarray


@dataclass(frozen=True)
class ProcessedRecord:
    ecg: ECGRecord
    filtered: np.ndarray
    peaks: np.ndarray
    rates: RateSeries


@dataclass(frozen=True)
class Evaluation:
    matches: tuple[tuple[int, int], ...]  # (reference position, prediction position)
    tp: int
    fp: int
    fn: int
    sensitivity: float
    ppv: float
    f1: float
    hr_mae: float


def bandpass_filter(raw: np.ndarray, fs: float, low_hz: float = 5.0, high_hz: float = 15.0) -> np.ndarray:
    """Offline, zero-phase second-order Butterworth band-pass in Hz."""
    if not 0 < low_hz < high_hz < fs / 2:
        raise ValueError("Invalid band-pass frequencies")
    sos = butter(2, (low_hz, high_hz), btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, np.asarray(raw, dtype=float))


class StreamingBandpass:
    """Continuous causal counterpart of the offline zero-phase band-pass.

    The SOS coefficients match Phase 2, but causal filtering has phase delay.
    Initial state is set to the first sample's steady-state value.
    """

    def __init__(self, fs: float, low_hz: float = 5.0, high_hz: float = 15.0):
        if not 0 < low_hz < high_hz < fs / 2:
            raise ValueError("Invalid band-pass frequencies")
        self.sos = butter(2, (low_hz, high_hz), btype="bandpass", fs=fs, output="sos")
        self.state = None

    def process(self, raw: np.ndarray) -> np.ndarray:
        raw = np.asarray(raw, dtype=float)
        if raw.ndim != 1 or not len(raw) or not np.all(np.isfinite(raw)):
            raise ValueError("Filter input must be a nonempty finite one-dimensional chunk")
        if self.state is None:
            self.state = sosfilt_zi(self.sos) * raw[0]
        filtered, self.state = sosfilt(self.sos, raw, zi=self.state)
        return filtered


def detect_r_peaks(filtered: np.ndarray, fs: float) -> np.ndarray:
    """Pan-Tompkins 1985 events localized to nearby positive R maxima.

    Its moving-window integrator detects QRS energy and can mark the end of
    the complex. A fixed ±100 ms search on the filtered lead maps each event
    to the R-wave sample; this is peak localization, not a second detector.
    """
    peaks = np.asarray(
        nk.ecg_findpeaks(filtered, sampling_rate=fs, method="pantompkins1985")["ECG_R_Peaks"],
        dtype=np.int64,
    )
    if peaks.ndim != 1 or np.any(peaks < 0) or np.any(peaks >= len(filtered)):
        raise ValueError("Detector returned out-of-range peak indices")
    radius = max(1, int(round(0.1 * fs)))
    localized = [
        max(0, peak - radius) + np.argmax(filtered[max(0, peak - radius):min(len(filtered), peak + radius + 1)])
        for peak in peaks
    ]
    return np.unique(np.asarray(localized, dtype=np.int64))


def compute_rates(peaks: np.ndarray, fs: float, min_rr: float = 0.3, max_rr: float = 2.0) -> RateSeries:
    """Keep valid RR intervals and average the most recent five for BPM."""
    peaks = np.asarray(peaks, dtype=np.int64)
    if fs <= 0 or np.any(np.diff(peaks) <= 0):
        raise ValueError("fs must be positive and peaks strictly increasing")
    rr = np.diff(peaks) / fs
    valid = np.isfinite(rr) & (rr >= min_rr) & (rr <= max_rr)
    rr = rr[valid]
    ends = peaks[1:][valid]
    smoothed = np.asarray([60.0 / np.mean(rr[max(0, i - 4):i + 1]) for i in range(len(rr))])
    return RateSeries(ends, rr, 60.0 / rr, smoothed)


def process_record(ecg: ECGRecord) -> ProcessedRecord:
    filtered = bandpass_filter(ecg.raw, ecg.fs)
    peaks = detect_r_peaks(filtered, ecg.fs)
    return ProcessedRecord(ecg, filtered, peaks, compute_rates(peaks, ecg.fs))


def match_peaks(reference: np.ndarray, predicted: np.ndarray, fs: float, tolerance_s: float = 0.1) -> tuple[tuple[int, int], ...]:
    """Maximum-cardinality chronological one-to-one matches within tolerance."""
    reference = np.asarray(reference, dtype=np.int64)
    predicted = np.asarray(predicted, dtype=np.int64)
    if fs <= 0 or tolerance_s < 0 or np.any(np.diff(reference) <= 0) or np.any(np.diff(predicted) <= 0):
        raise ValueError("Peak arrays must be strictly increasing; fs/tolerance valid")
    tolerance_samples = tolerance_s * fs
    matches = []
    i = j = 0
    while i < len(reference) and j < len(predicted):
        delta = predicted[j] - reference[i]
        if delta < -tolerance_samples:
            j += 1
        elif delta > tolerance_samples:
            i += 1
        else:
            matches.append((i, j))
            i += 1
            j += 1
    return tuple(matches)


def evaluate_peaks(reference: np.ndarray, predicted: np.ndarray, fs: float, tolerance_s: float = 0.1) -> Evaluation:
    """Beat detection metrics; HR MAE uses adjacent matched intervals only."""
    reference = np.asarray(reference, dtype=np.int64)
    predicted = np.asarray(predicted, dtype=np.int64)
    matches = match_peaks(reference, predicted, fs, tolerance_s)
    tp = len(matches)
    fp = len(predicted) - tp
    fn = len(reference) - tp
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    ppv = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * sensitivity * ppv / (sensitivity + ppv) if sensitivity + ppv else 0.0
    errors = []
    for (ref_a, pred_a), (ref_b, pred_b) in zip(matches, matches[1:]):
        if ref_b == ref_a + 1 and pred_b == pred_a + 1:
            ref_rr = (reference[ref_b] - reference[ref_a]) / fs
            pred_rr = (predicted[pred_b] - predicted[pred_a]) / fs
            if 0.3 <= ref_rr <= 2.0 and 0.3 <= pred_rr <= 2.0:
                errors.append(abs(60.0 / pred_rr - 60.0 / ref_rr))
    hr_mae = float(np.mean(errors)) if errors else float("nan")
    return Evaluation(matches, tp, fp, fn, sensitivity, ppv, f1, hr_mae)
