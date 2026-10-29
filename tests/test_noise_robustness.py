"""Guard the fixed NSTDB window and annotation coordinate system."""

from types import SimpleNamespace

import numpy as np

from scripts import run_noise_robustness as noise


def test_window_reader_keeps_signal_and_annotations_aligned(monkeypatch):
    start = 300 * 360
    stop = 420 * 360
    calls = []
    monkeypatch.setattr(noise.wfdb, "rdheader", lambda *args, **kwargs:
                        SimpleNamespace(fs=360, sig_len=650000, sig_name=["V1", "MLII"]))

    def fake_rdsamp(record, **kwargs):
        calls.append(("signal", record, kwargs))
        return np.zeros((stop - start, 1)), {"sig_name": ["MLII"], "units": ["mV"]}

    def fake_rdann(record, extension, **kwargs):
        calls.append(("annotation", record, kwargs))
        return SimpleNamespace(sample=[start + 155, start + 200, stop - 1],
                               symbol=["N", "+", "V"])

    monkeypatch.setattr(noise.wfdb, "rdsamp", fake_rdsamp)
    monkeypatch.setattr(noise.wfdb, "rdann", fake_rdann)
    ecg = noise.load_window("118e06", "nstdb/1.0.0")

    assert calls[0][2] == {"sampfrom": start, "sampto": stop,
                           "channels": [1], "pn_dir": "nstdb/1.0.0"}
    assert calls[1][2] == {"sampfrom": start, "sampto": stop,
                           "shift_samps": False, "pn_dir": "nstdb/1.0.0"}
    assert ecg.annotation_samples.tolist() == [155, 200, stop - start - 1]
    assert ecg.beat_samples.tolist() == [155, stop - start - 1]
