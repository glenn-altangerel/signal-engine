from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from strategy.strategy import Strategy


class Backtester:
    def __init__(self, args: argparse.Namespace, strategy: Strategy) -> None:
        self.data_dir = Path(args.data_dir)
        self.signal_dir = Path(args.signal_dir)
        self.strategy = strategy

    def _load_ohlcv(self) -> pd.DataFrame:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"data_dir not found: {self.data_dir}")

        csvs = sorted(self.data_dir.glob("*.csv"))
        if not csvs:
            warnings.warn(
                f"No CSV files found in data_dir: {self.data_dir}\n"
                f"data_dir に CSV ファイルが見つかりません: {self.data_dir}",
                RuntimeWarning,
            )
            return pd.DataFrame()

        df = pd.concat((pd.read_csv(p) for p in csvs), ignore_index=True)

        required = {"open_time", "close_time"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="raise", format="mixed")
        df["close_time"] = pd.to_datetime(df["close_time"], utc=True, errors="raise", format="mixed")
        df = df.sort_values("open_time", kind="mergesort").reset_index(drop=True)
        return df

    def _write_signals_per_day(self, sig_df: pd.DataFrame) -> None:
        """
        Write per-day CSV files containing ONLY rows where a signal exists.
        Timesteps with no corresponding generated signal are excluded.
        """
        self.signal_dir.mkdir(parents=True, exist_ok=True)

        out = sig_df.copy()

        # Keep only rows with actual signals
        out = out[out["signal"].notna()].copy()
        if out.empty:
            return

        out["date"] = out["open_time"].dt.date

        for d, g in out.groupby("date", sort=True):
            # g is guaranteed non-empty here, but keep this defensive check
            if g.empty:
                continue

            g[["open_time", "close_time", "signal"]].to_csv(
                self.signal_dir / f"{d}.csv",
                index=False,
            )

    def run(self) -> pd.DataFrame:
        df = self._load_ohlcv()
        if df.empty:
            return df

        n = len(df)
        window_len = int(self.strategy.num_past_timesteps)

        if n < window_len:
            warnings.warn(
                f"Not enough data to generate even one signal window: need {window_len}, got {n}\n"
                f"1 つのシグナルウィンドウを生成するのに十分なデータがありません: 必要数は {window_len}、取得できたのは {n} です",
                RuntimeWarning,
            )

        signals = np.full(n, None, dtype=object)
        start = window_len - 1

        for t in range(start, n):
            window = df.iloc[t - window_len + 1 : t + 1]
            signals[t] = self.strategy.per_step(window)

        out = df.copy()
        out["signal"] = signals

        # Only rows with non-null signals will be written
        self._write_signals_per_day(out[["open_time", "close_time", "signal"]])
        return out
