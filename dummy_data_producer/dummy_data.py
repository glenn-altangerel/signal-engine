from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

def _format_ts_series_standard(s: pd.Series) -> pd.Series:
    """
    Format timezone-aware timestamps to: 'YYYY-MM-DD HH:MM:SS+00:00'
    (space separator, and timezone offset with colon).
    """
    # ISO-8601 / RFC 3339 style: 'YYYY-MM-DDTHH:MM:SS+00:00'
    return s.dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(
        r"([+-]\d{2})(\d{2})$", r"\1:\2", regex=True
    )

def generate_dummy_ohlcv_daily_csvs(
    start_date: str,
    end_date: str,
    freq: str,
    signal_dir: str = "data",
    symbol: str | None = None,
    seed: int = 1234,
    start_price: float = 100.0,
    base_volume: float = 1_000.0,
    tz: str = "UTC",
) -> None:
    """
    Generate dummy random OHLCV bars for each day in [start_date, end_date] (inclusive),
    and write one CSV per date into `signal_dir`.

    Each CSV columns:
      open_time, close_time, open, high, low, close, volume

    File name:
      YYYY-MM-DD.csv  (or YYYY-MM-DD_<symbol>.csv if symbol is provided)

    Timestamp output format (standardized):
      YYYY-MM-DD HH:MM:SS+00:00   (space separator; timezone offset includes colon)
    """
    out_path = Path(signal_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)

    # Normalize inputs to midnight boundaries in the requested timezone.
    start = pd.Timestamp(start_date, tz=tz).normalize()
    end = pd.Timestamp(end_date, tz=tz).normalize()
    if end < start:
        raise ValueError("end_date must be >= start_date")

    for day in pd.date_range(start, end, freq="D", tz=tz):
        day_start = day
        day_end = day + pd.Timedelta(days=1)

        open_times = pd.date_range(day_start, day_end, freq=freq, tz=tz, inclusive="left")
        if len(open_times) == 0:
            continue

        close_times = open_times + pd.Timedelta(freq)
        close_times = close_times.map(lambda ts: min(ts, day_end))

        n = len(open_times)

        # --- Price process ---
        vol = 0.002
        drift = 0.0
        rets = drift + vol * rng.standard_normal(n)
        close_prices = start_price * np.exp(np.cumsum(rets))

        gap_vol = 0.0005
        gap = gap_vol * rng.standard_normal(n)
        open_prices = np.empty(n, dtype=float)
        open_prices[0] = start_price * np.exp(gap[0])
        open_prices[1:] = close_prices[:-1] * np.exp(gap[1:])

        wick_scale = 0.0015
        wick_up = np.abs(wick_scale * rng.standard_normal(n))
        wick_dn = np.abs(wick_scale * rng.standard_normal(n))

        high_base = np.maximum(open_prices, close_prices)
        low_base = np.minimum(open_prices, close_prices)

        high_prices = high_base * (1.0 + wick_up)
        low_prices = low_base * (1.0 - wick_dn)

        vol_sigma = 0.35
        volume = base_volume * np.exp(vol_sigma * rng.standard_normal(n))

        df = pd.DataFrame(
            {
                "open_time": open_times,
                "close_time": close_times,
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volume,
            }
        )

        # Round numeric columns for nicer CSVs (2 decimal places for prices)
        price_cols = ["open", "high", "low", "close"]
        df[price_cols] = df[price_cols].round(2)

        # Optional: also round volume (choose what you want)
        df["volume"] = df["volume"].round(2)   # or round(0) if you prefer integer-like volumes


        # --- Standardize timestamp string format ---
        df["open_time"] = _format_ts_series_standard(pd.to_datetime(df["open_time"]))
        df["close_time"] = _format_ts_series_standard(pd.to_datetime(df["close_time"]))

        date_str = day.strftime("%Y-%m-%d")
        fname = f"{date_str}.csv" if not symbol else f"{date_str}_{symbol}.csv"
        fpath = out_path / fname

        df.to_csv(fpath, index=False)

        # Carry forward last close as next day's start price
        start_price = float(df["close"].iloc[-1])



if __name__ == "__main__":
    signal_dir = Path(__file__).resolve().parent.parent / "data" / "asset_name"
    generate_dummy_ohlcv_daily_csvs(
        start_date="2025-12-01",
        end_date="2025-12-07",
        freq="60min",
        signal_dir=str(signal_dir),
        symbol=None,
        seed=42,
        start_price=100.0,
        base_volume=1_000.0,
        tz="UTC",
    )