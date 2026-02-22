from __future__ import annotations

import argparse

import pandas as pd

from .config import load_settings
from .holidays import national_holidays_2026
from .io_utils import list_export_files, load_json, write_run_manifest
from .extract import build_member_lookup, find_account_id_by_name, extract_checkins_raw, extract_my_cardio_sessions
from .transforms import (
    leaderboard_from_raw_checkins,
    extract_winners_daily,
    extract_champions_weekly,
    dedupe_cardio,
    extract_my_cardio_weekly_km,
    extract_my_cardio_progress,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process GymRats Pro JSON exports and generate leaderboards + cardio reports."
    )
    parser.add_argument("--user", type=str, required=False, help="Seu nome (members.full_name).")
    parser.add_argument("--year", type=int, default=2026, help="Ano de referência (foco em 2026).")
    parser.add_argument("--exports-dir", type=str, default="exports", help="Pasta com JSONs.")
    parser.add_argument("--out-dir", type=str, default="out", help="Pasta de saída.")
    parser.add_argument("--verbose", action="store_true", help="Logs adicionais.")
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    settings = load_settings(args.user, args.year, args.exports_dir, args.out_dir, args.verbose)

    if settings.year != 2026:
        raise SystemExit("Por enquanto, apenas year=2026 está suportado para feriados nacionais.")

    holidays = national_holidays_2026()

    if not settings.exports_dir.exists():
        raise SystemExit(f"Pasta não encontrada: {settings.exports_dir}")

    files = list_export_files(settings.exports_dir, verbose=settings.verbose)
    if not files:
        raise SystemExit(f"Nenhum export JSON válido encontrado em: {settings.exports_dir}")

    if settings.verbose:
        print(f"Processando {len(files)} arquivo(s): {[f.name for f in files]}")

    first_data = load_json(files[0])
    member_lookup = build_member_lookup(first_data)

    my_account_id = find_account_id_by_name(member_lookup, settings.user)
    if my_account_id is None:
        available = sorted(set(member_lookup.values()))
        raise SystemExit(
            "Não encontrei o usuário informado em members.full_name.\n"
            f"User recebido: {settings.user}\n"
            f"Nomes disponíveis (amostra): {available[:20]}"
        )

    raw_checkins_all = []
    cardio_all = []

    for p in files:
        data = load_json(p)
        raw_checkins_all.append(extract_checkins_raw(data, member_lookup, holidays))
        cardio_all.append(extract_my_cardio_sessions(data, member_lookup, my_account_id))

    settings.out_dir.mkdir(parents=True, exist_ok=True)

    df_raw = pd.concat(raw_checkins_all, ignore_index=True)
    if not df_raw.empty:
        df_raw = df_raw.drop_duplicates(subset=["dedupe_key"], keep="first")

    df_leader = leaderboard_from_raw_checkins(df_raw)
    df_leader.to_csv(settings.out_dir / "leaderboard_daily.csv", index=False, encoding="utf-8")

    df_winners = extract_winners_daily(df_leader)
    df_winners.to_csv(settings.out_dir / "winners_daily.csv", index=False, encoding="utf-8")

    df_champ = extract_champions_weekly(df_leader)
    df_champ.to_csv(settings.out_dir / "champions_weekly.csv", index=False, encoding="utf-8")

    df_cardio = pd.concat(cardio_all, ignore_index=True)
    df_cardio = dedupe_cardio(df_cardio)
    df_cardio.to_csv(settings.out_dir / "my_cardio_sessions.csv", index=False, encoding="utf-8")

    df_weekly = extract_my_cardio_weekly_km(df_cardio)
    df_weekly.to_csv(settings.out_dir / "my_cardio_weekly_km.csv", index=False, encoding="utf-8")

    df_progress = extract_my_cardio_progress(df_weekly)
    df_progress.to_csv(settings.out_dir / "my_cardio_progress.csv", index=False, encoding="utf-8")

    write_run_manifest(settings.out_dir, files, df_leader, df_cardio)

    print(f"OK! Processados {len(files)} export(s). Saídas em: {settings.out_dir}/")


if __name__ == "__main__":
    run()