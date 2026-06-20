"""Unit tests for pure helpers (no I/O, no browser)."""

from __future__ import annotations

import pytest

from luckflow.core.utils import (
    balance_decreased,
    calculate_balance_difference,
    extract_balance_number,
    parse_proxy,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1.2.3.4:8080:user:pass", {"server": "http://1.2.3.4:8080", "username": "user", "password": "pass"}),
        ("1.2.3.4:8080", {"server": "http://1.2.3.4:8080"}),
        ("", None),
        ("nan", None),
        (None, None),
        ("garbage:with:three", None),
    ],
)
def test_parse_proxy(value, expected):
    assert parse_proxy(value) == expected


@pytest.mark.parametrize(
    "text,expected",
    [("≈$1,234.56", 1234.56), ("$0.10", 0.10), ("no number", 0.0), ("", 0.0)],
)
def test_extract_balance_number(text, expected):
    assert extract_balance_number(text) == expected


@pytest.mark.parametrize(
    "start,end,deposit,expected",
    [
        ("10.00", "12.50", 0.0, "+$2.50"),
        ("12,50", "10,00", 0.0, "-$2.50"),
        ("10.00", "10.00", 0.0, "$0.00"),
        ("10.00", "13.00", 1.0, "+$2.00"),  # deposit discounted
    ],
)
def test_calculate_balance_difference(start, end, deposit, expected):
    assert calculate_balance_difference(start, end, deposit) == expected


def test_balance_decreased():
    assert balance_decreased("12,00", "10,00") is True
    assert balance_decreased("10,00", "12,00") is False
    assert balance_decreased("10,00", "8,00", enabled=False) is False
