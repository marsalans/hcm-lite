import assert from "node:assert/strict";
import { test } from "node:test";

import {
  capitalize,
  fmtMoney,
  fmtNum,
  fmtPct,
  formatDay,
  inclusiveDays,
  monthLabel,
  parseRetryAfter,
  plural,
  recentMonths,
} from "../src/hcm_ai/web/js/format.js";

test("percent and number formatting, with a dash for missing values", () => {
  assert.equal(fmtPct(83.333), "83.3%");
  assert.equal(fmtPct(0), "0.0%");
  assert.equal(fmtPct(null), "-");
  assert.equal(fmtPct(undefined), "-");
  assert.equal(fmtNum(1234567), "1,234,567");
  assert.equal(fmtMoney(1234567.4), "PKR 1,234,567");
  assert.equal(fmtMoney(null), "-");
});

test("month helpers", () => {
  assert.equal(monthLabel("2026-10"), "October 2026");
  assert.equal(monthLabel("garbage"), "garbage");
  assert.deepEqual(recentMonths("2026-02", 4), ["2026-02", "2026-01", "2025-12", "2025-11"]);
  assert.deepEqual(recentMonths("bad", 3), []);
  assert.equal(recentMonths("2026-10").length, 6);
});

test("dates", () => {
  assert.equal(formatDay("2026-10-26"), "26 Oct 2026");
  assert.equal(formatDay("nope"), "nope");
  assert.equal(inclusiveDays("2026-10-26", "2026-10-27"), 2);
  assert.equal(inclusiveDays("2026-10-26", "2026-10-26"), 1);
  assert.equal(inclusiveDays("2026-10-27", "2026-10-26"), null);
  assert.equal(inclusiveDays("", "2026-10-26"), null);
});

test("Retry-After parsing falls back to 60 seconds", () => {
  assert.equal(parseRetryAfter("30"), 30);
  assert.equal(parseRetryAfter("abc"), 60);
  assert.equal(parseRetryAfter(null), 60);
  assert.equal(parseRetryAfter("0"), 60);
});

test("capitalize", () => {
  assert.equal(capitalize("casual"), "Casual");
  assert.equal(capitalize(""), "");
});

test("plural", () => {
  assert.equal(plural(1, "absent day"), "1 absent day");
  assert.equal(plural(0, "absent day"), "0 absent days");
  assert.equal(plural(12, "late day"), "12 late days");
});
