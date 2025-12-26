#!/usr/bin/env python3
"""
stream_append_dummy_ohlcv.py

Behavior:
- Infer the dataset candle interval from existing CSVs under data/<asset>/*.csv.
- Every APPEND_EVERY_SECONDS (default 5 seconds), append ONE new synthetic OHLCV row.
- The new row advances timestamps by the INFERRED candle interval (not by 5 seconds).
- One CSV per calendar date (based on open_time). If date changes, create a new CSV.

CSV schema:
open_time,close_time,open,high,low,close,volume
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


HEADER = ["open_time", "close_time", "open", "high", "low", "close", "volume"]
NO_BAR_WARN = "No continuous bars detected. Run dummy_data.py first. 連続したバーが検出されません。先に dummy_data.py を実行してください。"


@dataclass(frozen=True)
class LastBar:
    close_time: pd.Timestamp
    close: float


def _format_ts_standard(ts: pd.Timestamp) -> str:
    """
    Standardize timestamp format to match your existing CSVs:
      'YYYY-MM-DD HH:MM:SS+00:00'
    - Space separator (no 'T')
    - Timezone offset with colon (+0000 -> +00:00)
    """
    ts = pd.Timestamp(ts)

    s = ts.strftime("%Y-%m-%dT%H:%M:%S%z")
    if len(s) >= 5 and (s[-5] in ["+", "-"]) and s[-2:].isdigit():
        s = s[:-2] + ":" + s[-2:]
    return s


def _tail_last_data_line(path: Path) -> Optional[str]:
    """Return the last non-empty line of a file (fast, no full read)."""
    if not path.exists() or path.stat().st_size == 0:
        return None

    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        if end == 0:
            return None

        block_size = 4096
        data = b""
        pos = end
        while pos > 0:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(read_size)
            data = chunk + data
            if b"\n" in chunk:
                break

        lines = data.splitlines()
        for raw in reversed(lines):
            s = raw.decode("utf-8", errors="replace").strip()
            if s:
                return s
    return None


def _parse_last_row_from_csv(path: Path) -> Optional[LastBar]:
    """
    Parse the last data row of a CSV to get (close_time, close).
    Assumes schema: open_time,close_time,open,high,low,close,volume
    """
    last_line = _tail_last_data_line(path)
    if not last_line:
        return None

    if last_line.lower().replace(" ", "") == ",".join(HEADER):
        return None

    parts = [p.strip() for p in last_line.split(",")]
    if len(parts) < 7:
        return None

    close_time = pd.to_datetime(parts[1], utc=False)
    close = float(parts[5])
    return LastBar(close_time=close_time, close=close)


def find_latest_bar(asset_dir: Path) -> LastBar:
    """Find the latest close_time across all CSVs and return its close price as seed."""
    csvs = sorted(asset_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found under: {asset_dir}")

    latest: Optional[LastBar] = None
    for p in csvs:
        lb = _parse_last_row_from_csv(p)
        if lb is None:
            continue
        if latest is None or lb.close_time > latest.close_time:
            latest = lb

    if latest is None:
        raise ValueError(f"Found CSVs under {asset_dir}, but no valid data rows.")
    return latest


def infer_candle_interval(
    asset_dir: Path,
    max_files: int = 10,
    max_rows_per_file: int = 500,
    min_bars_total: int = 3,
) -> pd.Timedelta:
    """
    Infer the candle interval using recent open_time deltas across recent files.
    Uses median positive diff of open_time.

    Requirements:
    - Must be able to observe at least `min_bars_total` bars overall (i.e., >= min_bars_total timestamps).
    - Must yield a meaningful median positive diff.
    """
    csvs = sorted(asset_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found under: {asset_dir}")

    recent = csvs[-max_files:]

    diffs = []
    total_timestamps = 0

    for p in recent:
        try:
            df = pd.read_csv(p, usecols=["open_time"], nrows=None)
            if df.empty:
                continue
            if len(df) > max_rows_per_file:
                df = df.tail(max_rows_per_file)

            t = pd.to_datetime(df["open_time"], utc=False, errors="coerce").dropna().sort_values()
            total_timestamps += len(t)

            if len(t) < 2:
                continue
            d = t.diff().dropna()
            d = d[d > pd.Timedelta(0)]
            diffs.extend(d.tolist())
        except Exception:
            continue

    # Enforce: at least 3 bars overall (>= 3 timestamps)
    if total_timestamps < min_bars_total:
        raise ValueError(
            f"Not enough bars to infer interval (need >= {min_bars_total} bars)."
        )

    if not diffs:
        raise ValueError(
            f"Could not infer interval from open_time diffs under {asset_dir}. "
            f"Ensure CSVs have valid open_time values."
        )

    interval = pd.to_timedelta(pd.Series(diffs).median())
    if interval <= pd.Timedelta(0):
        raise ValueError("Inferred a non-positive interval; check your timestamps.")
    return interval


def ensure_daily_csv(asset_dir: Path, day_str: str) -> Path:
    """Return the path for YYYY-MM-DD.csv; create file + header if missing."""
    path = asset_dir / f"{day_str}.csv"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
    return path


def append_row(path: Path, row: list) -> None:
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def make_dummy_bar(last: LastBar, candle_interval: pd.Timedelta):
    """
    Create a new synthetic bar:
      open_time = last.close_time
      close_time = open_time + candle_interval
    """
    open_time = last.close_time
    close_time = open_time + candle_interval

    o = last.close

    step = random.gauss(0.0, max(1e-8, abs(o) * 0.0005))
    c = max(1e-8, o + step)

    wiggle = abs(random.gauss(0.0, max(1e-8, abs(o) * 0.0008)))
    high = max(o, c) + wiggle
    low = max(1e-8, min(o, c) - wiggle * 0.8)

    vol = max(0.0, random.gauss(1000.0, 300.0))

    row = [
        _format_ts_standard(open_time),
        _format_ts_standard(close_time),
        f"{o:.2f}",
        f"{high:.2f}",
        f"{low:.2f}",
        f"{c:.2f}",
        f"{vol:.2f}",
    ]

    day_str = open_time.date().isoformat()
    return LastBar(close_time=close_time, close=c), row, day_str


def _preflight_or_warn(asset_dir: Path) -> tuple[pd.Timedelta, LastBar]:
    """
    Validate that we have usable historical bars to seed streaming.
    If not, print the requested warning and raise.
    """
    # Explicitly check folder existence to match your requirement wording.
    if not DATA_ROOT.exists() or not DATA_ROOT.is_dir():
        raise RuntimeError(NO_BAR_WARN)

    if not asset_dir.exists() or not asset_dir.is_dir():
        raise RuntimeError(NO_BAR_WARN)

    try:
        candle_interval = infer_candle_interval(asset_dir, min_bars_total=3)
        last = find_latest_bar(asset_dir)
        return candle_interval, last
    except Exception as _:
        raise RuntimeError(NO_BAR_WARN)


REPO_ROOT = Path(__file__).resolve().parent.parent   # parent of dummy_data_producer/
DATA_ROOT = REPO_ROOT / "data"
ASSET = "asset_name"
APPEND_EVERY_SECONDS = 5


def main() -> int:
    asset_dir = DATA_ROOT / ASSET

    try:
        candle_interval, last = _preflight_or_warn(asset_dir)
    except RuntimeError as e:
        # Required exact message:
        print(f"[WARN] {e}")
        return 1

    print(f"[INFO] Inferred candle interval: {candle_interval} (from {asset_dir})")
    print(
        f"[INFO] Latest close_time found: "
        f"{_format_ts_standard(last.close_time)} | last close: {last.close:.6f}"
    )

    while True:
        last, row, day_str = make_dummy_bar(last, candle_interval)
        out_csv = ensure_daily_csv(asset_dir, day_str)
        append_row(out_csv, row)
        print(
            f"[APPEND] {out_csv.name} "
            f"open_time={row[0]} close_time={row[1]} close={row[5]}"
        )
        time.sleep(APPEND_EVERY_SECONDS)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
