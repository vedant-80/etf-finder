"""get_etf_holders and pin_holders: ranking, tie-breaks, the cut at 20 and the answer key."""

from __future__ import annotations

from pathlib import Path

import pytest

from contract import FindInput, HoldersInput
from plugin import get_etf_holders, pin_holders


def ranked(ticker: str, tmp_path: Path) -> list[tuple[str, str]]:
    return [(etf.ticker, etf.weight_pct) for etf in get_etf_holders(HoldersInput(ticker=ticker), tmp_path).etfs]


def test_holders_rank_by_weight_highest_first(mini, tmp_path: Path) -> None:
    assert ranked("FEW", tmp_path) == [("E01", "2.5000"), ("E02", "1.2500"), ("E03", "0.0100")]


def test_equal_weights_rank_alphabetically_by_etf_ticker(mini, tmp_path: Path) -> None:
    assert ranked("TIE", tmp_path) == [("E04", "3.3000"), ("E09", "3.3000"), ("E05", "0.1000")]


def test_more_than_twenty_holders_are_cut_to_twenty_and_counted(mini, tmp_path: Path) -> None:
    out = get_etf_holders(HoldersInput(ticker="WIDE"), tmp_path)
    assert out.total_holders == 25 and len(out.etfs) == 20
    # E20 and E21 tie at 6.0000 for ranks 20 and 21: E20 wins the tie on its ticker.
    assert [(etf.ticker, etf.weight_pct) for etf in out.etfs[-2:]] == [("E19", "7.0000"), ("E20", "6.0000")]


def test_exactly_twenty_holders_are_all_listed(mini, tmp_path: Path) -> None:
    out = get_etf_holders(HoldersInput(ticker="TWNY"), tmp_path)
    assert out.total_holders == 20 and len(out.etfs) == 20 and out.etfs[0].ticker == "E20"


def test_each_holder_carries_its_full_name(mini, tmp_path: Path) -> None:
    assert get_etf_holders(HoldersInput(ticker="BRK-B"), tmp_path).etfs[0].name == "Example Fund 07 ETF"


def test_an_unknown_ticker_is_refused_by_name(mini, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ZZZZ"):
        get_etf_holders(HoldersInput(ticker="ZZZZ"), tmp_path)


def test_the_answer_key_pins_every_holder_of_the_first_candidate(mini, tmp_path: Path) -> None:
    pin = pin_holders(FindInput(query="Alphabet"), tmp_path)
    assert pin.stock.ticker == "GOOG" and sorted(etf.ticker for etf in pin.holders) == ["E01", "E02"]
    assert len(pin_holders(FindInput(query="wide"), tmp_path).holders) == 25


def test_the_answer_key_for_an_unknown_query_has_no_stock(mini, tmp_path: Path) -> None:
    pin = pin_holders(FindInput(query="ZZZZ"), tmp_path)
    assert pin.stock is None and pin.holders == []
