from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd

from strategy.strategy import Strategy
from .watcher import LinearCSVFolderWatcher


class RealTimeTrader:
    """
    Event-driven real-time trader.

    On each watcher trigger:
      - loads the most recent window across daily CSVs
      - if enough rows: computes signal for last timestep and
        appends it to signals/asset_name/YYYY-MM-DD.csv (schema identical to backtester)
      - else: prints a waiting message
    """

    HEADER = "open_time,close_time,signal\n"

    def __init__(self, args, strategy: Strategy):
        self.data_dir = Path(args.data_dir)
        self.signal_dir = Path(args.signal_dir)
        self.strategy = strategy
        self.window_len = int(strategy.num_past_timesteps)

        self._last_written: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None

        poll_interval = float(getattr(args, "poll_interval", 0.5))

        self.watcher = LinearCSVFolderWatcher(
            folder=self.data_dir,
            on_new_data=self.on_new_data,
            poll_interval=poll_interval,
        )

    @staticmethod
    def _format_ts_iso_t(ts: pd.Timestamp) -> str:
        """
        Format a timestamp as ISO-8601 / RFC3339 with 'T' and timezone colon:
          YYYY-MM-DDTHH:MM:SS+00:00
        """
        ts = pd.to_datetime(ts, utc=True, errors="raise")
        s = ts.strftime("%Y-%m-%dT%H:%M:%S%z")  # %z -> +0000
        # Convert +0000 -> +00:00
        if len(s) >= 5 and (s[-5] in ["+", "-"]) and s[-2:].isdigit():
            s = s[:-2] + ":" + s[-2:]
        return s

    def start(self) -> None:
        self.watcher.start()

    # =========================
    # Watcher callback
    # =========================
    def on_new_data(self, filename: str, line: str) -> None:
        window = self._load_latest_window(self.window_len)

        if window is None or len(window) < self.window_len:
            print("New data bar detected but not enough bars for generating signal. Waiting for more bars.")
            print("新しいデータを受信しましたが、シグナル生成にはデータが不足しています。追加データ待ちです。")
            return

        # Signal for the last timestep of the window
        signal = self.strategy.per_step(window)

        last = window.iloc[-1]
        open_time: pd.Timestamp = last["open_time"]
        close_time: pd.Timestamp = last["close_time"]

        print(
            f"[signal] {self._format_ts_iso_t(open_time)} -> "
            f"{self._format_ts_iso_t(close_time)} : {signal}"
        )

        # Write to per-day signal CSV (same format as backtester)
        self._append_signal_row(open_time=open_time, close_time=close_time, signal=signal)

    # =========================
    # Data loading
    # =========================
    def _load_latest_window(self, n: int) -> Optional[pd.DataFrame]:
        csvs = sorted(self.data_dir.glob("*.csv"))
        if not csvs:
            return None

        chunks: List[pd.DataFrame] = []
        rows = 0

        # Read from newest backwards until we have n rows
        for path in reversed(csvs):
            try:
                df = pd.read_csv(path)
            except Exception:
                return None  # file mid-write

            if df.empty:
                continue

            if "open_time" not in df.columns or "close_time" not in df.columns:
                raise ValueError(f"Missing open_time/close_time columns in {path}")

            # Reads both:
            # - 2025-12-08T11:00:00+00:00
            # - 2025-12-08 11:00:00+00:00
            df["open_time"] = pd.to_datetime(
                df["open_time"], utc=True, errors="raise", format="mixed"
            )
            df["close_time"] = pd.to_datetime(
                df["close_time"], utc=True, errors="raise", format="mixed"
            )
            df = df.sort_values("open_time", kind="mergesort").reset_index(drop=True)

            need = n - rows
            if need <= 0:
                break

            tail = df.tail(need)
            chunks.append(tail)
            rows += len(tail)

            if rows >= n:
                break

        if rows < n:
            return None

        out = pd.concat(reversed(chunks), ignore_index=True)
        out = out.sort_values("open_time", kind="mergesort").reset_index(drop=True)
        return out.tail(n).reset_index(drop=True)

    # =========================
    # Signal persistence
    # =========================
    def _append_signal_row(self, open_time: pd.Timestamp, close_time: pd.Timestamp, signal: str) -> None:
        """
        Append one row into signals/asset_name/<YYYY-MM-DD>.csv, schema:
          open_time,close_time,signal

        Prevents duplicates by checking:
          - in-memory last written key, and
          - existing file content (tail scan) for the same open_time/close_time
        """
        key = (open_time, close_time)
        if self._last_written == key:
            return  # same process, same row

        # Determine output file by open_time date
        day = open_time.date()
        out_path = self.signal_dir / f"{day}.csv"
        self.signal_dir.mkdir(parents=True, exist_ok=True)

        # Ensure header exists if file is new
        if not out_path.exists():
            out_path.write_text(self.HEADER, encoding="utf-8")

        # Dedup against existing file (fast tail read)
        if self._row_already_written(out_path, open_time, close_time):
            self._last_written = key
            return

        # Append row (force ISO 'T' format)
        open_s = self._format_ts_iso_t(open_time)
        close_s = self._format_ts_iso_t(close_time)
        row = f"{open_s},{close_s},{signal}\n"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(row)

        self._last_written = key

    def _row_already_written(self, out_path: Path, open_time: pd.Timestamp, close_time: pd.Timestamp) -> bool:
        """
        Check if (open_time, close_time) already exists in the output file.
        We only scan the last ~200 lines to keep it cheap.
        (The number 200 has nothing to do with how many data entries the strategy can look at)
        """
        try:
            text = out_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) <= 1:
            return False  # only header

        # Scan tail lines; good enough for append-only stream
        tail = lines[-200:]

        # Compare against the enforced output format, so dedup works even if older rows used space format.
        open_s = self._format_ts_iso_t(open_time)
        close_s = self._format_ts_iso_t(close_time)

        for ln in tail:
            if ln.lower().startswith("open_time,"):
                continue
            parts = ln.split(",")
            if len(parts) < 3:
                continue

            # Backward-compatible dedup:
            # If the file contains older rows with space separator, normalize them via pandas parsing.
            try:
                existing_open = pd.to_datetime(parts[0], utc=True, errors="raise")
                existing_close = pd.to_datetime(parts[1], utc=True, errors="raise")
                existing_open_s = self._format_ts_iso_t(existing_open)
                existing_close_s = self._format_ts_iso_t(existing_close)
            except Exception:
                continue

            if existing_open_s == open_s and existing_close_s == close_s:
                return True

        return False
