"""Serve the current virtual ECG replay snapshot and Cardia from one Flask app."""

from pathlib import Path
from threading import Lock, Thread
import time

from flask import Flask, jsonify, send_from_directory

from virtual_ecg.data import ECGRecord
from virtual_ecg.streaming import StreamingECG, replay_chunks


WEB_DIR = Path(__file__).resolve().parents[2] / "web"


class VirtualECGDevice:
    """Process each replay chunk once; HTTP readers only copy published state."""

    def __init__(self, ecg: ECGRecord, speed: float = 1.0, chunk_duration_s: float = 0.25):
        if speed < 0 or chunk_duration_s <= 0:
            raise ValueError("speed must be nonnegative and chunk duration positive")
        self.ecg = ecg
        self.speed = speed
        self.chunk_duration_s = chunk_duration_s
        self.stream = StreamingECG.from_record(ecg)
        self._lock = Lock()
        self._snapshot = self._enrich(self.stream.snapshot(), active=False, completed=False, uptime=0)
        self._thread: Thread | None = None
        self._started_at: float | None = None

    def _enrich(self, state: dict, *, active: bool, completed: bool, uptime: int) -> dict:
        wave = state["wave"]
        return {
            **state,
            "amplitude": max(wave) - min(wave) if wave else None,
            "active": active,
            "completed": completed,
            "record": self.ecg.record,
            "uptime": uptime,  # wall-clock milliseconds since replay started
        }

    def snapshot(self) -> dict:
        with self._lock:
            # Published snapshots are immutable after assignment. Flask's JSON
            # encoder only sees this copy, never a partially processed chunk.
            return self._snapshot.copy()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Replay has already started")
        self._started_at = time.monotonic()
        with self._lock:
            self._snapshot = self._enrich(self.stream.snapshot(), active=True, completed=False, uptime=0)
        self._thread = Thread(target=self._run, name="virtual-ecg-replay", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            for chunk in replay_chunks(self.ecg.raw, self.ecg.fs, self.chunk_duration_s, self.speed):
                state = self.stream.process_chunk(chunk)
                uptime = round((time.monotonic() - self._started_at) * 1000)
                with self._lock:
                    self._snapshot = self._enrich(state, active=True, completed=False, uptime=uptime)
        finally:
            uptime = round((time.monotonic() - self._started_at) * 1000)
            with self._lock:
                self._snapshot = self._enrich(self.stream.snapshot(), active=False, completed=True, uptime=uptime)

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)


def create_app(device: VirtualECGDevice) -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/ecg")
    def ecg():
        return jsonify(device.snapshot())

    @app.get("/<path:filename>")
    def asset(filename: str):
        return send_from_directory(WEB_DIR, filename)

    return app
