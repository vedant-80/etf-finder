# ETF Finder

A `nanoagent.plugin/v0001` plugin. Give it a stock's ticker or company name (`NVDA`, `nvda`,
`Nvidia`) and its agent lists up to 20 ETFs that hold the stock, ranked by holding percentage
(the share of the ETF's net assets the stock makes up), each with its ticker, full name and weight:

| # | ETF | Name | Holding % |
|---|---|---|---|
| 1 | SMH | VanEck Semiconductor ETF | 17.5486 |
| 2 | FTEC | Fidelity MSCI Information Technology Index ETF | 17.0945 |
| 3 | VGT | Vanguard Information Technology ETF | 16.8215 |
| … | | | |

The holdings are a frozen snapshot of SEC Form N-PORT filings for 280 large US-listed equity
ETFs, shipped in the plugin, so every answer is exact and every run can be reproduced offline.

## Tools

| Tool | Does | Code |
|---|---|---|
| `search_stocks` | Up to 5 stocks a query matches, best first: an exact ticker, then an exact company name (ignoring trailing Inc, Corp, Co, Holdings and the like), then a name that starts with the query's words, then one that contains them; ties alphabetically by ticker. Only stocks some ETF holds are searchable | `src/plugin/tools.py`, `src/plugin/snapshot.py` |
| `get_etf_holders` | A stock's top 20 ETF holders, highest weight first, ties alphabetically by ETF ticker, with how many ETFs hold it in all and the data's dates | `src/plugin/tools.py` |
| `pin_holders` | The answer key: the stock a query resolves to (`search_stocks`' first candidate) and every ETF holding it, unranked | `src/plugin/tools.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `find-etfs` | Lists up to 20 ETFs holding the stock a query names, ranked by weight | `agent`, with `search_stocks` and `get_etf_holders`; reference `pin_holders` |
| `lookup-stock` | Shows which stocks a query matches, best first | `tool` (`search_stocks`) |

The `find-etfs` agent makes at most three tool calls: `search_stocks` with the query, then
`get_etf_holders` with the first candidate's ticker, then `submit` with the holders unchanged. If
nothing matches it submits `found: false`. The tool ranks, because the hosted model's reply is
capped at 2,048 tokens; the agent resolves the query, picks the stock and copies the answer exactly.

## Ground truth

Before the agent starts, NanoAgent runs `pin_holders` with the task's query and pins its output.
The verifier never trusts that key's order: it ranks the full holder list itself (weight
descending, then ETF ticker), takes the top 20 and compares the answer with them.

The data comes from three SEC files, recorded with their sha256 in `src/plugin/data/SOURCE.json`:

- **[Form N-PORT data set](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets)
  2026q3**, every registered fund's portfolio holdings. Each ETF's weights are from its latest
  report in the quarter (report dates 2026-05-31 to 2026-07-31; `as_of` names the range).
  `PERCENTAGE` is the holding's value as a percent of the fund's net assets.
- **`company_tickers_mf.json`**, which maps an ETF's ticker to its fund series. SPY, DIA and MDY are
  unit investment trusts with no series; they are matched by their trust's CIK, and the build checks
  that CIK reports a single series.
- **`company_tickers.json`**, SEC-registered companies' tickers and names.

`src/plugin/tools_dev/build_snapshot.py` builds `src/plugin/data/snapshot.json.gz`:

1. Each ticker in `src/plugin/data/etf_universe.txt` is mapped to its SEC registration. An ETF whose
   series name is not its own name (Vanguard's ETFs are share classes of an index fund) gets its
   name after a `|` in that file.
2. From each ETF's report it keeps common stock (`ASSET_CAT` EC) valued in USD.
3. Many funds, iShares among them, report a CUSIP but no ticker. So a CUSIP → ticker map is built
   from the whole quarter: every common-stock row of every fund that reports both is a vote, and a
   CUSIP's ticker is the majority. Tickers are written SEC's way (`BRK/B`, `BRK.B` → `BRK-B`) and
   kept only when they are SEC-registered companies. A CUSIP whose vote ties is left out.
4. A stock's rows within one report are summed and rounded to 4 decimals, half up.

The build stops and names the ETF on any failure: a ticker with no registration, no report in the
quarter, or no US common stock. It never skips one silently. `SOURCE.json` counts what was kept and
dropped.

## Checks

`verify_task` for `find-etfs` returns every check below in order with its expected and actual
values (the page shows them under the answer). The verdict is valid only when all hold. A failure
of `answer-key`, `query` or `stock-resolved` scores 0; otherwise the score is the share of ranks
exactly right out of the longer of the expected and submitted lists.

| Check | Holds when |
|---|---|
| `answer-key` | The pinned key is for this query, its stock matches the query by the search rule, and its holders are well formed |
| `query` | The answer's query is the task's |
| `stock-resolved` | `found` and `stock` are the key's (the first candidate), or `found: false` and no stock when nothing matches |
| `well-formed` | Every ETF has a valid ticker, a name and a weight in (0, 100] with exactly 4 decimals, once each, at most 20 |
| `count` | The answer lists min(20, number of holders) ETFs |
| `order` | Weight descending, ties by ETF ticker (skipped when the list is malformed) |
| `etfs-exact` | At each rank the ticker, name and weight equal the expected ones; the message names each wrong rank |
| `no-extra` | No ETF outside the expected top 20 is listed |
| `none-missing` | Every ETF in the expected top 20 is listed |
| `as-of` | `as_of` is the key's, or empty when nothing was found |

Each tool call is checked too: a blank or over-long query, or a malformed ticker, is refused;
`search_stocks`' candidates must each match the query and be in rank order; `get_etf_holders`
must list min(20, total) holders, sorted, with valid weights. The verifier re-implements the
matching and ranking rules (`verifier/rules.py`) and imports none of the plugin's code.

## Limitations

- **Quarterly, lagged data.** N-PORT holdings are public about 60 days after each report, and each
  ETF's weights are from its own latest report date, so ETFs in one answer can differ by a month or two.
- **A curated universe.** "All ETFs" means the 280 ETFs in `etf_universe.txt`, not every US ETF.
- **US-listed common stock only.** Holdings valued in other currencies, and CUSIPs that no fund
  reported with a ticker that quarter, are dropped (`SOURCE.json` counts them).
- **Rule-based search.** Names match whole words after SEC's spelling: `Exxon Mobil` finds nothing
  because SEC lists `ExxonMobil Holdings Corp`; `Facebook` does not find META. `lookup-stock` shows
  what a query matches.
- **One share class per query.** `Alphabet` resolves to GOOG, the first of GOOG and GOOGL by ticker;
  ask for `GOOGL` to get that class.
- **The tool ranks.** The agent is judged on resolving and copying, not on sorting hundreds of
  weights, which does not fit the hosted model's budget.

Data: U.S. Securities and Exchange Commission, Form N-PORT data sets (public domain).

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no network), tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs (none)
├── src/plugin/      # the MCP server (__main__.py), the tools (tools.py), the snapshot and ranking
│                    #   (snapshot.py), data/ (snapshot, SOURCE.json, the ETF universe) and
│                    #   tools_dev/build_snapshot.py, which rebuilds the snapshot from SEC
├── tests/           # offline tests: a hand-made mini snapshot for edge cases, and end-to-end
│                    #   cases on the real snapshot
├── ui/              # how the page draws the outputs and the verdict's checks
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: one module per tool, the task's checks in task.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest -v          # offline; no model and no network
uv run ruff check .
```

The tests replay each task the way NanoAgent runs it, with a script in place of the model:
`pin_holders` first, then `search_stocks` and `get_etf_holders`, each call checked by
`verify_input` and `verify_output`, then `verify_task` on the submitted answer (run twice, to show
the verdict is deterministic). `tests/test_verifier.py` covers correct, incorrect, missing,
malformed and boundary answers on a hand-made snapshot; `tests/test_cases.py` runs real queries
(`NVDA`, `Nvidia`, `apple`, `brk.b`, an unknown name) and wrong answers on the real snapshot.

Rebuild the snapshot (downloads about 460 MB into the cache folder, never into the repository;
SEC requires a contact email in the User-Agent):

```bash
SEC_USER_AGENT="etf-finder-build you@example.edu" uv run python src/plugin/tools_dev/build_snapshot.py 2026q3 /tmp/sec
```

Publishing checks every plugin rule: push the plugin to a public GitHub repository and submit it to
the RUSH Lab marketplace.
