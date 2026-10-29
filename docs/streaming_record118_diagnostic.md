# Record 118 streaming peak timestamp diagnostic

This is the one-time diagnostic for the 120 s no-sleep MIT-BIH replay. The offline and streaming evaluations used the same loaded MLII signal, 360 Hz sampling rate, 147 filtered beat annotations, 120 s interval, NeuroKit2 `pantompkins1985` detector, and one-to-one ±100 ms matching. The offline filter is zero-phase; the streaming filter is causal with continuous state across 0.25 s chunks.

## Before correction

Record 118: 147 reference beats, 146 committed peaks, TP=18, FP=128, FN=129, F1=0.1229. First 20 reference indices:

```text
68, 369, 674, 980, 1284, 1587, 1879, 2175, 2475, 2766,
3054, 3364, 3674, 3978, 4282, 4580, 4883, 5171, 5464, 5762
```

First 20 committed indices:

```text
104, 407, 712, 1017, 1322, 1625, 1917, 2212, 2512, 2803,
3091, 3400, 3712, 4016, 4319, 4618, 4921, 5208, 5501, 5799
```

The 10–20 s [diagnostic overlay](../results/figures/streaming_diagnostic_record118.png) is a **PRE-FIX diagnostic figure**, not a final project result figure. It shows one committed peak for each reference beat but around 37 samples late. A diagnostic-only 36-sample backward shift made TP=146, FP=0, FN=1, F1=0.9966. Thus the original FP/FN counts mostly represent the same beats outside matching tolerance, not independent false detections and misses.

## Root cause and minimal correction

The local-to-global rolling-buffer mapping and causal filter continuity were correct. The record 118 QRS has a small positive raw R wave followed by a much larger negative component. The causal 5–15 Hz filtered signal develops a later positive rebound, and the detector's filtered positive-maximum localization reports that rebound roughly 36–38 samples after the annotated R wave. Record 100's corresponding offset was only 4–5 samples. The ±100 ms evaluator accepts at most 36 samples at 360 Hz.

The streaming implementation now keeps a raw buffer aligned with the filtered detector buffer and maps each unchanged detector candidate to the nearby positive raw maximum before committing its global sample index. One fixed ±150 ms search is used for both records; there is no record-specific setting or detector replacement. A flat raw fixture retains the candidate index, preserving the commit/de-duplication tests.

## After correction

| Record | Reference | Committed | TP | FP | FN | F1 | HR MAE (BPM) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100 | 148 | 148 | 148 | 0 | 0 | 1.0000 | 0.148 |
| 118 | 147 | 146 | 146 | 0 | 1 | 0.9966 | 0.197 |

First 20 corrected record 118 indices:

```text
70, 370, 676, 982, 1285, 1589, 1881, 2177, 2477, 2768,
3055, 3366, 3676, 3980, 4284, 4582, 4885, 5173, 5466, 5764
```

The remaining miss is the last reference beat at sample 43175, 25 samples before the end. The existing 0.5 s safe-margin gate cannot commit an event that close to the end without further samples. This terminal edge effect is small and has been left unchanged in this minimal fix.
