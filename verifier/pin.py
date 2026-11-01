"""pin_holders, the answer key: the resolved stock matches the query, and its holders are well formed."""

from .checks import result
from .rules import holdings_problem, match_rank, query_problem


def verify_input(value):
    problem = query_problem(value.query)
    return result(problem is None, problem or "the query is valid")


def pin_problem(query, pin):
    """What is wrong with an answer key for ``query``, or None."""
    if pin is None:
        return "there is no answer key: NanoAgent pins pin_holders before the agent starts"
    if pin.query != query:
        return f"the answer key is for {pin.query!r}, not {query!r}"
    if pin.stock is None:
        return "the answer key found no stock but lists holders" if pin.holders else None
    if match_rank(query, pin.stock.ticker, pin.stock.name) is None:
        return f"the answer key's stock {pin.stock.ticker} ({pin.stock.name}) does not match {query!r}"
    if not pin.holders:
        return f"the answer key's stock {pin.stock.ticker} has no holders, but only held stocks are searchable"
    return holdings_problem(pin.holders, "answer-key holder")


def verify_output(input_value, output_value, workspace):
    problem = pin_problem(input_value.query, output_value)
    return result(problem is None, problem or "the answer key is well formed")
