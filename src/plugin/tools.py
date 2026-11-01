"""The three tools: each takes its contract input and the workspace (unused: they only read the
snapshot) and returns its contract output."""

from __future__ import annotations

from pathlib import Path

from contract import EtfHolding, FindInput, HoldersInput, HoldersOutput, PinOutput, SearchInput, SearchOutput, StockRef
from plugin.snapshot import TOP, load, ranked_holders, search


def search_stocks(given: SearchInput, workspace: Path) -> SearchOutput:
    candidates = [StockRef(ticker=ticker, name=name) for ticker, name in search(load(), given.query)]
    return SearchOutput(query=given.query, candidates=candidates)


def get_etf_holders(given: HoldersInput, workspace: Path) -> HoldersOutput:
    snapshot = load()
    if given.ticker not in snapshot.stocks:
        raise ValueError(
            f"{given.ticker!r} is not a stock any ETF in the universe holds: pass a ticker search_stocks gave"
        )
    holders = ranked_holders(snapshot, given.ticker)
    return HoldersOutput(
        stock=StockRef(ticker=given.ticker, name=snapshot.stocks[given.ticker]),
        as_of=snapshot.as_of,
        total_holders=len(holders),
        etfs=[EtfHolding(ticker=etf, name=name, weight_pct=weight) for etf, name, weight in holders[:TOP]],
    )


def pin_holders(given: FindInput, workspace: Path) -> PinOutput:
    """The answer key: the stock the query resolves to and every ETF holding it, unranked."""
    snapshot = load()
    found = search(snapshot, given.query)
    if not found:
        return PinOutput(query=given.query, stock=None, as_of=snapshot.as_of, holders=[])
    ticker, name = found[0]
    holders = [
        EtfHolding(ticker=etf, name=snapshot.etf_names[etf], weight_pct=weight)
        for etf, weight in snapshot.holdings[ticker]
    ]
    return PinOutput(query=given.query, stock=StockRef(ticker=ticker, name=name), as_of=snapshot.as_of, holders=holders)
