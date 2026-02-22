from __future__ import annotations

from datetime import date


def national_holidays_2026() -> set[date]:
    # Fonte: calendário oficial de feriados nacionais 2026 (MGI)
    return {
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 21),
        date(2026, 5, 1),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 2),
        date(2026, 11, 15),
        date(2026, 11, 20),
        date(2026, 12, 25),
    }