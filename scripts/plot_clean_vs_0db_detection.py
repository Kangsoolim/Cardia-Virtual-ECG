"""Plot one reproducibly chosen 10 s excerpt of the existing NSTDB evaluation.

Split the fixed 300–420 s evaluation into twelve nonoverlapping 10 s bins.
Count unmatched reference and detected peaks in each bin using the full-window
matches. Choose the lower median error count, then the earliest bin with that
count. This shows a typical error burden without hand-selecting a worst case.
"""

import csv
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.run_noise_robustness import WINDOW_START_S, load_window  # noqa: E402
from virtual_ecg.processing import evaluate_peaks, process_record  # noqa: E402


CSV_PATH = ROOT / "results" / "metrics" / "noise_robustness.csv"
OUTPUT = ROOT / "results" / "figures" / "clean_vs_0db_detection.png"
SEGMENT_S = 10
SOURCES = (("Clean", "118", "mitdb/1.0.0"),
           ("0 dB", "118e00", "nstdb/1.0.0"))


def load_existing_evaluation():
    with CSV_PATH.open(newline="", encoding="utf-8") as stream:
        saved = {row["Condition"]: row for row in csv.DictReader(stream)}
    records = []
    for condition, record, database in SOURCES:
        ecg = load_window(record, database)
        processed = process_record(ecg)
        metrics = evaluate_peaks(ecg.beat_samples, processed.peaks, ecg.fs)
        row = saved[condition]
        if (row["Source"] != f"{database}/{record}"
                or (int(row["Window_Start_s"]), int(row["Window_End_s"])) != (300, 420)
                or int(row["Reference_Beats"]) != len(ecg.beat_samples)
                or (metrics.tp, metrics.fp, metrics.fn) !=
                (int(row["TP"]), int(row["FP"]), int(row["FN"]))
                or not all(np.isclose(getattr(metrics, field), float(row[column]), rtol=0, atol=1e-12)
                           for field, column in (("sensitivity", "Sensitivity"), ("ppv", "PPV"),
                                                 ("f1", "F1"), ("hr_mae", "HR_MAE")))):
            raise ValueError(f"Peak indices disagree with saved evaluation for {condition}")
        records.append((ecg, processed, metrics))
    if (records[0][0].fs != records[1][0].fs
            or records[0][0].unit != records[1][0].unit
            or records[0][0].channel != records[1][0].channel
            or not np.array_equal(records[0][0].beat_samples, records[1][0].beat_samples)):
        raise ValueError("Clean and 0 dB reference timebases or leads differ")
    return records


def choose_segment(noisy_ecg, noisy_processed, noisy_metrics) -> tuple[int, int, int]:
    matched_ref = {i for i, _ in noisy_metrics.matches}
    matched_pred = {j for _, j in noisy_metrics.matches}
    missed = np.asarray([sample for i, sample in enumerate(noisy_ecg.beat_samples)
                         if i not in matched_ref])
    false = np.asarray([sample for j, sample in enumerate(noisy_processed.peaks)
                        if j not in matched_pred])
    width = int(round(SEGMENT_S * noisy_ecg.fs))
    if len(noisy_ecg.raw) % width:
        raise ValueError("Evaluation window is not an integer number of 10 s bins")
    scores = []
    for start in range(0, len(noisy_ecg.raw), width):
        stop = start + width
        scores.append(int(np.count_nonzero((missed >= start) & (missed < stop))
                          + np.count_nonzero((false >= start) & (false < stop))))
    median_score = sorted(scores)[(len(scores) - 1) // 2]
    index = scores.index(median_score)
    return index * width, (index + 1) * width, median_score


def main() -> None:
    records = load_existing_evaluation()
    start, stop, errors = choose_segment(*records[1])
    fs = records[0][0].fs
    start_s = WINDOW_START_S + start / fs
    stop_s = WINDOW_START_S + stop / fs

    fig, axes = plt.subplots(2, 1, figsize=(10.5, 6.3), sharex=True)
    fig.suptitle("R-peak detection: clean vs 0 dB", fontsize=13, y=0.97)
    for ax, (ecg, processed, _), title in zip(
            axes, records, ("A — Clean ECG", "B — 0 dB electrode-motion noise")):
        times = WINDOW_START_S + np.arange(start, stop) / ecg.fs
        line, = ax.plot(times, ecg.raw[start:stop], color="#334155", linewidth=0.9,
                        label="ECG waveform")
        reference = ecg.beat_samples[(ecg.beat_samples >= start) & (ecg.beat_samples < stop)]
        detected = processed.peaks[(processed.peaks >= start) & (processed.peaks < stop)]
        ref_markers = ax.scatter(WINDOW_START_S + reference / ecg.fs, ecg.raw[reference],
                                 facecolors="white", edgecolors="#087e8b", marker="o",
                                 s=58, linewidths=1.8, zorder=4, label="Reference R peaks")
        det_markers = ax.scatter(WINDOW_START_S + detected / ecg.fs, ecg.raw[detected],
                                 color="#d14932", marker="x", s=50, linewidths=1.6,
                                 zorder=5, label="Detected R peaks")
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_ylabel(f"ECG ({ecg.unit})")
        ax.set_xlim(start_s, stop_s)
        ax.margins(y=0.15)
        ax.grid(alpha=0.18)
    axes[-1].set_xlabel("Time (s)")
    axes[-1].set_xticks(np.arange(start_s, stop_s + 0.1, 2))
    fig.legend((line, ref_markers, det_markers),
               ("ECG waveform", "Reference R peaks", "Detected R peaks"),
               loc="center left", bbox_to_anchor=(0.81, 0.5), frameon=False)
    fig.subplots_adjust(left=0.10, right=0.79, bottom=0.11, top=0.88, hspace=0.32)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=180)
    plt.close(fig)
    print(f"Selected {start_s:g}–{stop_s:g} s; 0 dB unmatched peaks in bin: {errors}")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
