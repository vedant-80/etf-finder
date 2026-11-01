"""The shipped snapshot is the one SOURCE.json records, and holds every ETF of the universe."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from plugin.snapshot import SNAPSHOT, load

DATA = SNAPSHOT.parent


def universe() -> list[str]:
    lines = (DATA / "etf_universe.txt").read_text(encoding="utf-8").splitlines()
    return [line.partition("|")[0].strip() for line in lines if line.strip() and not line.startswith("#")]


def test_the_data_files_are_the_ones_source_json_records() -> None:
    source = json.loads((DATA / "SOURCE.json").read_text(encoding="utf-8"))
    for name, digest in source["outputs"].items():
        assert hashlib.sha256(Path(DATA / name).read_bytes()).hexdigest() == digest, name


def test_every_universe_etf_is_in_the_snapshot_once() -> None:
    assert sorted(load().etf_names) == sorted(universe())
    assert len(universe()) == len(set(universe()))


def test_every_holding_is_a_known_etf_with_a_4_decimal_weight() -> None:
    snapshot = load()
    for stock, rows in snapshot.holdings.items():
        assert stock in snapshot.stocks
        assert len({etf for etf, _ in rows}) == len(rows), stock
        for etf, weight in rows:
            assert etf in snapshot.etf_names
            assert Decimal(weight).as_tuple().exponent == -4 and 0 < Decimal(weight) <= 100


def test_the_snapshot_is_small_enough_to_publish() -> None:
    # The marketplace refuses a repository archive over 25 MB.
    assert SNAPSHOT.stat().st_size < 5_000_000
