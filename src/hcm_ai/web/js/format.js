// Pure formatting helpers (unit-tested with `node --test`).

const MONTH_RE = /^(\d{4})-(0[1-9]|1[0-2])$/;

export const fmtNum = (v) => (v === null || v === undefined ? "-" : new Intl.NumberFormat("en").format(v));

export const fmtPct = (v) => (v === null || v === undefined ? "-" : `${Number(v).toFixed(1)}%`);

export const fmtMoney = (v) =>
  v === null || v === undefined ? "-" : `PKR ${fmtNum(Math.round(v))}`;

export function monthLabel(ym) {
  const match = MONTH_RE.exec(ym ?? "");
  if (!match) return String(ym ?? "");
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1));
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
}

/** ym and the (count - 1) months before it, newest first. */
export function recentMonths(ym, count = 6) {
  const match = MONTH_RE.exec(ym ?? "");
  if (!match) return [];
  let year = Number(match[1]);
  let month = Number(match[2]);
  const out = [];
  for (let i = 0; i < count; i += 1) {
    out.push(`${year}-${String(month).padStart(2, "0")}`);
    month -= 1;
    if (month === 0) {
      month = 12;
      year -= 1;
    }
  }
  return out;
}

export function formatDay(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  if (!match) return String(iso ?? "");
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** Inclusive calendar days between two ISO dates, or null if invalid/reversed. */
export function inclusiveDays(startIso, endIso) {
  const a = Date.parse(`${startIso}T00:00:00Z`);
  const b = Date.parse(`${endIso}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  return Math.round((b - a) / 86_400_000) + 1;
}

export function parseRetryAfter(value, fallback = 60) {
  const seconds = Number.parseInt(value ?? "", 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : fallback;
}

export const plural = (n, word) => `${fmtNum(n)} ${word}${n === 1 ? "" : "s"}`;

export function capitalize(word) {
  return word ? word[0].toUpperCase() + word.slice(1) : "";
}
