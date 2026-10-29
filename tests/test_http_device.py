"""Flask and polling contract for one continuously advancing virtual device."""

import time

import numpy as np

from virtual_ecg.data import ECGRecord
from virtual_ecg.http_device import VirtualECGDevice, create_app


def test_cardia_routes_and_repeated_api_reads_share_one_replay(monkeypatch):
    fs = 100
    duration = 12
    raw = 0.1 * np.sin(np.arange(fs * duration) / 10)
    record = ECGRecord(
        record="fixture", fs=fs, channel="MLII", unit="mV", raw=raw,
        annotation_samples=np.array([], dtype=np.int64), annotation_symbols=(),
        beat_samples=np.array([], dtype=np.int64), source="fixture",
    )
    device = VirtualECGDevice(record, speed=12)
    peaks = np.arange(100, 1200, 100)

    def detector(buffer, sample_rate):
        start = device.stream.processed_samples - len(buffer)
        return np.array([peak - start for peak in peaks
                         if start <= peak < device.stream.processed_samples])

    monkeypatch.setattr("virtual_ecg.streaming.detect_r_peaks", detector)
    client = create_app(device).test_client()
    assert client.get("/").status_code == 200
    assert b'canvas id="wave"' in client.get("/").data
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert client.get("/api/ecg").status_code == 200

    device.start()
    observations = []
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get("/api/ecg")
        assert response.status_code == 200
        data = response.get_json()
        assert {
            "raw", "bpm", "ibi", "amplitude", "quality", "active", "beats",
            "uptime", "wave", "fs", "unit", "source", "record", "elapsed",
            "completed",
        } <= data.keys()
        observations.append(data)
        if data["completed"]:
            break
        time.sleep(0.025)
    device.join(1)

    assert observations[-1]["completed"] and not observations[-1]["active"]
    assert observations[-1]["elapsed"] == duration
    assert any(item["wave"] for item in observations)
    assert any(item["bpm"] is not None and 55 <= item["bpm"] <= 65 for item in observations)
    assert [item["beats"] for item in observations] == sorted(item["beats"] for item in observations)
    assert observations[-1]["beats"] > 0
    assert observations[-1]["fs"] == 100
    assert observations[-1]["unit"] == "mV"
    assert observations[-1]["record"] == "fixture"
    assert observations[-1]["source"] == "fixture:fixture/MLII"
    assert observations[-1]["uptime"] > observations[0]["uptime"]
    assert observations[-1]["elapsed"] > observations[0]["elapsed"]
    assert client.get("/api/ecg").get_json() == observations[-1]
