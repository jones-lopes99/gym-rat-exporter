from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


EXPORT_FILENAME_PATTERN = re.compile(r"^gym-rats_export-?\d{2}-\d{2}-\d{2}\.json$")


def list_export_files(export_dir: Path, verbose: bool = False) -> list[Path]:
    files: list[Path] = []
    for p in export_dir.glob("*.json"):
        if EXPORT_FILENAME_PATTERN.match(p.name):
            files.append(p)
        else:
            if verbose:
                print(f"[IGNORADO] Nome inválido: {p.name}")
    return sorted(files)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_run_manifest(
    out_dir: Path,
    files: list[Path],
    df_leader: pd.DataFrame,
    df_cardio: pd.DataFrame,
) -> None:
    manifest = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "processed_files_count": len(files),
        "processed_files": [f.name for f in files],
        "leaderboard_rows": int(len(df_leader)),
        "cardio_rows": int(len(df_cardio)),
    }
    with (out_dir / "run_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)