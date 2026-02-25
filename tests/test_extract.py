import pandas as pd

from src.extract import (
    parse_distance_km,
    build_member_lookup,
    find_account_id_by_name,
)


def test_parse_distance_km_with_comma():
    assert parse_distance_km("5,5") == 5.5 j


def test_parse_distance_km_with_dot():
    assert parse_distance_km("6.2") == 6.2


def test_parse_distance_km_invalid():
    assert parse_distance_km("abc") is None


def test_build_member_lookup():
    data = {
        "members": [
            {"id": 1, "full_name": "Alice"},
            {"id": 2, "full_name": "Bob"},
        ]
    }

    lookup = build_member_lookup(data)

    assert lookup[1] == "Alice"
    assert lookup[2] == "Bob"


def test_find_account_id_by_name_case_insensitive():
    lookup = {1: "Alice", 2: "Bob"}

    account_id = find_account_id_by_name(lookup, "alice")

    assert account_id == 1