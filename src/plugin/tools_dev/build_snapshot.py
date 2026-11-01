"""Build the frozen ETF holdings snapshot, src/plugin/data/snapshot.json.gz, from SEC data.

Dev-only: the plugin itself never touches the network. Run from the plugin root:

    SEC_USER_AGENT="etf-finder-build you@example.edu" uv run python src/plugin/tools_dev/build_snapshot.py 2026q3 /tmp/sec

It downloads (into the cache folder, never into the repository) the quarter's Form N-PORT data set
and SEC's two ticker files, then for each ETF in data/etf_universe.txt:

1. finds its SEC registration: a fund series in company_tickers_mf.json, or, for a unit investment
   trust such as SPY, its CIK in company_tickers.json;
2. takes that registration's N-PORT report with the latest REPORT_DATE in the quarter;
3. keeps its common-stock holdings (ASSET_CAT EC) valued in USD and names each by its CUSIP's
   ticker. Many funds (iShares among them) report only a CUSIP, so the CUSIP -> ticker map is
   built from the whole quarter's N-PORT data: every common-stock row that reports both a CUSIP
   and a ticker is a vote, tickers normalized (BRK/B, BRK.B -> BRK-B) and kept only when they are
   SEC-registered companies in company_tickers.json; a CUSIP's ticker is its majority vote, and a
   CUSIP whose top two tickers tie is left unmapped (and counted);
4. sums a stock's rows within the report and rounds its percentage of net assets to 4 decimals.

Every failure stops the build and names the ETF: no fallback, no silent skipping.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
UNIVERSE = DATA / "etf_universe.txt"
SNAPSHOT = DATA / "snapshot.json.gz"
SOURCE = DATA / "SOURCE.json"
NPORT_URL = "https://www.sec.gov/files/dera/data/form-n-port-data-sets/{quarter}_nport.zip"
FUNDS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
COMPANIES_URL = "https://www.sec.gov/files/company_tickers.json"
PLACES = Decimal("0.0001")
csv.field_size_limit(sys.maxsize)


def download(url: str, target: Path) -> Path:
    if target.is_file():
        return target
    agent = os.environ.get("SEC_USER_AGENT")
    if not agent or "@" not in agent:
        raise SystemExit("SEC_USER_AGENT must be set to a name and contact email; SEC refuses requests without one")
    request = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(request) as response, open(target.with_suffix(".part"), "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    target.with_suffix(".part").rename(target)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_ticker(ticker: str) -> str:
    return re.sub(r"[./ ]", "-", ticker.strip().upper())


def read_universe() -> list[tuple[str, str | None]]:
    """(ticker, display name or None) for each line of etf_universe.txt; a name follows a |."""
    entries, seen = [], set()
    for line in UNIVERSE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ticker, _, name = (part.strip() for part in line.partition("|"))
        if ticker in seen:
            raise SystemExit(f"{ticker} is listed twice in {UNIVERSE.name}")
        seen.add(ticker)
        entries.append((ticker, name or None))
    return entries


def table(archive: zipfile.ZipFile, name: str):
    with archive.open(f"{name}.tsv") as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""), delimiter="\t")


def report_date(text: str) -> datetime:
    return datetime.strptime(text, "%d-%b-%Y")


def main(quarter: str, cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    nport = download(NPORT_URL.format(quarter=quarter), cache / f"{quarter}_nport.zip")
    funds_file = download(FUNDS_URL, cache / "company_tickers_mf.json")
    companies_file = download(COMPANIES_URL, cache / "company_tickers.json")

    series_of = {row[3]: row[1] for row in json.loads(funds_file.read_text())["data"]}
    companies = {normalize_ticker(row["ticker"]): row for row in json.loads(companies_file.read_text()).values()}
    universe = read_universe()
    registration = {}  # etf ticker -> ("series", id) or ("cik", 10-digit cik)
    for ticker, _ in universe:
        if ticker in series_of:
            registration[ticker] = ("series", series_of[ticker])
        elif ticker in companies:
            registration[ticker] = ("cik", str(companies[ticker]["cik_str"]).zfill(10))
        else:
            raise SystemExit(
                f"{ticker} is neither a fund series in company_tickers_mf.json nor a CIK in company_tickers.json"
            )

    archive = zipfile.ZipFile(nport)
    submissions = {row["ACCESSION_NUMBER"]: row for row in table(archive, "SUBMISSION")}
    cik_of = {row["ACCESSION_NUMBER"]: row["CIK"] for row in table(archive, "REGISTRANT")}
    # The latest report of each registration in the quarter: (report date, filing date, accession).
    latest: dict[tuple[str, str], tuple[datetime, datetime, str, str]] = {}
    for row in table(archive, "FUND_REPORTED_INFO"):
        accession = row["ACCESSION_NUMBER"]
        submission = submissions[accession]
        key = (
            report_date(submission["REPORT_DATE"]),
            report_date(submission["FILING_DATE"]),
            accession,
            row["SERIES_NAME"],
        )
        for kind, value in (("series", row["SERIES_ID"]), ("cik", cik_of[accession])):
            if value and ((kind, value) not in latest or key > latest[(kind, value)]):
                latest[(kind, value)] = key
    series_of_cik = defaultdict(set)
    for row in table(archive, "FUND_REPORTED_INFO"):
        series_of_cik[cik_of[row["ACCESSION_NUMBER"]]].add(row["SERIES_ID"])
    for ticker, (kind, value) in registration.items():
        if kind == "cik" and len(series_of_cik[value]) > 1:
            raise SystemExit(
                f"{ticker} is matched by CIK {value}, which reports {len(series_of_cik[value])} series: ambiguous"
            )
    reports = {}
    for ticker, _ in universe:
        if registration[ticker] not in latest:
            raise SystemExit(
                f"{ticker} ({registration[ticker][0]} {registration[ticker][1]}) has no N-PORT report in {quarter}"
            )
        reports[ticker] = latest[registration[ticker]]
    etfs_of_accession = defaultdict(list)
    for ticker, report in reports.items():
        etfs_of_accession[report[2]].append(ticker)

    # Pass 1: every reported ticker that is an SEC-registered company, by holding id.
    ticker_of_holding: dict[int, str] = {}
    for row in table(archive, "IDENTIFIERS"):
        if row["IDENTIFIER_TICKER"]:
            ticker = normalize_ticker(row["IDENTIFIER_TICKER"])
            if ticker in companies:
                ticker_of_holding[int(row["HOLDING_ID"])] = ticker
    # Pass 2: CUSIP -> ticker votes from every fund's common stock, and the chosen reports' rows.
    votes: dict[str, Counter] = defaultdict(Counter)
    chosen: list[tuple[str, str, Decimal]] = []  # (accession, cusip, percentage)
    counts = Counter()
    for row in table(archive, "FUND_REPORTED_HOLDING"):
        if row["ASSET_CAT"] != "EC":
            if row["ACCESSION_NUMBER"] in etfs_of_accession:
                counts["dropped: not common stock"] += 1
            continue
        cusip = row["ISSUER_CUSIP"].strip().upper()
        valid_cusip = re.fullmatch(r"[0-9A-Z]{8}[0-9]", cusip) and cusip != "000000000"
        if valid_cusip and int(row["HOLDING_ID"]) in ticker_of_holding:
            votes[cusip][ticker_of_holding[int(row["HOLDING_ID"])]] += 1
        if row["ACCESSION_NUMBER"] not in etfs_of_accession:
            continue
        if row["CURRENCY_CODE"] != "USD" or not row["PERCENTAGE"] or not valid_cusip:
            counts["dropped: common stock not in USD or without a CUSIP"] += 1
            continue
        chosen.append((row["ACCESSION_NUMBER"], cusip, Decimal(row["PERCENTAGE"])))
    ticker_of_cusip, tied = {}, 0
    for cusip, tally in votes.items():
        ranked = tally.most_common(2)
        if len(ranked) == 2 and ranked[0][1] == ranked[1][1]:
            tied += 1
            continue
        ticker_of_cusip[cusip] = ranked[0][0]
    counts["CUSIPs mapped to a ticker"] = len(ticker_of_cusip)
    counts["CUSIPs left unmapped: tied vote"] = tied
    weights: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))  # accession -> stock -> pct
    for accession, cusip, percentage in chosen:
        if cusip in ticker_of_cusip:
            weights[accession][ticker_of_cusip[cusip]] += percentage
            counts["kept: common stock rows matched to a ticker"] += 1
        else:
            counts["dropped: CUSIP with no SEC-registered ticker"] += 1

    etfs, holdings = [], defaultdict(list)
    for ticker, name in universe:
        when, _, accession, series_name = reports[ticker]
        etfs.append(
            {
                "ticker": ticker,
                "name": name or series_name,
                "report_date": when.date().isoformat(),
                "accession": accession,
            }
        )
        for stock, percentage in weights[accession].items():
            rounded = percentage.quantize(PLACES, rounding=ROUND_HALF_UP)
            if rounded > 0:
                holdings[stock].append([ticker, str(rounded)])
        if not weights[accession]:
            raise SystemExit(f"{ticker} ({series_name}) has no US common stock holdings: not an equity ETF")
    stocks = [{"ticker": ticker, "name": companies[ticker]["title"]} for ticker in sorted(holdings)]
    snapshot = {
        "quarter": quarter,
        "etfs": etfs,
        "stocks": stocks,
        "holdings": {stock: sorted(rows) for stock, rows in sorted(holdings.items())},
    }
    payload = json.dumps(snapshot, separators=(",", ":"), sort_keys=True).encode()
    SNAPSHOT.write_bytes(gzip.compress(payload, mtime=0))
    source = {
        "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quarter": quarter,
        "inputs": {
            NPORT_URL.format(quarter=quarter): sha256(nport),
            FUNDS_URL: sha256(funds_file),
            COMPANIES_URL: sha256(companies_file),
        },
        "outputs": {SNAPSHOT.name: sha256(SNAPSHOT), UNIVERSE.name: sha256(UNIVERSE)},
        "counts": {**counts, "etfs": len(etfs), "stocks": len(stocks)},
        "report_dates": dict(sorted(Counter(etf["report_date"] for etf in etfs).items())),
    }
    SOURCE.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    unnamed = [
        f"{etf['ticker']}: {etf['name']}"
        for etf in etfs
        if "ETF" not in etf["name"].upper() and "TRUST" not in etf["name"].upper()
    ]
    print(json.dumps(source["counts"], indent=2))
    print(f"snapshot: {SNAPSHOT.stat().st_size / 1e6:.2f} MB")
    if unnamed:
        print("Series names that may not be the ETF's own name (give one after a | in etf_universe.txt):")
        print("\n".join(unnamed))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_snapshot.py <quarter, e.g. 2026q3> <cache folder>")
    main(sys.argv[1], Path(sys.argv[2]))
