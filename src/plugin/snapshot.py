"""The frozen SEC N-PORT snapshot (data/snapshot.json.gz) and the two lookups every tool shares:
resolving a query to stocks, and ranking a stock's ETF holders."""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent / "data" / "snapshot.json.gz"
TOP = 20  # holders a stock's answer lists
MAX_CANDIDATES = 5
# Words a company name ends with that a person leaves out: "NVIDIA CORP" is "Nvidia".
SUFFIXES = frozenset(
    [
        "INC",
        "INCORPORATED",
        "CORP",
        "CORPORATION",
        "CO",
        "COMPANY",
        "LTD",
        "LIMITED",
        "PLC",
        "LLC",
        "LP",
        "NV",
        "SA",
        "AG",
        "SE",
        "HOLDINGS",
        "HLDGS",
        "GROUP",
        "THE",
        "CLASS",
        "CL",
        "A",
        "B",
        "C",
        "DE",
        "DEL",
        "NEW",
    ]
)


@dataclass(frozen=True)
class Snapshot:
    quarter: str
    etf_names: dict[str, str]  # etf ticker -> full name
    report_dates: tuple[str, ...]  # every ETF's report date, sorted
    stocks: dict[str, str]  # stock ticker -> company name
    holdings: dict[str, list[tuple[str, str]]]  # stock ticker -> [(etf ticker, weight_pct)]

    @property
    def as_of(self) -> str:
        return f"SEC N-PORT {self.quarter}: each ETF's latest report, {self.report_dates[0]} to {self.report_dates[-1]}"


@cache
def load(path: Path = SNAPSHOT) -> Snapshot:
    data = json.loads(gzip.decompress(path.read_bytes()))
    return Snapshot(
        quarter=data["quarter"],
        etf_names={etf["ticker"]: etf["name"] for etf in data["etfs"]},
        report_dates=tuple(sorted(etf["report_date"] for etf in data["etfs"])),
        stocks={stock["ticker"]: stock["name"] for stock in data["stocks"]},
        holdings={stock: [(etf, weight) for etf, weight in rows] for stock, rows in data["holdings"].items()},
    )


def ticker_key(text: str) -> str:
    """A ticker as SEC writes it: upper case, a class after a dash (brk.b, BRK/B -> BRK-B)."""
    return re.sub(r"[./ ]", "-", text.strip().upper())


def name_words(text: str) -> tuple[str, ...]:
    """A name's words, upper case, punctuation dropped (& kept as AND), trailing suffixes stripped."""
    words = re.sub(r"[^0-9A-Z]+", " ", text.upper().replace("&", " AND ")).split()
    while len(words) > 1 and words[-1] in SUFFIXES:
        words.pop()
    return tuple(words)


def match_rank(query: str, ticker: str, name: str) -> int | None:
    """1 exact ticker, 2 exact name, 3 name starts with the query's words, 4 name contains them as a run of
    words; None when the stock does not match. Ranks 3 and 4 need a query of at least 2 characters."""
    if ticker_key(query) == ticker:
        return 1
    wanted, words = name_words(query), name_words(name)
    if not wanted:
        return None
    if wanted == words:
        return 2
    if len("".join(wanted)) < 2:
        return None
    if words[: len(wanted)] == wanted:
        return 3
    if any(words[start : start + len(wanted)] == wanted for start in range(1, len(words))):
        return 4
    return None


def search(snapshot: Snapshot, query: str) -> list[tuple[str, str]]:
    """The best (ticker, name) matches for ``query``, at most MAX_CANDIDATES, best first, ties by ticker."""
    ranked = []
    for ticker, name in snapshot.stocks.items():
        rank = match_rank(query, ticker, name)
        if rank is not None:
            ranked.append((rank, ticker, name))
    return [(ticker, name) for _, ticker, name in sorted(ranked)[:MAX_CANDIDATES]]


def ranked_holders(snapshot: Snapshot, ticker: str) -> list[tuple[str, str, str]]:
    """Every (etf ticker, etf name, weight_pct) holding ``ticker``, highest weight first, ties by ETF ticker."""
    rows = snapshot.holdings[ticker]
    return [
        (etf, snapshot.etf_names[etf], weight)
        for etf, weight in sorted(rows, key=lambda row: (-Decimal(row[1]), row[0]))
    ]
