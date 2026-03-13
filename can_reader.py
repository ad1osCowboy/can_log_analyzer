#!/usr/bin/env python3
"""Robust CAN log reader and basic analyzer.

Usage example:
    python can_reader_refactored.py \
        --input sample.asc \
        --outdir output \
        --can-id 586 \
        --limit 300

What it does:
1. Reads a whitespace-delimited ASC/text CAN log.
2. Cleans and converts d0-d7 hex bytes to decimal.
3. Calculates CAN ID period summary (mean/std/count) and exports CSV.
4. Optionally analyzes one target CAN ID and saves byte/signal plots as PNG files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")  # Save figures without requiring a GUI
import matplotlib.pyplot as plt
import pandas as pd

BYTE_COLS = [f"d{i}" for i in range(8)]
BASE_COLS = [
    "timestamp", "channel", "can_id", "direction", "frame_type", "dlc",
    *BYTE_COLS,
]


class CanReaderError(Exception):
    """Custom exception for predictable CAN reader failures."""



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read, clean, summarize, and plot CAN log data."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input ASC/text log file.",
    )
    parser.add_argument(
        "--outdir",
        default="output",
        help="Directory to save CSV summaries and plots. Default: output",
    )
    parser.add_argument(
        "--can-id",
        default=None,
        help="Optional target CAN ID for byte/signal plots, for example 586 or 18ef1900x.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Number of rows to plot for the selected CAN ID. Default: 300",
    )
    parser.add_argument(
        "--delimiter",
        default=r"\s+",
        help=r"Regex delimiter for reading the file. Default: \s+",
    )
    return parser.parse_args()



def sanitize_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value))
    return safe.strip("_") or "unknown"



def byte_to_int(value: object) -> int | None:
    """Convert one CAN byte to decimal.

    Supports values like:
    - 1A
    - 0x1A
    - 1a
    - nan / None / empty
    Returns None for invalid values.
    """
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None

    text = text.upper()
    if text.startswith("0X"):
        text = text[2:]

    try:
        return int(text, 16)
    except ValueError:
        return None



def load_can_log(input_file: Path, delimiter: str = r"\s+") -> pd.DataFrame:
    if not input_file.exists():
        raise CanReaderError(f"Input file not found: {input_file}")

    df = pd.read_csv(
        input_file,
        sep=delimiter,
        header=None,
        comment=';',
        on_bad_lines='skip',
        engine='python',
        dtype=str,
    )

    if df.empty:
        raise CanReaderError("Input file was read successfully, but it contains no usable rows.")

    if df.shape[1] < len(BASE_COLS):
        raise CanReaderError(
            f"Expected at least {len(BASE_COLS)} columns, but found {df.shape[1]}. "
            "This file format does not match the current parser layout."
        )

    df = df.iloc[:, :len(BASE_COLS)].copy()
    df.columns = BASE_COLS

    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["can_id"] = df["can_id"].astype(str).str.strip()
    df["dlc"] = pd.to_numeric(df["dlc"], errors="coerce")

    return df



def clean_byte_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    bad_examples: list[tuple[str, str]] = []
    invalid_count = 0

    for col in BYTE_COLS:
        original = df[col].copy()
        df[col] = df[col].apply(byte_to_int)

        invalid_mask = original.notna() & df[col].isna() & (original.astype(str).str.strip() != "")
        if invalid_mask.any():
            invalid_values = original[invalid_mask].astype(str).tolist()
            invalid_count += len(invalid_values)
            for value in invalid_values[:5]:
                bad_examples.append((col, value))

    report = {
        "invalid_hex_count": invalid_count,
        "invalid_hex_examples": bad_examples[:10],
    }
    return df, report



def build_period_summary(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["period"] = work.groupby("can_id")["timestamp"].diff()
    summary = (
        work.groupby("can_id")["period"]
        .agg(mean="mean", std="std", count="count")
        .reset_index()
    )
    summary["mean"] = pd.to_numeric(summary["mean"], errors="coerce")
    summary = summary.sort_values(["mean", "count"], ascending=[True, False], na_position="last")
    return summary



def add_adjacent_signals(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for i in range(7):
        low = BYTE_COLS[i]
        high = BYTE_COLS[i + 1]
        sig = f"sig{i}{i+1}"
        work[sig] = work[low] + 256 * work[high]
    return work



def save_plot(series: pd.Series, title: str, ylabel: str, outpath: Path) -> None:
    plt.figure(figsize=(10, 4))
    plt.plot(series.reset_index(drop=True))
    plt.xlabel("sample index")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()



def plot_target_can_id(df: pd.DataFrame, can_id: str, outdir: Path, limit: int) -> list[Path]:
    one = df[df["can_id"] == str(can_id)].copy()
    if one.empty:
        raise CanReaderError(f"CAN ID {can_id} not found in the input file.")

    one = add_adjacent_signals(one)
    sample = one.iloc[:limit].copy()
    saved_files: list[Path] = []

    byte_dir = outdir / "plots_bytes"
    sig_dir = outdir / "plots_signals"
    byte_dir.mkdir(parents=True, exist_ok=True)
    sig_dir.mkdir(parents=True, exist_ok=True)

    for col in BYTE_COLS:
        outpath = byte_dir / f"{sanitize_name(can_id)}_{col}.png"
        save_plot(
            sample[col],
            title=f"{col} first {len(sample)} samples ({can_id})",
            ylabel="byte value (decimal)",
            outpath=outpath,
        )
        saved_files.append(outpath)

    for i in range(7):
        sig = f"sig{i}{i+1}"
        outpath = sig_dir / f"{sanitize_name(can_id)}_{sig}.png"
        save_plot(
            sample[sig],
            title=f"{sig} first {len(sample)} samples ({can_id})",
            ylabel="combined value (decimal)",
            outpath=outpath,
        )
        saved_files.append(outpath)

    return saved_files



def write_report(outdir: Path, input_file: Path, df: pd.DataFrame, summary: pd.DataFrame, clean_report: dict[str, object], can_id: str | None) -> Path:
    report_file = outdir / "run_report.txt"
    lines = [
        "CAN Reader Run Report",
        "=" * 24,
        f"Input file: {input_file}",
        f"Rows loaded: {len(df)}",
        f"Unique CAN IDs: {df['can_id'].nunique(dropna=True)}",
        f"Invalid hex values: {clean_report['invalid_hex_count']}",
        f"Invalid hex examples: {clean_report['invalid_hex_examples']}",
        f"Target CAN ID: {can_id if can_id is not None else 'None'}",
        f"Summary rows: {len(summary)}",
    ]
    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file



def main() -> None:
    args = parse_args()
    input_file = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_can_log(input_file=input_file, delimiter=args.delimiter)
    df, clean_report = clean_byte_columns(df)

    summary = build_period_summary(df)
    summary_file = outdir / "canid_summary.csv"
    summary.to_csv(summary_file, index=False)

    plots: list[Path] = []
    if args.can_id is not None:
        plots = plot_target_can_id(df=df, can_id=args.can_id, outdir=outdir, limit=args.limit)

    report_file = write_report(
        outdir=outdir,
        input_file=input_file,
        df=df,
        summary=summary,
        clean_report=clean_report,
        can_id=args.can_id,
    )

    print(f"Summary saved: {summary_file}")
    print(f"Run report saved: {report_file}")
    if clean_report["invalid_hex_count"]:
        print(f"Invalid hex values found: {clean_report['invalid_hex_count']}")
        print(f"Examples: {clean_report['invalid_hex_examples']}")
    if plots:
        print(f"Saved {len(plots)} plot files for CAN ID {args.can_id}.")
    print("Done")


if __name__ == "__main__":
    try:
        main()
    except CanReaderError as exc:
        raise SystemExit(f"ERROR: {exc}")
