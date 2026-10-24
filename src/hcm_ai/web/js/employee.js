// Employee home: own balances/attendance/payslip, and the smart leave form.
// The AI only pre-fills the form. Nothing is saved until the user presses Confirm (and in this
// demo Confirm is not persisted: the leave module isn't connected).

import { api, describeError, ApiError } from "./api.js";
import { h, setChildren } from "./dom.js";
import { capitalize, fmtMoney, fmtNum, fmtPct, formatDay, inclusiveDays, monthLabel } from "./format.js";
import { aiLabel, card, loading, notice, skeletonLines, startCountdown } from "./ui.js";

const LEAVE_TYPES = ["annual", "sick", "casual", "unpaid"];

export function mountEmployee(root) {
  const stats = h("div", { class: "kpis", "aria-live": "polite" });
  root.append(
    h("div", { class: "page-head" }, h("h1", { text: "My dashboard" })),
    stats,
    smartLeaveCard(),
  );
  loadStats();

  async function loadStats() {
    setChildren(stats, ...Array.from({ length: 4 }, () => h("div", { class: "kpi" }, skeletonLines(2))));
    try {
      const d = await api("/dashboard/me");
      const bucket = (name, b) => kpi(`${capitalize(name)} leave left`, `${b.remaining} of ${b.quota}`, `${b.used} used in ${d.leave.year}`);
      setChildren(
        stats,
        bucket("annual", d.leave.annual),
        bucket("sick", d.leave.sick),
        bucket("casual", d.leave.casual),
        kpi("My attendance rate", fmtPct(d.attendance.attendance_rate_pct), `${monthLabel(d.month)} · ${fmtNum(d.attendance.late)} late, ${fmtNum(d.attendance.absent)} absent`),
        kpi("Latest net pay", d.payslip ? fmtMoney(d.payslip.total_net) : "-", d.payslip ? `${monthLabel(d.payslip.month)} · gross ${fmtMoney(d.payslip.total_gross)}` : "No payslip yet"),
      );
    } catch (err) {
      setChildren(stats, notice("error", describeError(err), " ", h("button", { class: "btn link", type: "button", onClick: loadStats }, "Retry")));
    }
  }
}

function kpi(label, value, hint) {
  return h("div", { class: "kpi" }, h("span", { class: "kpi-label", text: label }), h("span", { class: "kpi-value", text: value }), hint ? h("span", { class: "kpi-hint", text: hint }) : null);
}

function smartLeaveCard() {
  let cancelCountdown = null;
  const sentence = h("textarea", {
    id: "leave-text",
    rows: "2",
    maxlength: "500",
    placeholder: "e.g. I need next Monday and Tuesday off for my sister's wedding",
  });
  const fillBtn = h("button", { class: "btn primary", type: "button", onClick: () => fill() }, "Fill form with AI");
  const status = h("div", { class: "leave-status", "aria-live": "polite" });

  const type = h("select", { id: "leave-type", required: true }, h("option", { value: "", text: "Choose type" }), LEAVE_TYPES.map((t) => h("option", { value: t, text: capitalize(t) })));
  const start = h("input", { id: "leave-start", type: "date", required: true });
  const end = h("input", { id: "leave-end", type: "date", required: true });
  const reason = h("input", { id: "leave-reason", type: "text", maxlength: "200", placeholder: "Optional" });
  const fields = [type, start, end, reason];
  for (const f of fields) f.addEventListener("input", () => f.classList.remove("prefilled"));

  const result = h("div", { class: "leave-result", "aria-live": "polite" });
  const form = h(
    "form",
    { class: "leave-form", novalidate: true, onSubmit: (e) => { e.preventDefault(); confirm(); } },
    h("label", { for: "leave-type" }, "Leave type", type),
    h("label", { for: "leave-start" }, "From", start),
    h("label", { for: "leave-end" }, "To", end),
    h("label", { for: "leave-reason", class: "wide" }, "Reason", reason),
    h("div", { class: "form-actions wide" }, h("button", { class: "btn", type: "submit" }, "Confirm request"), h("button", { class: "btn link", type: "button", onClick: () => clearForm() }, "Clear")),
  );

  function clearForm() {
    for (const f of fields) {
      f.value = "";
      f.classList.remove("prefilled");
    }
    setChildren(result);
  }

  async function fill() {
    const text = sentence.value.trim();
    if (!text) {
      setChildren(status, notice("warn", "Type what you need first, in your own words."));
      sentence.focus();
      return;
    }
    fillBtn.disabled = true;
    setChildren(result);
    setChildren(status, loading("Reading your request..."));
    try {
      const res = await api("/ai/smart-leave", { method: "POST", body: { text } });
      if (res.success && res.data) {
        type.value = res.data.type;
        start.value = res.data.start;
        end.value = res.data.end;
        reason.value = res.data.reason ?? "";
        for (const f of fields) f.classList.add("prefilled");
        setChildren(status, notice("info", aiLabel(), " Filled in from your sentence. Please check every field, then confirm."));
        type.focus();
      } else {
        clearForm();
        setChildren(status, notice("warn", "I couldn't work that out. Please fill in the form yourself."));
        type.focus();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        cancelCountdown?.();
        fillBtn.disabled = true;
        cancelCountdown = startCountdown(
          err.retryAfter ?? 60,
          (left) => setChildren(status, notice("warn", `You've reached the hourly AI limit. You can still fill the form by hand, or try again in ${left} s.`)),
          () => {
            setChildren(status);
            fillBtn.disabled = false;
          },
        );
        return;
      }
      setChildren(status, notice("error", describeError(err), " You can fill the form by hand."));
    }
    fillBtn.disabled = false;
  }

  function confirm() {
    const missing = !type.value || !start.value || !end.value;
    const days = inclusiveDays(start.value, end.value);
    if (missing) {
      setChildren(result, notice("warn", "Please choose a type and both dates."));
    } else if (days === null) {
      setChildren(result, notice("warn", "The end date can't be before the start date."));
    } else {
      setChildren(
        result,
        notice("ok", h("strong", { text: "Request ready. " }), `${capitalize(type.value)} leave, ${formatDay(start.value)} to ${formatDay(end.value)} (${days} calendar day${days === 1 ? "" : "s"}). `, h("em", { text: "Demo only: not saved, because the leave module isn't connected." })),
      );
    }
  }

  return card(
    "Smart leave",
    {},
    h("label", { for: "leave-text", class: "muted" }, "Describe your leave in your own words"),
    sentence,
    h("div", { class: "form-actions" }, fillBtn),
    status,
    form,
    result,
  );
}
