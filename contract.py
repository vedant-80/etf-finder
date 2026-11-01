"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    SEARCH_STOCKS = "search_stocks"
    GET_ETF_HOLDERS = "get_etf_holders"
    PIN_HOLDERS = "pin_holders"


class Task(Enum):
    FIND_ETFS = "find-etfs"
    LOOKUP_STOCK = "lookup-stock"


QUERY = "A stock's ticker or company name, as the person typed it, e.g. NVDA or Nvidia"
TICKER = "A stock ticker as search_stocks gives it, e.g. NVDA or BRK-B"
WEIGHT = (
    "The stock's share of the ETF's net assets in percent, exactly 4 decimals, as text, e.g. \"7.5170\" "
    "(N-PORT's percentage, summed over the ETF's lots of the stock, rounded half up): copy it unchanged"
)
AS_OF = "Where the weights come from and their dates, e.g. SEC N-PORT 2026q3: each ETF's latest report, 2026-05-31 to 2026-07-31"


@dataclass
class StockRef(Output):
    ticker: Annotated[str, TICKER]
    name: Annotated[str, "The company's name as SEC lists it, e.g. NVIDIA CORP"]


@dataclass
class EtfHolding(Output):
    ticker: Annotated[str, "The ETF's ticker, e.g. SMH"]
    name: Annotated[str, "The ETF's full name, e.g. VanEck Semiconductor ETF"]
    weight_pct: Annotated[str, WEIGHT]


@dataclass
class SearchInput(Output):
    query: Annotated[str, QUERY]


@dataclass
class SearchOutput(Output):
    query: Annotated[str, "The query, as given"]
    candidates: Annotated[
        list[StockRef],
        "Up to 5 stocks held by at least one ETF, best match first: an exact ticker, then an exact company name "
        "(ignoring Inc, Corp, Co and the like), then a name starting with the query's words, then a name containing "
        "them; ties alphabetically by ticker. [] when nothing matches",
    ]


@dataclass
class HoldersInput(Output):
    ticker: Annotated[str, TICKER]


@dataclass
class HoldersOutput(Output):
    stock: Annotated[StockRef, "The stock"]
    as_of: Annotated[str, AS_OF]
    total_holders: Annotated[int, "How many ETFs in the universe hold the stock, before the cut to 20"]
    etfs: Annotated[
        list[EtfHolding],
        "The top 20 holders (all of them when fewer hold it), highest weight first, ties alphabetically by ETF ticker",
    ]


@dataclass
class FindInput(Output):
    query: Annotated[str, QUERY]


@dataclass
class PinOutput(Output):
    query: Annotated[str, "The query, as given"]
    stock: Annotated[
        StockRef | None, "The stock the query resolves to (search_stocks' first candidate); null when none"
    ]
    as_of: Annotated[str, AS_OF]
    holders: Annotated[list[EtfHolding], "Every ETF that holds the stock, in no particular order"]


@dataclass
class FindOutput(Output):
    query: Annotated[str, "The task's query, exactly as given"]
    found: Annotated[bool, "Whether search_stocks found a stock for the query"]
    stock: Annotated[StockRef | None, "The stock: search_stocks' first candidate, as given; null when not found"]
    as_of: Annotated[str, "get_etf_holders' as_of, unchanged; empty when not found"]
    etfs: Annotated[
        list[EtfHolding],
        "get_etf_holders' etfs, unchanged and in its order: up to 20, highest weight first; [] when not found",
    ]


TOOLS = {
    Tool.SEARCH_STOCKS: (SearchInput, SearchOutput),
    Tool.GET_ETF_HOLDERS: (HoldersInput, HoldersOutput),
    Tool.PIN_HOLDERS: (FindInput, PinOutput),
}
TASKS = {
    Task.FIND_ETFS: (FindInput, FindOutput),
    Task.LOOKUP_STOCK: (SearchInput, SearchOutput),
}
