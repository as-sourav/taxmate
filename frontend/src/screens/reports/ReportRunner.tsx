/**
 * Query-report runner — Frappe Desk layout: page head, page-form filters,
 * scrollable datatable, footer. SPA routes only. Callers: App.tsx /reports/:report
 * (Route path="/reports/:report"). User: reports UI like Frappe with horizontal slider.
 *
 * Phone (≤760px): period chips stay visible; dates / links / toggles move into
 * the same bottom sheet pattern list screens use (FilterBar / .lm-sheet).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import {
  GL_CATEGORIES,
  PERIODICITIES,
  bookFilters,
  chipRange,
  isRunnableReport,
  reportBlurbKey,
  reportCaps,
  type Periodicity,
} from "../../lib/bookReports";
import { useSession } from "../../lib/session";
import { useDoc } from "../../lib/resource";
import { useListParams } from "../../lib/list";
import { money, toIsoDate } from "../../lib/format";
import { useLang } from "../../lib/i18n";
import { useIsPhone } from "../../lib/useMedia";
import { t } from "../../i18n/strings";
import { Empty, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { LinkFilter, SearchFilter } from "../../components/filters";
import ReportDataTable, { type ReportCol } from "./ReportDataTable";
import "../../styles/list-mobile.css";
import "./reports.css";

type Col = ReportCol;
type Row = Record<string, unknown>;
type Payload = { result?: Row[]; columns?: Col[]; report_label?: string };
type Fy = { year_start_date?: string; year_end_date?: string };
type Chip = "month" | "quarter" | "ytd" | "fy";

const HIDDEN = new Set([
  "indent", "parent_account", "parent_section", "warn", "has_value",
  "account_currency", "currency_symbol",
]);

const CAT_LABEL: Record<string, string> = {
  "Categorize by Voucher (Consolidated)": "rpt.cat.consolidated",
  "Categorize by Voucher": "rpt.cat.voucher",
  "Categorize by Account": "rpt.cat.account",
  "Categorize by Party": "rpt.cat.party",
};

const fill = (s: string, vars: Record<string, string | number>) =>
  Object.entries(vars).reduce((out, [k, v]) => out.replaceAll(`{${k}}`, String(v)), s);

function yearStart(iso?: string): string {
  const d = iso || toIsoDate(new Date());
  return `${d.slice(0, 4)}-01-01`;
}

function isMoney(col: Col): boolean {
  return col.fieldtype === "Currency" || col.fieldtype === "Float" || col.fieldtype === "Int";
}

/** Pull a finite amount from Frappe-formatted currency text (`د.إ 1,234.50`, `AED 9.00`). */
function parseFormattedMoney(s: string): number | null {
  const m = s.match(/-?[\d]{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?/);
  if (!m) return null;
  const n = parseFloat(m[0].replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

/**
 * Money cells show numerals only — currency lives once in the footer.
 * UAE VAT 201 (and similar) return `frappe.format` strings; prefer `raw_*`
 * when present, else parse the decorated string.
 */

/** ERPNext wraps total lines in quotes, which break in RTL. */
function unquote(s: string): string {
  const t = s.trim();
  if (t.length >= 2 && t.startsWith("'") && t.endsWith("'")) return t.slice(1, -1);
  return t;
}

/**
 * `account` stays the document id (`Revenue - XSm`) so a row can still
 * open General Ledger. `account_label` is that id's translated heading.
 * `acc_name` is the Account Name column. `account_name` can be
 * `1000 - Revenue`, so it is not used as the visible name.
 */
function accountCell(row: Row, field: string): string | null {
  if (field === "acc_name") {
    return typeof row.acc_name === "string" && row.acc_name.trim() ? unquote(row.acc_name) : null;
  }
  if (field !== "account") return null;
  if (typeof row.account_label === "string" && row.account_label.trim()) return unquote(row.account_label);
  return typeof row.account === "string" && row.account.trim() ? unquote(row.account) : null;
}

function cell(row: Row, col: Col): string {
  const field = col.fieldname || "";
  const named = accountCell(row, field);
  if (named != null && named !== "") return named;
  const v = row[field];
  if (v == null || v === "") return "—";
  if (typeof v === "number") return isMoney(col) ? money(v) : String(v);
  if (!isMoney(col)) return String(v);

  const raw = row[`raw_${field}`];
  if (typeof raw === "number" && Number.isFinite(raw)) return money(raw);

  if (typeof v === "string") {
    const trimmed = v.trim();
    if (trimmed === "-" || trimmed === "—") return "—";
    if (/^[-\d.,\s]+$/.test(trimmed)) return money(trimmed);
    const parsed = parseFormattedMoney(trimmed);
    if (parsed != null) return money(parsed);
    return trimmed;
  }
  return money(Number(v));
}

function spaRouteForVoucher(voucherType: unknown, voucherNo: unknown): string | null {
  const vt = String(voucherType || "");
  const n = String(voucherNo || "");
  if (!n) return null;
  if (vt === "Payment Entry") return `/payments/${encodeURIComponent(n)}`;
  if (vt === "Journal Entry") return `/journals/${encodeURIComponent(n)}`;
  if (vt === "Sales Invoice") return `/invoices/${encodeURIComponent(n)}`;
  if (vt === "Purchase Invoice") return `/purchase-invoices/${encodeURIComponent(n)}`;
  if (vt === "Purchase Receipt") return `/purchase-receipts/${encodeURIComponent(n)}`;
  if (vt === "Delivery Note") return `/delivery-notes/${encodeURIComponent(n)}`;
  return null;
}

function usedColumns(cols: Col[], rows: Row[]): Col[] {
  return cols.filter((c) => {
    if (!c.fieldname || HIDDEN.has(c.fieldname)) return false;
    return rows.some((r) => {
      const v = r[c.fieldname!];
      return v != null && v !== "";
    });
  });
}

function exportCsv(name: string, cols: Col[], rows: Row[]): void {
  const esc = (s: string) => `"${s.replace(/"/g, "\"\"")}"`;
  const lines = [
    cols.map((c) => esc(c.label || c.fieldname || "")).join(","),
    ...rows.map((r) => cols.map((c) => esc(cell(r, c))).join(",")),
  ];
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function Check({ on, label, onChange }: { on: boolean; label: string; onChange: () => void }) {
  return (
    <label className="rpt-check">
      <input type="checkbox" checked={on} onChange={onChange} />
      {label}
    </label>
  );
}

export default function ReportRunner() {
  const { report = "" } = useParams();
  const name = decodeURIComponent(report);
  const nav = useNavigate();
  const session = useSession();
  const { lang } = useLang();
  const phone = useIsPhone();
  const { get, set, setMany } = useListParams(20);
  const today = session.today || toIsoDate(new Date());
  const company = session.company;
  const caps = reportCaps(name);
  const allowed = isRunnableReport(name);
  const [find, setFind] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const filterBtnRef = useRef<HTMLButtonElement | null>(null);

  const defaults = useFrappeGetCall<{ message: { fiscal_year?: string } }>(
    METHOD.getDefaults,
    { company },
    company ? `defaults-${company}` : null,
  );
  const fiscalYear = defaults.data?.message?.fiscal_year;
  const fy = useDoc<Fy>("Fiscal Year", fiscalYear, fiscalYear ? `fy-${fiscalYear}` : null);

  const fromDate = get("from") || fy.data?.year_start_date || yearStart(today);
  const toDate = get("to") || today;
  const periodicity = (PERIODICITIES as readonly string[]).includes(get("p"))
    ? (get("p") as Periodicity)
    : "Monthly";
  const costCenter = get("cc");
  const account = get("account");
  const warehouse = get("wh");
  const itemCode = get("item");
  const partyType = get("ptype") || (caps.party === "typed" ? "" : caps.party || "");
  const party = get("party");
  const voucherNo = get("vn");
  const categorizeBy = get("cat") || "Categorize by Voucher (Consolidated)";
  const showZeros = get("zeros") === "1";
  const accumulated = get("acc") === "0" ? false : get("acc") === "1" ? true : undefined;
  const showGroups = get("groups") !== "0";
  const status = get("status");
  const sla = get("sla");
  const electSbr = get("sbr") === "1";
  const electQfzp = get("qfzp") === "1";

  const needsFy = name === "Trial Balance" || name === "Profit and Loss Statement"
    || name === "Balance Sheet" || name === "Cash Flow";
  const paused = !session.user || !company || !allowed || (needsFy && !fiscalYear);

  const filters = useMemo(() => {
    if (!company) return {};
    return bookFilters(name, {
      company, fiscalYear, fromDate, toDate, periodicity, costCenter, account,
      partyType, party, voucherNo, categorizeBy, showZeros, accumulated, showGroups,
      status, sla, electSbr, electQfzp, warehouse, itemCode,
    });
  }, [
    name, company, fiscalYear, fromDate, toDate, periodicity, costCenter, account,
    partyType, party, voucherNo, categorizeBy, showZeros, accumulated, showGroups,
    status, sla, electSbr, electQfzp, warehouse, itemCode,
  ]);

  const run = useFrappeGetCall<{ message: Payload }>(
    METHOD.runReport,
    { report_name: name, filters },
    paused ? null : `rpt-${lang}-${name}-${JSON.stringify(filters)}`,
  );

  const columns = useMemo(
    () => usedColumns((run.data?.message?.columns ?? []).filter((c) => c.fieldname), run.data?.message?.result ?? []),
    [run.data],
  );
  const rows = useMemo(
    () => (run.data?.message?.result ?? []).filter((r) => r && typeof r === "object" && !Array.isArray(r)),
    [run.data],
  );
  const q = find.trim().toLowerCase();
  const shown = useMemo(() => {
    if (!q) return rows;
    return rows.filter((r) => columns.some((c) => cell(r, c).toLowerCase().includes(q)));
  }, [rows, columns, q]);

  const blurbKey = reportBlurbKey(name);
  const companyFilters = company ? [["company", "=", company]] : undefined;
  const activeChip = (["month", "quarter", "ytd", "fy"] as const).find((k) => {
    const next = chipRange(k, today, fy.data?.year_start_date, fy.data?.year_end_date);
    return next.from === fromDate && next.to === toDate;
  });
  const hasToggles = caps.accumulated || caps.zeros || caps.groups || caps.ctElections;

  /** Sheet badge: URL-set extras (not period chips / grain). */
  const sheetApplied = useMemo(() => {
    let n = 0;
    if (caps.dates && (get("from") || get("to"))) n += 1;
    if (caps.costCenter && costCenter) n += 1;
    if (caps.account && account) n += 1;
    if (caps.warehouse && warehouse) n += 1;
    if (caps.itemCode && itemCode) n += 1;
    if (caps.party === "typed" && partyType) n += 1;
    if (caps.party && party) n += 1;
    if (caps.voucher && voucherNo) n += 1;
    if (caps.categorize && categorizeBy !== "Categorize by Voucher (Consolidated)") n += 1;
    if (caps.status.length > 0 && status) n += 1;
    if (caps.sla.length > 0 && sla) n += 1;
    if (caps.zeros && showZeros) n += 1;
    if (caps.accumulated && get("acc")) n += 1;
    if (caps.groups && get("groups") === "0") n += 1;
    if (caps.ctElections && (electSbr || electQfzp)) n += 1;
    return n;
  }, [
    caps, get, costCenter, account, warehouse, itemCode, partyType, party,
    voucherNo, categorizeBy, status, sla, showZeros, electSbr, electQfzp,
  ]);

  const sheetFieldCount = useMemo(() => {
    let n = 0;
    if (caps.dates) n += 2;
    if (caps.costCenter) n += 1;
    if (caps.account) n += 1;
    if (caps.warehouse) n += 1;
    if (caps.itemCode) n += 1;
    if (caps.party === "typed") n += 1;
    if (caps.party) n += 1;
    if (caps.voucher) n += 1;
    if (caps.categorize) n += 1;
    if (caps.status.length > 0) n += 1;
    if (caps.sla.length > 0) n += 1;
    if (hasToggles) n += 1;
    return n;
  }, [caps, hasToggles]);

  const clearSheetFilters = () => {
    setMany({
      from: "", to: "", cc: "", account: "", wh: "", item: "",
      ptype: "", party: "", vn: "", cat: "", zeros: "", acc: "", groups: "",
      status: "", sla: "", sbr: "", qfzp: "",
    });
  };

  useEffect(() => {
    if (!phone) setSheetOpen(false);
  }, [phone]);

  useEffect(() => {
    if (!sheetOpen) return;
    sheetRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setSheetOpen(false);
        filterBtnRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [sheetOpen]);

  const applyChip = (kind: Chip) => {
    const next = chipRange(kind, today, fy.data?.year_start_date, fy.data?.year_end_date);
    setMany({ from: next.from, to: next.to });
  };

  const closeSheet = () => {
    setSheetOpen(false);
    filterBtnRef.current?.focus();
  };

  const activateRow = (row: Row) => {
    const voucherRoute = spaRouteForVoucher(row.voucher_type, row.voucher_no);
    if (voucherRoute) {
      nav(voucherRoute);
      return;
    }
    const acct = String(row.account || "");
    if (!acct || name === "General Ledger" || !caps.tree) return;
    const params = new URLSearchParams({ account: acct, from: fromDate, to: toDate });
    nav(`/reports/${encodeURIComponent("General Ledger")}?${params}`);
  };

  if (!allowed) {
    return (
      <>
        <PageHead
          eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/reports")}>{t("rpt.title")}</button>}
          title={name}
        />
        <Empty label={t("rpt.unsupported")} />
      </>
    );
  }

  return (
    <div className="rpt-run">
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/reports")}>{t("rpt.title")}</button>}
        title={run.data?.message?.report_label || name}
        sub={phone ? undefined : (blurbKey ? t(blurbKey) : t("rpt.runSub"))}
        stickyActions={false}
        actions={
          <>
            <button
              type="button"
              className={`btn ghost sm${phone ? " rpt-icon-act" : ""}`}
              disabled={paused || run.isLoading}
              onClick={() => run.mutate()}
              aria-label={t("rpt.refresh")}
            >
              {phone ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M13.2 8a5.2 5.2 0 1 1-1.4-3.5" strokeLinecap="round" />
                  <path d="M13.2 2.8v3.2H10" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : t("rpt.refresh")}
            </button>
            <button
              type="button"
              className={`btn ghost sm${phone ? " rpt-icon-act" : ""}`}
              disabled={!shown.length}
              onClick={() => exportCsv(name, columns, shown)}
              aria-label={t("rpt.export")}
            >
              {phone ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M8 2.5v7M5.5 7.2 8 9.7l2.5-2.5M3.2 12.5h9.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : t("rpt.export")}
            </button>
          </>
        }
      />

      {/* Frappe `.page-form` — filters above the grid (sheet on phone). */}
      <div className={`rpt-form${phone ? " rpt-form-phone" : ""}`}>
        {(caps.periodChips || caps.periodicity || (phone && sheetFieldCount > 0)) && (
          <div className="rpt-top">
            {caps.periodChips && (
              <div className="rpt-links" role="group" aria-label={t("rpt.period")}>
                {(["month", "quarter", "ytd", "fy"] as const).map((k) => (
                  <button key={k} type="button" aria-pressed={activeChip === k} onClick={() => applyChip(k)}>
                    {t(`rpt.chip.${k}`)}
                  </button>
                ))}
              </div>
            )}
            {caps.periodicity && (
              <label className="rpt-grain">
                <span>{t("rpt.columns")}</span>
                <select className="ctl" value={periodicity} onChange={(e) => set("p", e.target.value)}>
                  {PERIODICITIES.map((p) => (
                    <option key={p} value={p}>{t(`rpt.p.${p}`)}</option>
                  ))}
                </select>
              </label>
            )}
            {phone && sheetFieldCount > 0 && (
              <button
                ref={filterBtnRef}
                type="button"
                className={`lm-fbtn rpt-fbtn${sheetApplied > 0 ? " lm-on" : ""}`}
                aria-expanded={sheetOpen}
                aria-haspopup="dialog"
                onClick={() => setSheetOpen(true)}
              >
                <svg className="lm-ic" width="15" height="15" viewBox="0 0 16 16" fill="none"
                  stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
                  <path d="M2 4h12M4.5 8h7M7 12h2" />
                </svg>
                {t("m.filters")}
                {sheetApplied > 0 && <span className="lm-fcount">{sheetApplied}</span>}
              </button>
            )}
          </div>
        )}

        {(!phone || !sheetFieldCount) && (
          <div className="rpt-fields">
            {caps.dates && (
              <>
                <Field label={t("rpt.from")}>
                  <input className="ctl" type="date" value={fromDate} onChange={(e) => set("from", e.target.value)} />
                </Field>
                <Field label={t("rpt.to")}>
                  <input className="ctl" type="date" value={toDate} onChange={(e) => set("to", e.target.value)} />
                </Field>
              </>
            )}
            {caps.costCenter && (
              <Field label={t("rpt.costCenter")}>
                <LinkFilter
                  doctype={DT.costCenter}
                  value={costCenter}
                  placeholder={t("rpt.costCenter")}
                  filters={companyFilters}
                  onChange={(v) => set("cc", v)}
                />
              </Field>
            )}
            {caps.account && (
              <Field label={t("rpt.account")}>
                <LinkFilter
                  doctype={DT.account}
                  value={account}
                  placeholder={t("rpt.account")}
                  filters={companyFilters}
                  onChange={(v) => set("account", v)}
                />
              </Field>
            )}
            {caps.warehouse && (
              <Field label={t("rpt.warehouse")}>
                <LinkFilter
                  doctype={DT.warehouse}
                  value={warehouse}
                  placeholder={t("rpt.warehouse")}
                  filters={companyFilters}
                  onChange={(v) => set("wh", v)}
                />
              </Field>
            )}
            {caps.itemCode && (
              <Field label={t("rpt.item")}>
                <LinkFilter
                  doctype={DT.item}
                  value={itemCode}
                  placeholder={t("rpt.item")}
                  onChange={(v) => set("item", v)}
                />
              </Field>
            )}
            {caps.party === "typed" && (
              <Field label={t("rpt.partyType")}>
                <select className="ctl" value={partyType} onChange={(e) => setMany({ ptype: e.target.value, party: "" })}>
                  <option value="">{t("rpt.any")}</option>
                  <option value="Customer">{t("nav.customers")}</option>
                  <option value="Supplier">{t("nav.suppliers")}</option>
                </select>
              </Field>
            )}
            {caps.party && (caps.party !== "typed" || partyType) && (
              <Field label={t("rpt.party")}>
                <LinkFilter
                  doctype={caps.party === "typed" ? partyType : caps.party}
                  value={party}
                  placeholder={t("rpt.party")}
                  onChange={(v) => set("party", v)}
                />
              </Field>
            )}
            {caps.voucher && (
              <Field label={t("rpt.voucher")}>
                <input className="ctl" value={voucherNo} onChange={(e) => set("vn", e.target.value)} placeholder={t("rpt.voucher")} />
              </Field>
            )}
            {caps.categorize && (
              <Field label={t("rpt.categorize")}>
                <select className="ctl" value={categorizeBy} onChange={(e) => set("cat", e.target.value)}>
                  {GL_CATEGORIES.map((c) => <option key={c} value={c}>{t(CAT_LABEL[c] ?? c)}</option>)}
                </select>
              </Field>
            )}
            {caps.status.length > 0 && (
              <Field label={t("rpt.status")}>
                <select className="ctl" value={status} onChange={(e) => set("status", e.target.value)}>
                  <option value="">{t("rpt.any")}</option>
                  {caps.status.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            )}
            {caps.sla.length > 0 && (
              <Field label={t("rpt.sla")}>
                <select className="ctl" value={sla} onChange={(e) => set("sla", e.target.value)}>
                  <option value="">{t("rpt.any")}</option>
                  {caps.sla.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            )}
            {hasToggles && (
              <div className="rpt-checks">
                {caps.accumulated && (
                  <Check
                    on={(accumulated ?? name === "Balance Sheet") === true}
                    label={t("rpt.accumulated")}
                    onChange={() => set("acc", (accumulated ?? name === "Balance Sheet") ? "0" : "1")}
                  />
                )}
                {caps.zeros && (
                  <Check on={showZeros} label={t("rpt.zeros")} onChange={() => set("zeros", showZeros ? "" : "1")} />
                )}
                {caps.groups && (
                  <Check on={showGroups} label={t("rpt.groups")} onChange={() => set("groups", showGroups ? "0" : "1")} />
                )}
                {caps.ctElections && (
                  <>
                    <Check on={electSbr} label={t("rpt.sbr")} onChange={() => set("sbr", electSbr ? "" : "1")} />
                    <Check on={electQfzp} label={t("rpt.qfzp")} onChange={() => set("qfzp", electQfzp ? "" : "1")} />
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {phone && sheetOpen && sheetFieldCount > 0 && (
        <>
          <button type="button" className="lm-scrim" tabIndex={-1} aria-label={t("m.close")} onClick={closeSheet} />
          <div
            className="lm-sheet"
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-label={t("m.filters")}
            tabIndex={-1}
          >
            <div className="lm-shead">
              <b>{t("m.filters")}</b>
              {sheetApplied > 0 && (
                <span className="lm-sapplied">{t("m.filters.on").replace("{n}", String(sheetApplied))}</span>
              )}
              <button type="button" className="lm-x" aria-label={t("m.close")} onClick={closeSheet}>✕</button>
            </div>
            <div className="lm-sbody rpt-sheet-body">
              {caps.dates && (
                <>
                  <div className="lm-frow">
                    <Field label={t("rpt.from")}>
                      <input className="ctl" type="date" value={fromDate} onChange={(e) => set("from", e.target.value)} />
                    </Field>
                  </div>
                  <div className="lm-frow">
                    <Field label={t("rpt.to")}>
                      <input className="ctl" type="date" value={toDate} onChange={(e) => set("to", e.target.value)} />
                    </Field>
                  </div>
                </>
              )}
              {caps.costCenter && (
                <div className="lm-frow">
                  <Field label={t("rpt.costCenter")}>
                    <LinkFilter
                      doctype={DT.costCenter}
                      value={costCenter}
                      placeholder={t("rpt.costCenter")}
                      filters={companyFilters}
                      onChange={(v) => set("cc", v)}
                    />
                  </Field>
                </div>
              )}
              {caps.account && (
                <div className="lm-frow">
                  <Field label={t("rpt.account")}>
                    <LinkFilter
                      doctype={DT.account}
                      value={account}
                      placeholder={t("rpt.account")}
                      filters={companyFilters}
                      onChange={(v) => set("account", v)}
                    />
                  </Field>
                </div>
              )}
              {caps.warehouse && (
                <div className="lm-frow">
                  <Field label={t("rpt.warehouse")}>
                    <LinkFilter
                      doctype={DT.warehouse}
                      value={warehouse}
                      placeholder={t("rpt.warehouse")}
                      filters={companyFilters}
                      onChange={(v) => set("wh", v)}
                    />
                  </Field>
                </div>
              )}
              {caps.itemCode && (
                <div className="lm-frow">
                  <Field label={t("rpt.item")}>
                    <LinkFilter
                      doctype={DT.item}
                      value={itemCode}
                      placeholder={t("rpt.item")}
                      onChange={(v) => set("item", v)}
                    />
                  </Field>
                </div>
              )}
              {caps.party === "typed" && (
                <div className="lm-frow">
                  <Field label={t("rpt.partyType")}>
                    <select className="ctl" value={partyType} onChange={(e) => setMany({ ptype: e.target.value, party: "" })}>
                      <option value="">{t("rpt.any")}</option>
                      <option value="Customer">{t("nav.customers")}</option>
                      <option value="Supplier">{t("nav.suppliers")}</option>
                    </select>
                  </Field>
                </div>
              )}
              {caps.party && (caps.party !== "typed" || partyType) && (
                <div className="lm-frow">
                  <Field label={t("rpt.party")}>
                    <LinkFilter
                      doctype={caps.party === "typed" ? partyType : caps.party}
                      value={party}
                      placeholder={t("rpt.party")}
                      onChange={(v) => set("party", v)}
                    />
                  </Field>
                </div>
              )}
              {caps.voucher && (
                <div className="lm-frow">
                  <Field label={t("rpt.voucher")}>
                    <input className="ctl" value={voucherNo} onChange={(e) => set("vn", e.target.value)} placeholder={t("rpt.voucher")} />
                  </Field>
                </div>
              )}
              {caps.categorize && (
                <div className="lm-frow">
                  <Field label={t("rpt.categorize")}>
                    <select className="ctl" value={categorizeBy} onChange={(e) => set("cat", e.target.value)}>
                      {GL_CATEGORIES.map((c) => <option key={c} value={c}>{t(CAT_LABEL[c] ?? c)}</option>)}
                    </select>
                  </Field>
                </div>
              )}
              {caps.status.length > 0 && (
                <div className="lm-frow">
                  <Field label={t("rpt.status")}>
                    <select className="ctl" value={status} onChange={(e) => set("status", e.target.value)}>
                      <option value="">{t("rpt.any")}</option>
                      {caps.status.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                </div>
              )}
              {caps.sla.length > 0 && (
                <div className="lm-frow">
                  <Field label={t("rpt.sla")}>
                    <select className="ctl" value={sla} onChange={(e) => set("sla", e.target.value)}>
                      <option value="">{t("rpt.any")}</option>
                      {caps.sla.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </Field>
                </div>
              )}
              {hasToggles && (
                <div className="lm-frow rpt-checks">
                  {caps.accumulated && (
                    <Check
                      on={(accumulated ?? name === "Balance Sheet") === true}
                      label={t("rpt.accumulated")}
                      onChange={() => set("acc", (accumulated ?? name === "Balance Sheet") ? "0" : "1")}
                    />
                  )}
                  {caps.zeros && (
                    <Check on={showZeros} label={t("rpt.zeros")} onChange={() => set("zeros", showZeros ? "" : "1")} />
                  )}
                  {caps.groups && (
                    <Check on={showGroups} label={t("rpt.groups")} onChange={() => set("groups", showGroups ? "0" : "1")} />
                  )}
                  {caps.ctElections && (
                    <>
                      <Check on={electSbr} label={t("rpt.sbr")} onChange={() => set("sbr", electSbr ? "" : "1")} />
                      <Check on={electQfzp} label={t("rpt.qfzp")} onChange={() => set("qfzp", electQfzp ? "" : "1")} />
                    </>
                  )}
                </div>
              )}
            </div>
            <div className="lm-sfoot">
              <button type="button" className="btn ghost" onClick={clearSheetFilters}>{t("m.filters.clear")}</button>
              <button type="button" className="btn" onClick={closeSheet}>{t("m.filters.show")}</button>
            </div>
          </div>
        </>
      )}

      {run.error && <ErrorBox error={run.error} onRetry={() => run.mutate()} />}

      <div className="rpt-grid-wrap">
        <ReportDataTable
          columns={columns}
          rows={shown}
          isMoney={isMoney}
          compact={phone}
          loading={paused || run.isLoading}
          loadingNode={<Loading />}
          empty={<Empty label={q ? t("rpt.noneRows") : t("rpt.empty")} />}
          regionLabel={t("rpt.resultsRegion")}
          isRowActive={(row) => {
            if (spaRouteForVoucher(row.voucher_type, row.voucher_no)) return true;
            return Boolean(caps.tree && row.account && name !== "General Ledger");
          }}
          rowLabel={(row) => {
            const voucherRoute = spaRouteForVoucher(row.voucher_type, row.voucher_no);
            if (voucherRoute) {
              return fill(t("rpt.openVoucher"), {
                t: String(row.voucher_type || ""),
                n: String(row.voucher_no || ""),
              });
            }
            return fill(t("rpt.openAccount"), { a: String(row.account || "") });
          }}
          rowClassName={(row) => {
            const clickable = Boolean(caps.tree && row.account && name !== "General Ledger");
            const voucherRoute = spaRouteForVoucher(row.voucher_type, row.voucher_no);
            return [
              row.bold ? "rpt-bold" : "",
              clickable || voucherRoute ? "rpt-open" : "",
            ].filter(Boolean).join(" ");
          }}
          onRowActivate={activateRow}
          renderCell={(row, c) => cell(row, c)}
        />
        <div className="rpt-footer">
          <span className="rpt-footer-meta">
            {[
              session.currency || null,
              paused || run.isLoading
                ? t("list.loading")
                : q && rows.length !== shown.length
                  ? fill(t("rpt.ofTotal"), { n: shown.length, total: rows.length })
                  : fill(t("rpt.rowCount"), { n: shown.length }),
            ].filter(Boolean).join(" · ")}
          </span>
          <div className="rpt-footer-find">
            <SearchFilter value={find} onChange={setFind} placeholder={t("rpt.find")} />
          </div>
        </div>
      </div>
    </div>
  );
}
