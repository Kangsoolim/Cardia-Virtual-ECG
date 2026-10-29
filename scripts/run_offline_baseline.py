"""Generate the fixed record 100 visual check for the offline baseline."""

import argparse
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from virtual_ecg.data import load_record  # noqa: E402
from virtual_ecg.processing import process_record  # noqa: E402


def save_overlay(processed, output: Path, start_s: float = 20.0, window_s: float = 10.0) -> None:
    ecg = processed.ecg
    start = int(start_s * ecg.fs)
    stop = min(int((start_s + window_s) * ecg.fs), len(ecg.raw))
    if stop <= start:
        raise ValueError("Overlay window is outside the signal")
    times = np.arange(start, stop) / ecg.fs
    reference = ecg.beat_samples[(ecg.beat_samples >= start) & (ecg.beat_samples < stop)]
    detected = processed.peaks[(processed.peaks >= start) & (processed.peaks < stop)]
    fig, (ax_raw, ax_filtered) = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)
    fig.suptitle(f"R-peak detection on MIT-BIH record {ecg.record} ({ecg.channel}, {start_s:g}–{start_s + window_s:g} s)", fontsize=15)
    fig.subplots_adjust(left=0.08, right=0.76, bottom=0.11, top=0.89, hspace=0.12)
    ax_raw.plot(times, ecg.raw[start:stop], color="#526071", linewidth=1.1)
    ax_raw.set_ylabel(f"Raw ({ecg.unit})")
    ax_filtered.plot(times, processed.filtered[start:stop], color="#11778a", linewidth=1.2, label="Filtered ECG (5–15 Hz)")
    ax_filtered.scatter(reference / ecg.fs, processed.filtered[reference], color="#188438", marker="o", s=60,
                        facecolors="none", linewidths=1.8, label="Reference R peaks", zorder=4)
    ax_filtered.scatter(detected / ecg.fs, processed.filtered[detected], color="#d52b32", marker="x", s=45,
                        linewidths=1.6, label="Detected R peaks", zorder=5)
    ax_filtered.set_ylabel(f"Filtered ({ecg.unit})")
    ax_filtered.set_xlabel("Time (seconds)")
    ax_filtered.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
    ax_filtered.grid(alpha=0.25)
    ax_raw.grid(alpha=0.25)
    ax_filtered.set_xlim(start / ecg.fs, stop / ecg.fs)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="mitdb", help="WFDB pn_dir 'mitdb' or local record directory")
    args = parser.parse_args()
    for record in ("100", "118"):
        processed = process_record(load_record(record, duration_s=120, source=args.source))
        ecg = processed.ecg
        rates = processed.rates
        print(f"{record}: fs={ecg.fs:g} Hz; lead={ecg.channel} ({ecg.unit}); "
              f"annotations={len(ecg.annotation_samples)}; beats={len(ecg.beat_samples)}; "
              f"detected={len(processed.peaks)}; valid RR={len(rates.rr_seconds)}; "
              f"last smoothed BPM={rates.smoothed_bpm[-1]:.2f}")
        if record == "100":
            output = ROOT / "results" / "figures" / "rpeak_overlay_record100.png"
            save_overlay(processed, output)
            print(f"Overlay: {output}")


if __name__ == "__main__":
    main()
