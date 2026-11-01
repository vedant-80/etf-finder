"""search_stocks (and the lookup-stock task, which is that one tool): the candidates follow the ranking rule."""

from .checks import result
from .rules import MAX_CANDIDATES, match_rank, query_problem, ticker_problem


def verify_input(value):
    problem = query_problem(value.query)
    return result(problem is None, problem or "the query is valid")


def candidates_problem(query, output):
    if output.query != query:
        return f"the output's query {output.query!r} is not the input's {query!r}"
    if len(output.candidates) > MAX_CANDIDATES:
        return f"{len(output.candidates)} candidates, more than {MAX_CANDIDATES}"
    previous, seen = None, set()
    for position, candidate in enumerate(output.candidates, 1):
        if ticker_problem(candidate.ticker):
            return f"candidate #{position}: {ticker_problem(candidate.ticker)}"
        if candidate.ticker in seen:
            return f"candidate #{position} ({candidate.ticker}) is listed twice"
        seen.add(candidate.ticker)
        rank = match_rank(query, candidate.ticker, candidate.name)
        if rank is None:
            return f"candidate #{position} ({candidate.ticker}, {candidate.name}) does not match {query!r}"
        if previous is not None and (rank, candidate.ticker) < previous:
            return f"candidate #{position} ({candidate.ticker}) is a better match than the one above it: out of order"
        previous = (rank, candidate.ticker)
    return None


def verify_output(input_value, output_value, workspace):
    problem = candidates_problem(input_value.query, output_value)
    return result(problem is None, problem or f"{len(output_value.candidates)} candidate(s), in rank order")


def verify_task(arguments, output, reference, workspace):
    return verify_output(arguments, output, workspace)
