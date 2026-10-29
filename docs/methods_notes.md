# Methods notes for the course report

## 1. Open-source system and modified architecture

Cardia (Nisa Maaşoğlu, MIT license) originally connects an AD8232 sensor to Arduino A0, samples at 500 Hz, computes R-peak/RR/BPM on Arduino, buffers a 125 Hz waveform, serves HTTP JSON, and is polled by a static browser dashboard at 4 Hz. This project retains the attributed Cardia interface and firmware but replaces the hardware acquisition path with a Python virtual ECG device. Flask serves the adapted page and current JSON snapshot on one origin. See `results/figures/system_architecture.svg`.

## 2. ECG dataset

The core dataset is MIT-BIH Arrhythmia Database records 100 and 118, first 120 seconds, MLII lead, 360 Hz, physical mV values. Python WFDB reads headers, signal samples, and `.atr` annotations. Beat symbols are retained; rhythm and noise markers are excluded. Record 100 contains 148 reference beats and record 118 contains 147 in the evaluated windows. Source data is fetched on demand and not committed.

## 3. Virtual real-time ECG replay

Replay divides each record into 0.25 s chunks (90 samples at 360 Hz). At speed 1 it schedules chunks against absolute monotonic deadlines; `--speed 0` uses the identical processing path without waits. A six-second raw-signal window is retained for display. One background replay publishes snapshots; HTTP polling only reads the latest one. Completed replay remains visible until the server is stopped.

## 4. ECG preprocessing and R-peak detection

Both paths use a second-order Butterworth 5–15 Hz band-pass and NeuroKit2's `pantompkins1985` detector. Offline detector events are localized to the positive filtered R maximum within ±100 ms. Offline processing uses zero-phase `sosfiltfilt`; streaming uses stateful causal `sosfilt` on chunks and an eight-second rolling detector buffer. Streaming detector candidates are localized to a nearby positive raw maximum within ±150 ms before global timestamps are committed; the same rule applies to both records. Streaming commits candidates after a 0.5 s right-edge margin and applies a 0.25 s refractory gate. Valid RR intervals are 0.3–2.0 s; displayed BPM is 60 divided by the mean of up to five recent valid RR intervals.

## 5. Cardia-compatible monitoring

Flask exposes `GET /api/ecg` and serves the adapted Cardia page. The browser polls every 250 ms and displays a six-second raw ECG trace, BPM, RR interval, amplitude, source, units, sample rate, beat count, and replay state. ECG remains in mV rather than Arduino ADC counts. BPM is unknown before valid beats and after a two-second stale interval. The `quality` flag means samples were received; it is not a signal-quality assessment.

## 6. Quantitative evaluation

For each 120 s core record, predicted peaks are matched chronologically one to one with `.atr` beat annotations within ±100 ms. TP, FP, FN, sensitivity, PPV, and F1 follow from these matches. HR MAE compares instantaneous BPM over adjacent matched intervals whose RR values are valid. The core table uses the offline path. A separate no-sleep streaming check uses the same annotations to expose path-specific behavior. The optional completed NSTDB check applies the offline pipeline to record 118 at 300–420 s under clean, 18 dB, 6 dB, and 0 dB conditions after checking aligned annotations.
