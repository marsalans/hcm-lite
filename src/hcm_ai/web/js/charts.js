import { h } from "./dom.js";
import { emptyState } from "./ui.js";

/**
 * Horizontal bar list. rows: [{label, value, display?}]. Widths use CSSOM (allowed by a strict
 * CSP, unlike style attributes).
 */
export function barList(rows, { max = null, ariaLabel, empty = "No data for this selection." } = {}) {
  const usable = rows.filter((r) => r.value !== null && r.value !== undefined);
  if (usable.length === 0) return emptyState(empty);
  const top = max ?? Math.max(...usable.map((r) => r.value), 1);
  return h(
    "ul",
    { class: "bars", "aria-label": ariaLabel },
    usable.map((row) => {
      const fill = h("span", { class: "bar-fill" });
      fill.style.width = `${Math.max(2, Math.min(100, (row.value / top) * 100))}%`;
      return h(
        "li",
        { class: "bar-row" },
        h("span", { class: "bar-label", text: row.label }),
        h("span", { class: "bar-track", "aria-hidden": "true" }, fill),
        h("span", { class: "bar-value", text: row.display ?? String(row.value) }),
      );
    }),
  );
}
