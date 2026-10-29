"""Replay a PhysioNet ECG record through the local Cardia dashboard."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from virtual_ecg.data import load_record  # noqa: E402
from virtual_ecg.http_device import VirtualECGDevice, create_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", default="100", help="MIT-BIH record number")
    parser.add_argument("--source", default="mitdb", help="WFDB pn_dir or local record directory")
    parser.add_argument("--duration", type=float, default=120.0, help="Signal seconds to replay")
    parser.add_argument("--chunk-duration", type=float, default=0.25)
    parser.add_argument("--speed", type=float, default=1.0, help="Replay rate; 0 processes without waits")
    args = parser.parse_args()

    try:
        ecg = load_record(args.record, args.duration, args.source)
    except Exception as exc:
        parser.exit(1, f"Could not load record {args.record} from {args.source}: {exc}\n"
                    "Check the network for PhysioNet, or pass --source to a local WFDB record directory.\n")

    device = VirtualECGDevice(ecg, speed=args.speed, chunk_duration_s=args.chunk_duration)
    app = create_app(device)
    device.start()
    print("Cardia: http://127.0.0.1:5000/  API: http://127.0.0.1:5000/api/ecg", flush=True)
    print(f"Replaying {ecg.source}:{ecg.record}/{ecg.channel} ({ecg.fs:g} Hz, {ecg.unit}); "
          "the display holds the final snapshot when the record completes.", flush=True)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
