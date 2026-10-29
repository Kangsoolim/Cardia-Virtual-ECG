"""Evaluate the fixed offline ECG pipeline on one NSTDB noisy interval.

PhysioNet documents noise in [300, 420) seconds for the NSTDB records:
https://physionet.org/content/nstdb/1.0.0/
"""

import csv
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import wfdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from virtual_ecg.data import ECGRecord, choose_channel, filter_beat_annotations  # noqa: E402
from virtual_ecg.processing import evaluate_peaks, process_record  # noqa: E402


WINDOW_START_S = 300
WINDOW_END_S = 420
CONDITIONS = (
    ("Clean", "118", "mitdb/1.0.0"),
    ("18 dB", "118e18", "nstdb/1.0.0"),
    ("6 dB", "118e06", "nstdb/1.0.0"),
    ("0 dB", "118e00", "nstdb/1.0.0"),
)


def load_window(record: str, database: str) -> ECGRecord:
    """Read the same absolute sample interval and its unshifted .atr labels."""
    header = wfdb.rdheader(record, pn_dir=database)
    if header.fs <= 0:
        raise ValueError(f"Invalid sampling rate for {database}/{record}")
    start = int(round(WINDOW_START_S * header.fs))
    stop = int(round(WINDOW_END_S * header.fs))
    if stop > header.sig_len or stop - start != (WINDOW_END_S - WINDOW_START_S) * header.fs:
        raise ValueError(f"Unexpected timebase or duration for {database}/{record}")
    channel = choose_channel(header.sig_name)
    samples, fields = wfdb.rdsamp(
        record, sampfrom=start, sampto=stop, channels=[channel], pn_dir=database
    )
    annotation = wfdb.rdann(
        record, "atr", sampfrom=start, sampto=stop,
        shift_samps=False, pn_dir=database
    )
    raw = np.asarray(samples[:, 0], dtype=float)
    absolute_annotations = np.asarray(annotation.sample, dtype=np.int64)
    relative_annotations = absolute_annotations - start
    if (len(raw) != stop - start or not np.all(np.isfinite(raw))
            or np.any(relative_annotations < 0)
            or np.any(relative_annotations >= len(raw))):
        raise ValueError(f"Invalid signal or annotation window for {database}/{record}")
    symbols = tuple(annotation.symbol)
    return ECGRecord(
        record=record,
        fs=float(header.fs),
        channel=fields["sig_name"][0],
        unit=fields["units"][0],
        raw=raw,
        annotation_samples=relative_annotations,
        annotation_symbols=symbols,
        beat_samples=filter_beat_annotations(relative_annotations, symbols),
        source=database,
    )


def evaluate_conditions() -> list[dict]:
    rows = []
    clean = None
    for condition, record, database in CONDITIONS:
        ecg = load_window(record, database)
        if clean is None:
            clean = ecg
        elif (ecg.fs != clean.fs or ecg.channel != clean.channel
              or ecg.unit != clean.unit
              or not np.array_equal(ecg.annotation_samples, clean.annotation_samples)
              or ecg.annotation_symbols != clean.annotation_symbols):
            raise ValueError(f"Reference annotations or lead differ for {database}/{record}")
        processed = process_record(ecg)
        metrics = evaluate_peaks(ecg.beat_samples, processed.peaks, ecg.fs)
        values = (
            np.asarray((metrics.sensitivity, metrics.ppv, metrics.f1, metrics.hr_mae)),
            processed.filtered,
            processed.rates.rr_seconds,
            processed.rates.instantaneous_bpm,
            processed.rates.smoothed_bpm,
        )
        if (not all(np.all(np.isfinite(value)) for value in values)
                or not len(ecg.beat_samples)
                or len({i for i, _ in metrics.matches}) != metrics.tp
                or len({j for _, j in metrics.matches}) != metrics.tp):
            raise ValueError(f"Invalid metrics or matches for {database}/{record}")
        rows.append({
            "Condition": condition,
            "Source": f"{database}/{record}",
            "Window_Start_s": WINDOW_START_S,
            "Window_End_s": WINDOW_END_S,
            "Reference_Beats": len(ecg.beat_samples),
            "TP": metrics.tp,
            "FP": metrics.fp,
            "FN": metrics.fn,
            "Sensitivity": metrics.sensitivity,
            "PPV": metrics.ppv,
            "F1": metrics.f1,
            "HR_MAE": metrics.hr_mae,
        })
    return rows


def main() -> None:
    rows = evaluate_conditions()
    metrics_path = ROOT / "results" / "metrics" / "noise_robustness.csv"
    figure_path = ROOT / "results" / "figures" / "f1_vs_noise.png"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(range(len(rows)), [row["F1"] for row in rows], marker="o", linewidth=1.8)
    ax.set_xticks(range(len(rows)), [row["Condition"] for row in rows])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1")
    ax.set_xlabel("Electrode motion noise (SNR)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_path, dpi=160)
    plt.close(fig)
    for row in rows:
        print(f'{row["Condition"]}: Sensitivity={row["Sensitivity"]:.4f}, '
              f'PPV={row["PPV"]:.4f}, F1={row["F1"]:.4f}, '
              f'HR MAE={row["HR_MAE"]:.3f} BPM')
    print(f"Metrics: {metrics_path}")
    print(f"Figure: {figure_path}")


if __name__ == "__main__":
    main()
