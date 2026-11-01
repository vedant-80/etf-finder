"""Run a find-etfs task the way NanoAgent does, with a script in place of the model: the reference
tool first, then the tool calls, each checked by verify_input and verify_output, then verify_task."""

from __future__ import annotations

import copy
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import FindInput, FindOutput, HoldersInput, SearchInput
from plugin import get_etf_holders, pin_holders, search_stocks


def call(tool: str, implementation, given_class, arguments: dict, workspace: Path):
    given = build_output(arguments, given_class)
    assert verifier.verify_input(tool, given)["valid"], verifier.verify_input(tool, given)
    made = implementation(given, workspace)
    verdict = verifier.verify_output(tool, given, made, str(workspace))
    assert verdict["valid"], verdict
    return made


def gold_answer(query: str, workspace: Path) -> dict:
    """The answer the task's instructions give: the first candidate's holders, copied unchanged."""
    found = call("search_stocks", search_stocks, SearchInput, {"query": query}, workspace)
    if not found.candidates:
        return {"query": query, "found": False, "stock": None, "as_of": "", "etfs": []}
    holders = call("get_etf_holders", get_etf_holders, HoldersInput, {"ticker": found.candidates[0].ticker}, workspace)
    return {
        "query": query,
        "found": True,
        "stock": plain_output(holders.stock),
        "as_of": holders.as_of,
        "etfs": plain_output(holders)["etfs"],
    }


def judge(query: str, answer: dict, workspace: Path) -> dict:
    """The verdict for ``answer`` to ``query``, against the pinned answer key."""
    arguments = build_output({"query": query}, FindInput)
    reference = call("pin_holders", pin_holders, FindInput, {"query": query}, workspace)
    output = build_output(answer, FindOutput)
    first = verifier.verify_task("find-etfs", arguments, output, reference, str(workspace))
    second = verifier.verify_task(
        "find-etfs", arguments, copy.deepcopy(output), copy.deepcopy(reference), str(workspace)
    )
    assert first == second, "the verdict must be deterministic"
    return first


def failing(verdict: dict) -> list[str]:
    return [entry["id"] for entry in verdict["details"]["checks"] if entry["ok"] is False]
