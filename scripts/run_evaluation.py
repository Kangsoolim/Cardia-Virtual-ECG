"""Evaluate Pan-Tompkins R peaks against MIT-BIH .atr beat annotations."""

import argparse
import csv
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from virtual_ecg.data import load_record  # noqa: E402
from virtual_ecg.processing import evaluate_peaks, process_record  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="mitdb", help="WFDB pn_dir 'mitdb' or local record directory")
    args = parser.parse_args()
    rows = []
    for record in ("100", "118"):
        processed = process_record(load_record(record, duration_s=120, source=args.source))
        ecg = processed.ecg
        metrics = evaluate_peaks(ecg.beat_samples, processed.peaks, ecg.fs, tolerance_s=0.1)
        if ecg.fs != 360 or not 100 <= len(ecg.beat_samples) <= len(ecg.annotation_samples):
            raise ValueError(f"Unexpected MIT-BIH metadata/annotation count in record {record}")
        if np.any(processed.peaks < 0) or np.any(processed.peaks >= len(ecg.raw)):
            raise ValueError(f"Out-of-range detection in record {record}")
        if not all(np.all(np.isfinite(values)) for values in
                   (processed.rates.rr_seconds, processed.rates.instantaneous_bpm, processed.rates.smoothed_bpm)):
            raise ValueError(f"Non-finite RR/BPM in record {record}")
        if len({i for i, _ in metrics.matches}) != metrics.tp or len({j for _, j in metrics.matches}) != metrics.tp:
            raise ValueError(f"Non-unique annotation matching in record {record}")
        if not np.isfinite(metrics.hr_mae):
            raise ValueError(f"HR MAE unavailable in record {record}")
        rows.append({
            "record": record,
            "duration": len(ecg.raw) / ecg.fs,
            "TP": metrics.tp,
            "FP": metrics.fp,
            "FN": metrics.fn,
            "Sensitivity": metrics.sensitivity,
            "PPV": metrics.ppv,
            "F1": metrics.f1,
            "HR_MAE": metrics.hr_mae,
        })
        print(f"{record}: TP={metrics.tp}, FP={metrics.fp}, FN={metrics.fn}, "
              f"Sensitivity={metrics.sensitivity:.4f}, PPV={metrics.ppv:.4f}, "
              f"F1={metrics.f1:.4f}, HR_MAE={metrics.hr_mae:.3f} BPM")
    output = ROOT / "results" / "metrics" / "core_evaluation.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Metrics: {output}")


if __name__ == "__main__":
    main()
