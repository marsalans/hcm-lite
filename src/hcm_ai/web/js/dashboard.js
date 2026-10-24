// Admin / HR dashboard: filters, KPI cards, charts and the AI "Summarize" button.

import { api, describeError, ApiError } from "./api.js";
import { barList } from "./charts.js";
import { h, setChildren } from "./dom.js";
import { capitalize, fmtMoney, fmtNum, fmtPct, monthLabel, plural, recentMonths } from "./format.js";
import { renderRich } from "./render.js";
import { aiLabel, card, emptyState, loading, notice, skeletonLines, startCountdown } from "./ui.js";

export function mountDashboard(root) {
  const state = { month: null, deptId: "", data: null, summary: { status: "idle" }, cancel: null };

  const monthSelect = h("select", { id: "f-month", onChange: () => onFilter() });
  const deptSelect = h("select", { id: "f-dept", onChange: () => onFilter() }, h("option", { value: "", text: "All departments" }));
  const filters = h(
    "form",
    { class: "filters", onSubmit: (e) => e.preventDefault(), "aria-label": "Dashboard filters" },
    h("label", { for: "f-month" }, "Month", monthSelect),
    h("label", { for: "f-dept" }, "Department", deptSelect),
  );
  const kpiGrid = h("div", { class: "kpis", "aria-live": "polite" });
  const charts = h("div", { class: "grid-2" });
  const summaryBody = h("div", { class: "summary-body", "aria-live": "polite" });
  const summarizeBtn = h("button", { class: "btn primary", type: "button", onClick: () => summarize() }, "Summarize");

  root.append(
    h("div", { class: "page-head" }, h("h1", { text: "Dashboard" }), filters),
    card("AI summary", { actions: summarizeBtn, className: "summary" }, summaryBody),
    kpiGrid,
    charts,
  );

  function onFilter() {
    state.month = monthSelect.value;
    state.deptId = deptSelect.value;
    state.summary = { status: "idle" };
    state.cancel?.();
    renderSummary();
    load();
  }

  async function loadDepartments() {
    try {
      const list = await api("/dashboard/departments");
      for (const d of list) deptSelect.append(h("option", { value: String(d.id), text: d.name }));
    } catch {
      /* the filter just stays on "All departments" */
    }
  }

  function setMonthOptions(current) {
    setChildren(
      monthSelect,
      recentMonths(current, 6).map((m) => h("option", { value: m, text: monthLabel(m) })),
    );
    monthSelect.value = state.month ?? current;
  }

  async function load() {
    setChildren(kpiGrid, ...Array.from({ length: 6 }, () => h("div", { class: "kpi" }, skeletonLines(2))));
    setChildren(charts);
    summarizeBtn.disabled = true;
    const params = new URLSearchParams();
    if (state.month) params.set("month", state.month);
    if (state.deptId) params.set("dept_id", state.deptId);
    try {
      state.data = await api(`/dashboard?${params}`);
      const { kpis } = state.data;
      if (!state.month) {
        state.month = kpis.month;
        setMonthOptions(kpis.month);
      }
      renderKpis(kpis);
      renderCharts(kpis);
      summarizeBtn.disabled = false;
    } catch (err) {
      state.data = null;
      setChildren(
        kpiGrid,
        notice("error", describeError(err), " ", h("button", { class: "btn link", type: "button", onClick: load }, "Retry")),
      );
    }
  }

  function kpi(label, value, hint) {
    return h("div", { class: "kpi" }, h("span", { class: "kpi-label", text: label }), h("span", { class: "kpi-value", text: value }), hint ? h("span", { class: "kpi-hint", text: hint }) : null);
  }

  function renderKpis(k) {
    setChildren(
      kpiGrid,
      kpi("Active headcount", fmtNum(k.headcount), k.department),
      kpi("Attendance rate", fmtPct(k.attendance_rate_pct), monthLabel(k.month)),
      kpi("Late %", fmtPct(k.late_pct), plural(k.late_days, "late day")),
      kpi("Absenteeism", fmtPct(k.absenteeism_pct), plural(k.absent_days, "absent day")),
      kpi("Pending leave requests", fmtNum(k.pending_leave_requests), `${plural(k.approved_leave_days_year, "approved day")} this year`),
      kpi("Payroll net", k.payroll ? fmtMoney(k.payroll.net) : "-", k.payroll ? `Gross ${fmtMoney(k.payroll.gross)}` : "No payroll for this month"),
    );
  }

  function renderCharts(k) {
    const types = Object.entries(k.leave_days_by_type_year ?? {}).map(([t, d]) => ({
      label: capitalize(t),
      value: d,
      display: `${d} d`,
    }));
    setChildren(
      charts,
      card("Headcount by department", {}, barList(k.by_department.map((d) => ({ label: d.name, value: d.headcount, display: String(d.headcount) })), { ariaLabel: "Headcount by department" })),
      card("Attendance rate by department", {}, barList(k.by_department.map((d) => ({ label: d.name, value: d.attendance_rate_pct, display: fmtPct(d.attendance_rate_pct) })), { max: 100, ariaLabel: "Attendance rate by department", empty: "No attendance yet for this selection." })),
      card("Approved leave days by type (this year)", {}, types.some((t) => t.value > 0) ? barList(types, { ariaLabel: "Approved leave days by type" }) : emptyState("No approved leave yet")),
      card("Top late-comers", {}, k.top_late_comers.length ? barList(k.top_late_comers.map((r) => ({ label: r.name, value: r.late_days, display: `${r.late_days} days` })), { ariaLabel: "Top late-comers" }) : emptyState("Nobody was late", "No late arrivals in this selection.")),
    );
  }

  function renderSummary() {
    const s = state.summary;
    if (s.status === "idle") {
      setChildren(summaryBody, h("p", { class: "muted", text: "Get 3-5 insights based only on the numbers shown below." }));
    } else if (s.status === "loading") {
      setChildren(summaryBody, loading("Writing summary..."), skeletonLines(3));
    } else if (s.status === "ok") {
      setChildren(
        summaryBody,
        renderRich(s.text),
        h("p", { class: "meta" }, aiLabel(), ` Based on ${monthLabel(s.month)} · ${s.department}`),
      );
    } else if (s.status === "limit") {
      setChildren(summaryBody, notice("warn", s.message));
    } else {
      setChildren(
        summaryBody,
        notice("error", s.message, " ", h("button", { class: "btn link", type: "button", onClick: summarize }, "Try again")),
      );
    }
  }

  async function summarize() {
    if (!state.data || state.summary.status === "loading") return;
    const { kpis } = state.data; // exactly what is on screen
    state.summary = { status: "loading" };
    summarizeBtn.disabled = true;
    renderSummary();
    try {
      const res = await api("/ai/summarize", { method: "POST", body: { kpis } });
      state.summary = res.success
        ? { status: "ok", text: res.summary, month: kpis.month, department: kpis.department }
        : { status: "error", message: "Couldn't write a summary right now." };
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        state.cancel?.();
        state.cancel = startCountdown(
          err.retryAfter ?? 60,
          (left) => {
            state.summary = { status: "limit", message: `You've reached the hourly AI limit. Try again in ${left} s.` };
            renderSummary();
          },
          () => {
            state.summary = { status: "idle" };
            summarizeBtn.disabled = false;
            renderSummary();
          },
        );
        return;
      }
      state.summary = { status: "error", message: describeError(err) };
    }
    summarizeBtn.disabled = false;
    renderSummary();
  }

  renderSummary();
  loadDepartments();
  load();
}
