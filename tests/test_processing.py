import numpy as np
import pytest
from types import SimpleNamespace

from virtual_ecg.data import choose_channel, filter_beat_annotations, load_record
from virtual_ecg.processing import bandpass_filter, compute_rates, detect_r_peaks, evaluate_peaks, match_peaks


def test_channel_selection_and_annotation_filtering():
    assert choose_channel(["V1", "MLII"]) == 1
    assert choose_channel(["V5", "II"]) == 1
    assert filter_beat_annotations(np.array([1, 2, 3, 4, 5]), ("+", "N", "~", "/", "|")) == pytest.approx([2, 4])


def test_wfdb_reader_uses_header_lead_units_and_atr(monkeypatch):
    calls = []
    monkeypatch.setattr("virtual_ecg.data.wfdb.rdheader", lambda *args, **kwargs:
                        SimpleNamespace(fs=360, sig_name=["V1", "MLII"], sig_len=1000))

    def fake_rdsamp(name, **kwargs):
        calls.append(("signal", name, kwargs))
        return np.ones((720, 1)), {"sig_name": ["MLII"], "units": ["mV"]}

    def fake_rdann(name, extension, **kwargs):
        calls.append(("annotation", extension, kwargs))
        return SimpleNamespace(sample=[1, 100, 200, 300], symbol=["+", "N", "~", "/"])

    monkeypatch.setattr("virtual_ecg.data.wfdb.rdsamp", fake_rdsamp)
    monkeypatch.setattr("virtual_ecg.data.wfdb.rdann", fake_rdann)
    ecg = load_record("100", duration_s=2)
    assert (ecg.fs, ecg.channel, ecg.unit) == (360, "MLII", "mV")
    assert ecg.beat_samples.tolist() == [100, 300]
    assert calls[0][2]["channels"] == [1]
    assert calls[0][2]["sampto"] == 720
    assert calls[1][1] == "atr"


def test_filter_retains_qrs_band_and_suppresses_drift():
    fs = 360
    t = np.arange(3600) / fs
    signal = np.sin(2 * np.pi * 10 * t) + np.sin(2 * np.pi * 0.5 * t)
    filtered = bandpass_filter(signal, fs)
    middle = filtered[360:-360]
    assert np.std(middle - np.sin(2 * np.pi * 10 * t)[360:-360]) < 0.15


def test_rates_gate_and_recent_five_rr_mean():
    rates = compute_rates(np.array([0, 360, 720, 1080, 1440, 1800, 1980, 2340]), 360)
    assert len(rates.rr_seconds) == 7
    assert np.all(np.isfinite(rates.instantaneous_bpm))
    assert np.all(np.isfinite(rates.smoothed_bpm))
    assert rates.smoothed_bpm[-1] == pytest.approx(60 / np.mean([1, 1, 1, 0.5, 1]))
    gated = compute_rates(np.array([0, 100, 460, 1460]), 360)
    assert gated.rr_seconds == pytest.approx([1.0])


def test_pantompkins_event_is_localized_to_r_maximum(monkeypatch):
    filtered = np.zeros(200)
    filtered[50] = 2.0
    filtered[150] = 1.5
    monkeypatch.setattr("virtual_ecg.processing.nk.ecg_findpeaks", lambda *args, **kwargs: {"ECG_R_Peaks": [57, 143]})
    assert detect_r_peaks(filtered, fs=100).tolist() == [50, 150]


def test_matching_is_one_to_one_with_100_ms_tolerance():
    reference = np.array([100, 120, 500, 900])
    predicted = np.array([110, 505, 515, 1000])
    matches = match_peaks(reference, predicted, fs=360)
    assert matches == ((0, 0), (2, 1))
    assert len({i for i, _ in matches}) == len(matches)
    assert len({j for _, j in matches}) == len(matches)
    result = evaluate_peaks(reference, predicted, fs=360)
    assert (result.tp, result.fp, result.fn) == (2, 2, 2)
    assert result.f1 == pytest.approx(0.5)


def test_hr_mae_uses_only_adjacent_matched_intervals():
    result = evaluate_peaks(np.array([0, 360, 720]), np.array([0, 370, 730]), fs=360)
    assert (result.tp, result.fp, result.fn) == (3, 0, 0)
    expected = abs(60 / (370 / 360) - 60) / 2
    assert result.hr_mae == pytest.approx(expected)
