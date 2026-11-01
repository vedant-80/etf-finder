"""The find-etfs verdict: named checks, in order, comparing the submitted answer with the top 20 the
verifier ranks itself from the answer key's full, unranked holder list.

The verdict is valid only when every check holds. Any failure among GATES (the answer key, the query,
the stock) scores 0; otherwise the score is the share of ranks whose ticker, name and weight are exactly
right, out of the longer of the expected and the submitted list (1.0 when both are empty)."""

from .checks import constraint, first_failure, named, result
from .pin import pin_problem
from .rules import TOP, holdings_problem, plain, rank_key, unsorted_at

TEXT = {
    "answer-key": "The answer key is pinned for this query and well formed",
    "query": "The answer is for the task's query",
    "stock-resolved": "The answer names the stock the query resolves to, or says none was found",
    "well-formed": "Every listed ETF has a ticker, a name and a weight in (0, 100] with 4 decimals, once each, at most 20",
    "count": "The answer lists min(20, number of holders) ETFs",
    "order": "The ETFs are ranked by weight, highest first, ties alphabetically by ticker",
    "etfs-exact": "At each rank, the ETF's ticker, name and weight are exactly the expected ones",
    "no-extra": "No ETF outside the expected top 20 is listed",
    "none-missing": "Every ETF in the expected top 20 is listed",
    "as-of": "The answer states where and when the weights come from, as get_etf_holders gave it",
}
GATES = ("answer-key", "query", "stock-resolved")


def expected_top(pin):
    return sorted(pin.holders, key=rank_key)[:TOP] if pin.stock is not None else []


def verify_task(arguments, output, reference, workspace):
    entries = []

    def check(identifier, ok, expected=None, actual=None, message=""):
        entries.append(constraint(identifier, TEXT[identifier], ok, expected, actual, message))
        return ok

    problem = pin_problem(arguments.query, reference)
    if not check("answer-key", problem is None, message=problem or ""):
        return verdict(entries, 0.0)
    check(
        "query",
        output.query == arguments.query,
        arguments.query,
        output.query,
        f"the answer is for {output.query!r}, the task for {arguments.query!r}",
    )
    want_stock = None if reference.stock is None else {"ticker": reference.stock.ticker, "name": reference.stock.name}
    got_stock = None if output.stock is None else {"ticker": output.stock.ticker, "name": output.stock.name}
    resolved = output.found == (want_stock is not None) and got_stock == want_stock
    check(
        "stock-resolved",
        resolved,
        {"found": want_stock is not None, "stock": want_stock},
        {"found": output.found, "stock": got_stock},
        f"expected {want_stock['ticker'] if want_stock else 'no stock'}, got "
        f"{got_stock['ticker'] if got_stock else 'no stock'} with found={output.found}",
    )

    expected = expected_top(reference)
    malformed = holdings_problem(output.etfs, "ETF") or (
        f"{len(output.etfs)} ETFs listed, more than {TOP}" if len(output.etfs) > TOP else None
    )
    check("well-formed", malformed is None, message=malformed or "")
    check(
        "count",
        len(output.etfs) == len(expected),
        len(expected),
        len(output.etfs),
        f"{len(output.etfs)} ETFs listed; {len(reference.holders)} hold the stock, so {len(expected)} must be",
    )
    position = None if malformed else unsorted_at(output.etfs)
    check(
        "order",
        None if malformed else position is None,
        message=(
            "skipped: the list is malformed"
            if malformed
            else f"ETF #{position} ({output.etfs[position - 1].ticker}) ranks above #{position - 1} by weight, then ticker"
            if position
            else ""
        ),
    )
    wrong = [
        f"#{rank} expected {plain(want) if want else 'nothing'} got {plain(got) if got else 'nothing'}"
        for rank, (want, got) in enumerate(_pairs(expected, output.etfs), 1)
        if got is None or want is None or plain(want) != plain(got)
    ]
    correct = sum(1 for want, got in zip(expected, output.etfs) if plain(want) == plain(got))
    check("etfs-exact", not wrong, actual=f"{correct} of {len(expected)} ranks right", message=named(wrong))
    wanted, listed = [holding.ticker for holding in expected], [holding.ticker for holding in output.etfs]
    extra = [ticker for ticker in listed if ticker not in wanted]
    missing = [ticker for ticker in wanted if ticker not in listed]
    check("no-extra", not extra, [], extra, f"not in the expected top {TOP}: {named(extra)}")
    check("none-missing", not missing, [], missing, f"missing from the answer: {named(missing)}")
    want_as_of = reference.as_of if reference.stock is not None else ""
    check(
        "as-of",
        output.as_of == want_as_of,
        want_as_of,
        output.as_of,
        "as_of is not get_etf_holders' as_of unchanged" if want_as_of else "as_of must be empty when no stock is found",
    )

    gated = any(entry["ok"] is False for entry in entries if entry["id"] in GATES)
    longest = max(len(expected), len(output.etfs))
    score = 0.0 if gated else (correct / longest if longest else 1.0)
    return verdict(entries, score)


def _pairs(expected, listed):
    """(expected, listed) holdings rank by rank, None where one list is shorter."""
    for rank in range(max(len(expected), len(listed))):
        yield (expected[rank] if rank < len(expected) else None, listed[rank] if rank < len(listed) else None)


def verdict(entries, score):
    for entry in entries:
        if entry["ok"]:
            entry["message"] = ""
    failure = first_failure(entries)
    if failure is None:
        return result(True, f"all {len(entries)} checks hold", score=1.0, checks=entries)
    return result(False, failure, score=score, checks=entries)
