# Project Status

## Core: COMPLETE

The Cardia virtual ECG course project is finalized locally. It extends the attributed Cardia dashboard with hardware-free MIT-BIH replay, real-time ECG processing, a Flask JSON device, and annotation-based validation. The course prototype is not a medical device.

## Final acceptance (2026-09-28)

| Check | Result |
|---|---|
| Full pytest | **PASS**, 18 passed |
| Phase 2 offline evaluation | **PASS**, records 100 and 118, 120 s each; overlay and core CSV regenerated |
| Phase 3 no-sleep streaming | **PASS**, records 100 and 118, 43,200 samples each |
| Phase 4 HTTP smoke | **PASS**, page and `/api/ecg` HTTP 200; record 100, MLII, 360 Hz, mV, 2,160-sample waveform, completed snapshot |
| Phase 4 browser automation | **PASS**, local Cardia page displayed waveform, BPM, RR, source, units, beat count, and Completed state |
| Manual browser acceptance | **PASS**, confirmed by project owner on 2026-09-28 |
| Optional NSTDB robustness | **PASS**, clean, 18 dB, 6 dB, and 0 dB results retained |
| `git diff --check` | **PASS** before final commit |
| GitHub push | **PENDING**: `gh` is unavailable on PATH; authentication could not be checked. No push attempted. |

## Core metrics

The release table uses the **offline** path. Full precision is in `results/metrics/core_evaluation.csv`.

| Record | Duration (s) | TP | FP | FN | Sensitivity | PPV | F1 | HR MAE (BPM) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 120 | 147 | 0 | 1 | 0.9932 | 1.0000 | 0.9966 | 0.025 |
| 118 | 120 | 147 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.103 |

The corrected no-sleep streaming path produced record 100 TP=148, FP=0, FN=0, F1=1.0000, HR MAE=0.148 BPM; record 118 TP=146, FP=0, FN=1, F1=0.9966, HR MAE=0.197 BPM. The remaining record 118 miss is its final beat, 25 samples from the replay end and inside the 0.5 s commit safety margin. The historical pre-fix result and diagnosis are retained only in `docs/streaming_record118_diagnostic.md`.

## Results package

- `results/figures/system_architecture.svg`: final pipeline.
- `results/figures/dashboard_record100.png`: actual browser capture, not a synthetic mockup.
- `results/figures/rpeak_overlay_record100.png`: raw, filtered, reference, and detected R peaks.
- `results/metrics/core_evaluation.csv`: reproducible core offline metrics.
- `results/figures/f1_vs_noise.png` and `results/metrics/noise_robustness.csv`: completed optional NSTDB check.

## Git and publication

- Final commit: `docs: finalize Cardia virtual ECG course project` (resolve the committed SHA with `git rev-parse HEAD`).
- Annotated release tag: `v1.0-course-project` (resolve its commit with `git rev-parse 'v1.0-course-project^{commit}'`).
- Local branch: `main`; original Cardia history and phase commits remain intact.
- `origin`: https://github.com/Kangsoolim/Cardia-Virtual-ECG.git. The local final commit and corrected tag have **not** been confirmed on GitHub.
- `upstream`: https://github.com/nisamaasoglu/Cardia.git, retained for attribution only.
- The user's Word course plan is ignored and stays local; raw PhysioNet files, `.venv`, caches, and logs are not tracked.

## Reproduction

From the repository root, install `requirements.txt`, then run `python -m pytest -q tests`, `python scripts/run_offline_baseline.py`, `python scripts/run_evaluation.py`, and `python scripts/run_virtual_device.py --record 100 --speed 1`. See `README.md` for the dashboard URL and optional NSTDB command. PhysioNet access is needed for records unless a local WFDB directory is supplied.
