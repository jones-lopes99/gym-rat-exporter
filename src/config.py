from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    user: str
    year: int
    exports_dir: Path
    out_dir: Path
    verbose: bool


def load_settings(
    user_arg: str | None,
    year_arg: int,
    exports_dir_arg: str,
    out_dir_arg: str,
    verbose: bool,
) -> Settings:
    load_dotenv()

    user = user_arg or os.getenv("GYMRATS_USER")
    if not user:
        raise ValueError("User not provided. Use --user or set GYMRATS_USER in .env.")

    year_env = os.getenv("DEFAULT_YEAR")
    year = year_arg if year_arg is not None else int(year_env) if year_env else 2026

    return Settings(
        user=user,
        year=year,
        exports_dir=Path(exports_dir_arg),
        out_dir=Path(out_dir_arg),
        verbose=verbose,
    )