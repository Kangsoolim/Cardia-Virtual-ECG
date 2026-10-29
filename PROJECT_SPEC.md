# Project Specification

## Identity

- **Title:** Virtual ECG Acquisition and Real-Time Monitoring Based on Cardia
- **Project root:** repository root (commands in this document are relative to it).
- **Upstream:** [nisamaasoglu/Cardia](https://github.com/nisamaasoglu/Cardia), imported `main` commit `3f8b655f3a92de3579836d19c95a2e33c8e6f7f2`.
- **Attribution and license:** Cardia by Nisa Maaşoğlu; original MIT License retained in `LICENSE`. See `THIRD_PARTY_NOTICES.md`.

## Core pipeline

MIT-BIH ECG → Python virtual real-time replay → simple band-pass → one R-peak detector → RR/BPM → Python HTTP JSON device → modified Cardia dashboard → annotation-based evaluation.

## Required components

The project must retain: Cardia frontend; Python Virtual ECG Device; MIT-BIH; real-time replay; band-pass filtering; one R-peak detector; RR/BPM calculation; HTTP JSON; and annotation-based evaluation.

## Out of scope

Do not add deep learning, arrhythmia classification, HRV, multi-detector benchmarks, complex SQI, databases, cloud services, mobile apps, or hardware/SPICE simulation.

## Data

Core records are MIT-BIH Arrhythmia Database records **100** and **118**, sampled at **360 Hz**. A completed optional NSTDB robustness check uses record 118 at 300–420 seconds. Raw data files must not be committed; WFDB fetches source records on demand.

## Upstream Cardia architecture and demo behavior

Original path: **AD8232 → Arduino A0 at 500 Hz → Arduino R-peak/RR/BPM → 125 Hz waveform buffer → HTTP JSON → browser polling at 4 Hz**. The firmware serves JSON from `/`; the browser dashboard is a dependency-free static page.

Cardia's demo is a **browser-side synthetic waveform generator** (`DemoSource` in `web/app.js`). Its displayed demo BPM is supplied directly by the generator's `currentBpm()`; it is not calculated by a detector operating on the synthetic ECG waveform. Demo mode is distinct from the planned Python replay pipeline.

## Python dependencies

Expected packages: `numpy`, `scipy`, `wfdb`, `neurokit2`, `flask`, `matplotlib`, and `pytest`. See `requirements.txt`.

## Git rules

Commit after each phase's checks pass. Never commit raw files under `data/`. Never force-push. Preserve upstream history and attribution.
