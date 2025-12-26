from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Set, Callable


class LinearCSVFolderWatcher:
    """
    Append-only CSV folder watcher.

    Calls `on_new_data(filename, line)` whenever:
      - First data row appears in a newly created CSV
      - A new row is appended to the most recent CSV
    """

    def __init__(
        self,
        folder: str | Path,
        on_new_data: Callable[[str, str], None],
        poll_interval: float = 0.5,
    ):
        self.folder = Path(folder)
        self.poll_interval = poll_interval
        self.on_new_data = on_new_data

        self._offsets: Dict[Path, int] = {}
        self._known_files: Set[Path] = set()
        self._bootstrapped = False

    def start(self) -> None:
        print(f"[watcher] Watching folder: {self.folder.resolve()}")
        while True:
            self._poll_once()
            time.sleep(self.poll_interval)

    def _poll_once(self) -> None:
        csv_files = sorted(self.folder.glob("*.csv"))
        if not csv_files:
            return

        # Bootstrap: skip all existing content
        if not self._bootstrapped:
            for p in csv_files:
                self._known_files.add(p)
                self._offsets[p] = p.stat().st_size
            self._bootstrapped = True
            return

        latest_file = csv_files[-1]

        # Detect new files
        for p in csv_files:
            if p not in self._known_files:
                self._known_files.add(p)
                self._handle_new_file_created(p)

        # Read appends only from the most recent file
        self._read_appends(latest_file)

    def _handle_new_file_created(self, path: Path) -> None:
        self._offsets[path] = 0

        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        data_lines = [ln for ln in lines if not self._is_header(ln)]

        if data_lines:
            # Trigger ONLY the first data row
            self.on_new_data(path.name, data_lines[0])

        self._offsets[path] = path.stat().st_size

    def _read_appends(self, path: Path) -> None:
        last_offset = self._offsets.get(path)
        if last_offset is None:
            self._offsets[path] = path.stat().st_size
            return

        try:
            current_size = path.stat().st_size
        except FileNotFoundError:
            return

        if current_size <= last_offset:
            return

        with path.open("r", encoding="utf-8") as f:
            f.seek(last_offset)
            chunk = f.read()

        self._offsets[path] = current_size

        for line in chunk.splitlines():
            line = line.strip()
            if not line or self._is_header(line):
                continue
            self.on_new_data(path.name, line)

    @staticmethod
    def _is_header(line: str) -> bool:
        return line.lower().startswith("open_time,")
