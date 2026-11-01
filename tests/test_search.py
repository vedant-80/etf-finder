"""search_stocks: tickers, names, suffixes, ambiguity and the ranking rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract import SearchInput
from plugin import search_stocks


def tickers(query: str, tmp_path: Path) -> list[str]:
    return [stock.ticker for stock in search_stocks(SearchInput(query=query), tmp_path).candidates]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("WIDE", ["WIDE"]),  # exact ticker
        ("wide", ["WIDE"]),  # case does not matter
        ("  few ", ["FEW"]),  # nor surrounding spaces
        ("brk.b", ["BRK-B"]),  # a class after a dot or slash is SEC's dash
        ("BRK/B", ["BRK-B"]),
        ("Berkshire Hathaway", ["BRK-B"]),  # name without its suffix
        ("Berkshire", ["BRK-B"]),  # name prefix
        ("Hathaway", ["BRK-B"]),  # a run of the name's words
        ("Alphabet", ["GOOG", "GOOGL"]),  # two classes, same name: ties by ticker, GOOG first
        ("Alphabet Inc.", ["GOOG", "GOOGL"]),
        ("Apple", ["AAPL", "APLE"]),  # exact name (Apple Inc.) before a prefix (Apple Hospitality REIT)
        ("Holders", ["FEW", "TWNY"]),  # contained words only, ties by ticker
        ("ZZZZ", []),  # nothing matches
        ("Inc", []),  # a suffix alone is the name's whole first word nowhere
        ("H", []),  # one-letter name fragments match nothing
    ],
)
def test_search_ranks_candidates(mini, tmp_path: Path, query: str, expected: list[str]) -> None:
    assert tickers(query, tmp_path) == expected


def test_an_exact_ticker_beats_a_name_match(mini, tmp_path: Path) -> None:
    # "TIE" is the ticker of TIED WEIGHTS INC; no name equals "TIE", and the ticker comes first.
    assert tickers("tie", tmp_path)[0] == "TIE"


def test_search_returns_at_most_five(mini, tmp_path: Path) -> None:
    assert len(search_stocks(SearchInput(query="Inc"), tmp_path).candidates) <= 5
