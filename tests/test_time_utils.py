from datetime import date

from src.time_utils import is_weekend
from src.holidays import national_holidays_2026
from src.time_utils import is_ignored_day


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