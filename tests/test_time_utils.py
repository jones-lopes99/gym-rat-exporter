from datetime import date

from src.time_utils import is_weekend
from src.holidays import national_holidays_2026
from src.time_utils import is_ignored_day
from src.time_utils import parse_iso_datetime_to_sp_day


def test_weekend_is_ignored():
    # 14/03/2026 é sábado
    saturday = date(2026, 3, 14)
    assert is_weekend(saturday) is True


def test_weekday_is_not_weekend():
    # 17/03/2026 é terça-feira
    tuesday = date(2026, 3, 17)
    assert is_weekend(tuesday) is False


def test_national_holiday_is_ignored():
    holidays = national_holidays_2026()
    holiday = date(2026, 11, 20)  # Consciência Negra
    assert is_ignored_day(holiday, holidays) is True


def test_normal_weekday_not_ignored():
    holidays = national_holidays_2026()
    normal_day = date(2026, 3, 17)  # terça comum
    assert is_ignored_day(normal_day, holidays) is False


def test_parse_iso_datetime_to_sp_day_same_day():
    # 15:00 UTC ainda é o mesmo dia em São Paulo
    day = parse_iso_datetime_to_sp_day("2026-03-17T15:00:00Z")
    assert day.isoformat() == "2026-03-17"


def test_parse_iso_datetime_to_sp_day_previous_day():
    # 01:30 UTC é 22:30 do dia anterior em São Paulo (UTC-3)
    day = parse_iso_datetime_to_sp_day("2026-03-17T01:30:00Z")
    assert day.isoformat() == "2026-03-16"