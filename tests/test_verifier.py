"""The find-etfs verdict on the mini snapshot: one test per kind of answer the assignment names
(correct, incorrect, missing, malformed, boundary), each failing the check it should."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from helpers import failing, gold_answer, judge
from slimconfig import build_output

import verifier
from contract import FindInput, HoldersInput, HoldersOutput, PinOutput, SearchInput, SearchOutput


def mutated(query: str, tmp_path: Path, change) -> dict:
    answer = copy.deepcopy(gold_answer(query, tmp_path))
    change(answer)
    return judge(query, answer, tmp_path)


# Correct ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["WIDE", "TWNY", "FEW", "TIE", "Alphabet", "berkshire", "ZZZZ"])
def test_the_gold_answer_holds_every_check(mini, tmp_path: Path, query: str) -> None:
    verdict = judge(query, gold_answer(query, tmp_path), tmp_path)
    assert verdict["valid"] and verdict["score"] == 1.0, verdict["message"]
    assert all(entry["ok"] for entry in verdict["details"]["checks"])


# Incorrect --------------------------------------------------------------------------------------


def test_two_swapped_ranks_fail_order_and_exact(mini, tmp_path: Path) -> None:
    def swap(answer):
        answer["etfs"][0], answer["etfs"][1] = answer["etfs"][1], answer["etfs"][0]

    verdict = mutated("FEW", tmp_path, swap)
    assert failing(verdict) == ["order", "etfs-exact"]
    assert verdict["score"] == pytest.approx(1 / 3)


def test_a_weight_off_by_one_ten_thousandth_fails_exact(mini, tmp_path: Path) -> None:
    def nudge(answer):
        answer["etfs"][1]["weight_pct"] = "1.2501"

    verdict = mutated("FEW", tmp_path, nudge)
    assert failing(verdict) == ["etfs-exact"] and "1.2501" in verdict["message"]


def test_a_wrong_etf_name_fails_exact(mini, tmp_path: Path) -> None:
    def rename(answer):
        answer["etfs"][0]["name"] = "Example Fund 1 ETF"

    assert failing(mutated("FEW", tmp_path, rename)) == ["etfs-exact"]


def test_the_wrong_share_class_fails_the_stock_and_scores_zero(mini, tmp_path: Path) -> None:
    # Alphabet resolves to GOOG (first by ticker); answering with GOOGL's holders is wrong.
    answer = gold_answer("GOOGL", tmp_path) | {"query": "Alphabet"}
    verdict = judge("Alphabet", answer, tmp_path)
    assert "stock-resolved" in failing(verdict) and verdict["score"] == 0.0


def test_an_answer_for_another_query_fails_query(mini, tmp_path: Path) -> None:
    verdict = judge("FEW", gold_answer("FEW", tmp_path) | {"query": "few"}, tmp_path)
    assert failing(verdict) == ["query"] and verdict["score"] == 0.0


def test_an_etf_that_does_not_hold_the_stock_fails_no_extra(mini, tmp_path: Path) -> None:
    def replace(answer):
        answer["etfs"][2] = {"ticker": "E25", "name": "Example Fund 25 ETF", "weight_pct": "0.0100"}

    verdict = mutated("FEW", tmp_path, replace)
    assert {"etfs-exact", "no-extra", "none-missing"} <= set(failing(verdict))


def test_a_changed_as_of_fails_as_of(mini, tmp_path: Path) -> None:
    def date(answer):
        answer["as_of"] = "today"

    assert failing(mutated("FEW", tmp_path, date)) == ["as-of"]


# Missing ----------------------------------------------------------------------------------------


def test_nineteen_of_twenty_fails_count_and_none_missing(mini, tmp_path: Path) -> None:
    def drop_last(answer):
        answer["etfs"].pop()

    verdict = mutated("WIDE", tmp_path, drop_last)
    assert failing(verdict) == ["count", "etfs-exact", "none-missing"]
    assert verdict["score"] == pytest.approx(19 / 20)


def test_an_empty_list_when_etfs_hold_it_fails(mini, tmp_path: Path) -> None:
    def empty(answer):
        answer["etfs"] = []

    verdict = mutated("FEW", tmp_path, empty)
    assert {"count", "none-missing"} <= set(failing(verdict)) and verdict["score"] == 0.0


def test_saying_not_found_for_a_known_stock_fails_the_stock(mini, tmp_path: Path) -> None:
    answer = {"query": "FEW", "found": False, "stock": None, "as_of": "", "etfs": []}
    assert "stock-resolved" in failing(judge("FEW", answer, tmp_path))


# Malformed --------------------------------------------------------------------------------------


def test_twenty_one_etfs_fail_well_formed_and_count(mini, tmp_path: Path) -> None:
    def add(answer):
        answer["etfs"].append({"ticker": "E21", "name": "Example Fund 21 ETF", "weight_pct": "6.0000"})

    verdict = mutated("WIDE", tmp_path, add)
    assert {"well-formed", "count", "no-extra"} <= set(failing(verdict))


def test_a_duplicate_etf_fails_well_formed(mini, tmp_path: Path) -> None:
    def duplicate(answer):
        answer["etfs"][2] = answer["etfs"][1]

    assert "well-formed" in failing(mutated("FEW", tmp_path, duplicate))


@pytest.mark.parametrize("weight", ["abc", "2.5", "2.50000", "-1.0000", "0.0000", "101.0000", "1e2", ""])
def test_a_weight_that_is_not_a_4_decimal_percentage_is_malformed(mini, tmp_path: Path, weight: str) -> None:
    def spoil(answer):
        answer["etfs"][0]["weight_pct"] = weight

    verdict = mutated("FEW", tmp_path, spoil)
    assert "well-formed" in failing(verdict)
    order = next(entry for entry in verdict["details"]["checks"] if entry["id"] == "order")
    assert order["ok"] is None, "order is skipped, never a crash, on a malformed list"


@pytest.mark.parametrize("ticker", ["nvda$", "e01", "", "TOOLONGTICKER"])
def test_a_malformed_etf_ticker_fails_well_formed(mini, tmp_path: Path, ticker: str) -> None:
    def spoil(answer):
        answer["etfs"][0]["ticker"] = ticker

    assert "well-formed" in failing(mutated("FEW", tmp_path, spoil))


def test_a_value_of_the_wrong_type_is_refused_before_the_verifier() -> None:
    from slimconfig import build_output as build

    from contract import FindOutput

    with pytest.raises(ValueError):
        build({"query": "FEW", "found": "yes", "stock": None, "as_of": "", "etfs": []}, FindOutput)


@pytest.mark.parametrize(
    ("tool", "given_class", "value"),
    [
        ("search_stocks", SearchInput, {"query": "   "}),
        ("search_stocks", SearchInput, {"query": "x" * 101}),
        ("get_etf_holders", HoldersInput, {"ticker": "nvda"}),
        ("get_etf_holders", HoldersInput, {"ticker": "NVDA$"}),
        ("pin_holders", FindInput, {"query": ""}),
    ],
)
def test_malformed_tool_inputs_are_refused(tool: str, given_class, value: dict) -> None:
    assert verifier.verify_input(tool, build_output(value, given_class))["valid"] is False


# Boundary ---------------------------------------------------------------------------------------


def test_a_tie_at_ranks_20_and_21_keeps_the_alphabetically_first(mini, tmp_path: Path) -> None:
    def other_side_of_the_tie(answer):
        answer["etfs"][19] = {"ticker": "E21", "name": "Example Fund 21 ETF", "weight_pct": "6.0000"}

    verdict = mutated("WIDE", tmp_path, other_side_of_the_tie)
    assert {"etfs-exact", "no-extra", "none-missing"} <= set(failing(verdict))
    assert "order" not in failing(verdict), "the list is still sorted; it holds the wrong ETF of the tie"


def test_tied_weights_in_the_wrong_ticker_order_fail_order(mini, tmp_path: Path) -> None:
    def swap(answer):
        answer["etfs"][0], answer["etfs"][1] = answer["etfs"][1], answer["etfs"][0]

    assert "order" in failing(mutated("TIE", tmp_path, swap))


def test_a_stock_held_by_fewer_than_twenty_lists_them_all(mini, tmp_path: Path) -> None:
    assert len(gold_answer("berkshire", tmp_path)["etfs"]) == 1
    assert judge("berkshire", gold_answer("berkshire", tmp_path), tmp_path)["valid"]


def test_a_found_stock_for_an_unknown_query_fails(mini, tmp_path: Path) -> None:
    verdict = judge("ZZZZ", gold_answer("FEW", tmp_path) | {"query": "ZZZZ"}, tmp_path)
    assert {"stock-resolved", "count", "no-extra"} <= set(failing(verdict)) and verdict["score"] == 0.0


def test_not_found_needs_an_empty_as_of(mini, tmp_path: Path) -> None:
    answer = {"query": "ZZZZ", "found": False, "stock": None, "as_of": "2026", "etfs": []}
    assert failing(judge("ZZZZ", answer, tmp_path)) == ["as-of"]


# The answer key ---------------------------------------------------------------------------------


def test_no_answer_key_fails_first_and_scores_zero(mini, tmp_path: Path) -> None:
    arguments = build_output({"query": "FEW"}, FindInput)
    from contract import FindOutput

    output = build_output(gold_answer("FEW", tmp_path), FindOutput)
    verdict = verifier.verify_task("find-etfs", arguments, output, None, str(tmp_path))
    assert failing(verdict) == ["answer-key"] and verdict["score"] == 0.0


def test_an_answer_key_whose_stock_does_not_match_the_query_is_refused() -> None:
    pin = build_output(
        {
            "query": "FEW",
            "stock": {"ticker": "WIDE", "name": "WIDELY HELD CORP"},
            "as_of": "x",
            "holders": [{"ticker": "E01", "name": "n", "weight_pct": "1.0000"}],
        },
        PinOutput,
    )
    assert verifier.verify_output("pin_holders", build_output({"query": "FEW"}, FindInput), pin, "")["valid"] is False


# Tool outputs -----------------------------------------------------------------------------------


def test_search_candidates_out_of_rank_order_are_refused() -> None:
    out = build_output(
        {
            "query": "Apple",
            "candidates": [
                {"ticker": "APLE", "name": "Apple Hospitality REIT, Inc."},
                {"ticker": "AAPL", "name": "Apple Inc."},
            ],
        },
        SearchOutput,
    )
    verdict = verifier.verify_output("search_stocks", build_output({"query": "Apple"}, SearchInput), out, "")
    assert verdict["valid"] is False and "out of order" in verdict["message"]


def test_a_search_candidate_that_does_not_match_is_refused() -> None:
    out = build_output({"query": "Apple", "candidates": [{"ticker": "MSFT", "name": "MICROSOFT CORP"}]}, SearchOutput)
    assert (
        verifier.verify_output("search_stocks", build_output({"query": "Apple"}, SearchInput), out, "")["valid"]
        is False
    )


def test_holders_cut_short_of_twenty_are_refused() -> None:
    out = build_output(
        {
            "stock": {"ticker": "WIDE", "name": "W"},
            "as_of": "x",
            "total_holders": 25,
            "etfs": [{"ticker": "E01", "name": "n", "weight_pct": "25.0000"}],
        },
        HoldersOutput,
    )
    verdict = verifier.verify_output("get_etf_holders", build_output({"ticker": "WIDE"}, HoldersInput), out, "")
    assert verdict["valid"] is False and "20 must be" in verdict["message"]
