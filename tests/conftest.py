"""A small hand-made snapshot whose answers are known, and helpers that run the real tools on it."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from plugin import snapshot as snapshot_module
from plugin import tools

# 25 ETFs, E01 ... E25.
ETFS = [
    {"ticker": f"E{n:02d}", "name": f"Example Fund {n:02d} ETF", "report_date": "2026-06-30", "accession": f"A{n}"}
    for n in range(1, 26)
]
STOCKS = {
    "WIDE": "WIDELY HELD CORP",  # 25 holders, a weight tie at ranks 20 and 21
    "TWNY": "TWENTY HOLDERS INC",  # exactly 20 holders
    "FEW": "FEW HOLDERS INC",  # 3 holders
    "TIE": "TIED WEIGHTS INC",  # 3 holders, the top two tied
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "BRK-B": "BERKSHIRE HATHAWAY INC",
    "AAPL": "Apple Inc.",
    "APLE": "Apple Hospitality REIT, Inc.",
}


def wide_weights() -> list[list[str]]:
    # E01 holds the most (25.0000), each next ETF 1 less; E20 and E21 are tied at 6.0000.
    rows = []
    for n in range(1, 26):
        weight = 26 - n if n != 21 else 6
        rows.append([f"E{n:02d}", f"{weight}.0000"])
    return rows


HOLDINGS = {
    "WIDE": wide_weights(),
    "TWNY": [[f"E{n:02d}", f"{n}.5000"] for n in range(1, 21)],
    "FEW": [["E03", "0.0100"], ["E01", "2.5000"], ["E02", "1.2500"]],
    "TIE": [["E09", "3.3000"], ["E04", "3.3000"], ["E05", "0.1000"]],
    "GOOG": [["E01", "3.0000"], ["E02", "2.0000"]],
    "GOOGL": [["E01", "4.0000"], ["E03", "1.0000"]],
    "BRK-B": [["E07", "1.7000"]],
    "AAPL": [["E01", "7.0000"], ["E05", "6.0000"]],
    "APLE": [["E06", "0.0500"]],
}


@pytest.fixture
def mini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> snapshot_module.Snapshot:
    """Every tool reads the mini snapshot instead of the real one."""
    data = {
        "quarter": "2026q3",
        "etfs": ETFS,
        "stocks": [{"ticker": ticker, "name": name} for ticker, name in sorted(STOCKS.items())],
        "holdings": HOLDINGS,
    }
    path = tmp_path / "mini.json.gz"
    path.write_bytes(gzip.compress(json.dumps(data).encode()))
    loaded = snapshot_module.load.__wrapped__(path)
    monkeypatch.setattr(tools, "load", lambda: loaded)
    return loaded
