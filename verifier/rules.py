"""The task's rules, written again from the README for the verifier alone: it imports none of the
plugin's code, so a bug in a tool cannot hide itself by agreeing with its own checker."""

import re
from decimal import Decimal, InvalidOperation

TOP = 20
MAX_CANDIDATES = 5
MAX_QUERY = 100
TICKER = re.compile(r"[A-Z][A-Z0-9-]{0,9}")
WEIGHT = re.compile(r"\d{1,3}\.\d{4}")
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


def query_problem(query):
    if not query.strip():
        return "the query is blank"
    if len(query) > MAX_QUERY:
        return f"the query is {len(query)} characters, more than {MAX_QUERY}"
    return None


def ticker_problem(ticker):
    if not TICKER.fullmatch(ticker):
        return f"ticker {ticker!r} is not a ticker: upper-case letters, digits and dashes, starting with a letter, as search_stocks gives it"
    return None


def weight_of(text):
    """The weight as a Decimal in (0, 100] with exactly 4 decimals, or None."""
    if not isinstance(text, str) or not WEIGHT.fullmatch(text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if 0 < value <= 100 else None


def ticker_key(text):
    return re.sub(r"[./ ]", "-", text.strip().upper())


def name_words(text):
    words = re.sub(r"[^0-9A-Z]+", " ", text.upper().replace("&", " AND ")).split()
    while len(words) > 1 and words[-1] in SUFFIXES:
        words.pop()
    return tuple(words)


def match_rank(query, ticker, name):
    """1 exact ticker, 2 exact name, 3 name starts with the query's words, 4 name contains them; None: no match."""
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


def rank_key(holding):
    """Sort key of a well-formed holding: highest weight first, ties by ETF ticker."""
    return (-weight_of(holding.weight_pct), holding.ticker)


def holdings_problem(holdings, label):
    """What is malformed in a list of EtfHolding, or None: bad tickers, blank names, bad weights, duplicates."""
    seen = set()
    for position, holding in enumerate(holdings, 1):
        where = f"{label} #{position} ({holding.ticker})"
        if ticker_problem(holding.ticker):
            return f"{where}: {ticker_problem(holding.ticker)}"
        if not holding.name.strip():
            return f"{where} has a blank name"
        if weight_of(holding.weight_pct) is None:
            return f"{where} has weight {holding.weight_pct!r}, not a percentage in (0, 100] with 4 decimals"
        if holding.ticker in seen:
            return f"{where} is listed twice"
        seen.add(holding.ticker)
    return None


def unsorted_at(holdings):
    """The first position (1-based) whose holding should come before the one above it, or None."""
    for position in range(1, len(holdings)):
        if rank_key(holdings[position]) < rank_key(holdings[position - 1]):
            return position + 1
    return None


def plain(holding):
    return {"ticker": holding.ticker, "name": holding.name, "weight_pct": holding.weight_pct}
