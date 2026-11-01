"""get_etf_holders: the top holders, ranked, with valid weights and a consistent count."""

from .checks import result
from .rules import TOP, holdings_problem, ticker_problem, unsorted_at


def verify_input(value):
    problem = ticker_problem(value.ticker)
    return result(problem is None, problem or "the ticker is valid")


def verify_output(input_value, output_value, workspace):
    if output_value.stock.ticker != input_value.ticker:
        return result(False, f"the output is for {output_value.stock.ticker}, not the requested {input_value.ticker}")
    problem = holdings_problem(output_value.etfs, "holder")
    if problem:
        return result(False, problem)
    expected = min(TOP, output_value.total_holders)
    if len(output_value.etfs) != expected:
        return result(
            False,
            f"{len(output_value.etfs)} holders listed; {output_value.total_holders} hold it, so {expected} must be",
        )
    position = unsorted_at(output_value.etfs)
    if position:
        return result(False, f"holder #{position} ({output_value.etfs[position - 1].ticker}) is out of order")
    return result(True, f"the top {expected} of {output_value.total_holders} holders, ranked")
