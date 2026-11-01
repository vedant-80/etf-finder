"""End-to-end cases on the real SEC snapshot: the reference tool, the scripted agent's tool calls and
the verdict, with no model. These are the runs the report cites; -v prints each case's name."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from helpers import failing, gold_answer, judge

from plugin.snapshot import load

GOLD = {
    "NVDA": "NVDA",
    "Nvidia": "NVDA",
    "nvda": "NVDA",
    "apple": "AAPL",
    "Microsoft": "MSFT",
    "brk.b": "BRK-B",
    "ExxonMobil": "XOM",  # SEC writes it as one word; "Exxon Mobil" finds nothing (README, Limitations)
}


@pytest.mark.parametrize(("query", "ticker"), GOLD.items(), ids=list(GOLD))
def test_gold_run_resolves_the_stock_and_holds_every_check(tmp_path: Path, query: str, ticker: str) -> None:
    answer = gold_answer(query, tmp_path)
    assert answer["stock"]["ticker"] == ticker
    assert len(answer["etfs"]) == min(20, len(load().holdings[ticker]))
    verdict = judge(query, answer, tmp_path)
    assert verdict["valid"] and verdict["score"] == 1.0, verdict["message"]


def test_nvidia_is_led_by_the_semiconductor_and_technology_etfs(tmp_path: Path) -> None:
    top = [etf["ticker"] for etf in gold_answer("NVDA", tmp_path)["etfs"][:6]]
    assert top[0] == "SMH" and {"VGT", "XLK"} <= set(top)


def test_an_unknown_company_is_not_found(tmp_path: Path) -> None:
    answer = gold_answer("Definitely Not A Company", tmp_path)
    assert answer == {"query": "Definitely Not A Company", "found": False, "stock": None, "as_of": "", "etfs": []}
    assert judge("Definitely Not A Company", answer, tmp_path)["valid"]


@pytest.mark.parametrize(
    ("name", "change", "fails"),
    [
        ("reversed", lambda a: a["etfs"].reverse(), {"order", "etfs-exact"}),
        ("top10-only", lambda a: a["etfs"].__delitem__(slice(10, None)), {"count", "none-missing"}),
        (
            "rounded-weights",
            lambda a: [e.update(weight_pct=f"{float(e['weight_pct']):.2f}") for e in a["etfs"]],
            {"well-formed"},
        ),
        ("fund-names-shortened", lambda a: [e.update(name=e["ticker"]) for e in a["etfs"]], {"etfs-exact"}),
    ],
)
def test_wrong_answers_for_nvidia_fail_their_check(tmp_path: Path, name: str, change, fails: set[str]) -> None:
    answer = copy.deepcopy(gold_answer("Nvidia", tmp_path))
    change(answer)
    verdict = judge("Nvidia", answer, tmp_path)
    assert not verdict["valid"] and fails <= set(failing(verdict)), (name, verdict["message"])
