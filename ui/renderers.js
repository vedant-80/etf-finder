// How this plugin's page draws its tasks' outputs: the find-etfs answer (a FindOutput) as a ranked
// table of ETFs with their weights, and a stock lookup (a SearchOutput) as its candidates. A
// find-etfs result ends with the verdict's checks.
import { dataTable, disclosure, h, statusPill } from "./kit/components.js";

/** The verdict's named checks, each with whether it held and, if not, why. */
function checks(verdict) {
  const entries = verdict?.details?.checks;
  if (!Array.isArray(entries)) return null;
  const failed = entries.filter((entry) => entry.ok === false).length;
  return disclosure(
    { summary: failed ? `${failed} of ${entries.length} checks fail` : `All ${entries.length} checks hold` },
    h(
      "ul",
      { class: "checks" },
      entries.map((entry) =>
        h(
          "li",
          {},
          statusPill(entry.ok === true ? "Holds" : entry.ok === false ? "Fails" : "Skipped", entry.ok === true ? "ok" : entry.ok === false ? "bad" : "neutral"),
          " ",
          entry.constraint,
          entry.message ? h("div", { class: "muted", text: entry.message }) : null,
        ),
      ),
    ),
  );
}

function findOutput(answer, { verdict }) {
  if (!answer.found) {
    return h("div", { class: "etf-answer" }, h("p", { text: `No stock held by an ETF in the universe matches "${answer.query}".` }), checks(verdict));
  }
  const rows = answer.etfs.map((etf, index) => ({ rank: index + 1, ...etf, weight: Number(etf.weight_pct) }));
  const table = dataTable({
    caption: `ETFs holding ${answer.stock.ticker}`,
    columns: [
      { key: "rank", label: "#", numeric: true },
      { key: "ticker", label: "ETF", primary: true },
      { key: "name", label: "Name" },
      { key: "weight", label: "Holding %", numeric: true, render: (row) => `${row.weight_pct}%` },
    ],
    rows,
    sort: { key: "rank", dir: "asc" },
    empty: "No ETF holds this stock.",
  });
  return h(
    "div",
    { class: "etf-answer" },
    h("h3", { text: `${answer.stock.ticker} · ${answer.stock.name}` }),
    h("p", { class: "muted", text: answer.as_of }),
    table.element,
    checks(verdict),
  );
}

function searchOutput(found) {
  if (!found.candidates.length) return h("p", { text: `Nothing matches "${found.query}".` });
  return h(
    "ol",
    { class: "candidates" },
    found.candidates.map((stock, index) => h("li", {}, h("strong", { text: stock.ticker }), ` ${stock.name}`, index === 0 ? [" ", statusPill("Used by find-etfs", "info")] : null)),
  );
}

export default { FindOutput: findOutput, SearchOutput: searchOutput };
