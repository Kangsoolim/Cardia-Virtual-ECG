"""Read a short, single-lead MIT-BIH record and its beat annotations."""

from dataclasses import dataclass

import numpy as np
import wfdb


# WFDB beat codes only. In particular, '+', '~', and '|' are not heartbeats.
BEAT_SYMBOLS = frozenset("NLRaVFJASEj/QBenfr")
PREFERRED_LEADS = ("MLII", "II", "I", "V5", "V1")


@dataclass(frozen=True)
class ECGRecord:
    record: str
    fs: float
    channel: str
    unit: str
    raw: np.ndarray
    annotation_samples: np.ndarray
    annotation_symbols: tuple[str, ...]
    beat_samples: np.ndarray
    source: str


def choose_channel(sig_names: list[str]) -> int:
    """Prefer MLII/lead II for QRS detection, then a conventional ECG lead."""
    if not sig_names:
        raise ValueError("Record has no signal channels")
    normalized = [name.upper().replace(" ", "") for name in sig_names]
    for lead in PREFERRED_LEADS:
        if lead in normalized:
            return normalized.index(lead)
    raise ValueError(f"No supported ECG lead among {sig_names!r}")


def filter_beat_annotations(samples: np.ndarray, symbols: tuple[str, ...]) -> np.ndarray:
    """Retain only WFDB beat symbols; skip rhythm, noise, and artifact codes."""
    samples = np.asarray(samples, dtype=np.int64)
    if len(samples) != len(symbols):
        raise ValueError("Annotation samples/symbols have different lengths")
    mask = np.fromiter((symbol in BEAT_SYMBOLS for symbol in symbols), dtype=bool)
    return samples[mask]


def load_record(record: str, duration_s: float = 120.0, source: str = "mitdb") -> ECGRecord:
    """Read from PhysioNet ``mitdb`` or a local WFDB record path.

    ``source='mitdb'`` uses WFDB's PhysioNet reader; a local source is a
    directory containing the record files, e.g. ``data/raw/mitdb``.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    name = record if source == "mitdb" else f"{source}/{record}"
    remote = {"pn_dir": "mitdb"} if source == "mitdb" else {}
    header = wfdb.rdheader(name, **remote)
    channel_index = choose_channel(header.sig_name)
    sample_count = min(int(round(duration_s * header.fs)), header.sig_len)
    samples, fields = wfdb.rdsamp(name, sampto=sample_count, channels=[channel_index], **remote)
    annotation = wfdb.rdann(name, "atr", sampto=sample_count, **remote)
    raw = np.asarray(samples[:, 0], dtype=float)
    if raw.size != sample_count or not np.all(np.isfinite(raw)):
        raise ValueError(f"Invalid signal samples in record {record}")
    annotation_samples = np.asarray(annotation.sample, dtype=np.int64)
    annotation_symbols = tuple(annotation.symbol)
    return ECGRecord(
        record=str(record),
        fs=float(header.fs),
        channel=fields["sig_name"][0],
        unit=fields["units"][0],
        raw=raw,
        annotation_samples=annotation_samples,
        annotation_symbols=annotation_symbols,
        beat_samples=filter_beat_annotations(annotation_samples, annotation_symbols),
        source=source,
    )
