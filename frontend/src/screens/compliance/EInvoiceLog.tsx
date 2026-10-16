/**
 * E-Invoice Log — bulk queue + failure triage UI (Phase 23).
 * Importers: App.tsx route /e-invoice-log.
 * API: taxmate.api.resource.get_list on UAE E-Invoice Log;
 *   taxmate.uae_e_invoicing.utils.e_invoice.generate_e_invoice (retry);
 *   taxmate.uae_e_invoicing.utils.e_invoice.sync_status_from_asp (sync);
 *   taxmate.uae_e_invoicing.utils.e_invoice.bulk_generate_e_invoices.
 * Schema: name, status (Select), reference_name, reference_doctype, company, modified, asp_document_id.
 * User: "Implement the plan… complete all the to-dos."
 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDocCount, useDocList } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { useListParams, type FilterTuple } from "../../lib/list";
import { datetime } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, PageHead, Pill } from "../../components/ui";
import { DataTable, ListFooter, type Column } from "../../components/DataTable";
import { FilterBar, SearchFilter, SelectFilter } from "../../components/filters";

const PAGE = 20;

const STATUS_OPTIONS = [
  /* value = the server's own status word, never translated.
     labelKey is resolved at render time — see the SelectFilter below. */
  { value: "Failed", labelKey: "einv.st.failed" },
  { value: "Rejected", labelKey: "einv.st.rejected" },
  { value: "Pending", labelKey: "einv.st.pending" },
  { value: "Generated", labelKey: "einv.st.generated" },
  { value: "Accepted", labelKey: "einv.st.accepted" },
];

type Row = {
  name: string;
  status?: string;
  reference_name?: string;
  reference_doctype?: string;
  company?: string;
  modified?: string;
  asp_document_id?: string;
};

function elogPill(status?: string): string {
  if (status === "Accepted" || status === "Generated") return "p-done";
  if (status === "Failed" || status === "Rejected") return "p-cxl";
  if (status === "Pending") return "p-open";
  return "p-draft";
}

export default function EInvoiceLog() {
  const nav = useNavigate();
  const session = useSession();
  const { get, set, page, setPage, start } = useListParams(PAGE);
  const q = get("q");
  const statusFilter = get("status");
  const company = session.company;
  const paused = !session.user || !company;

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  const generateCall = useFrappePostCall(METHOD.generateEInvoice);
  const syncCall = useFrappePostCall(METHOD.syncEInvoiceStatus);

  const filters = useMemo<FilterTuple[]>(() => {
    const f: FilterTuple[] = company ? [["company", "=", company]] : [];
    if (q.trim()) f.push(["reference_name", "like", `%${q.trim()}%`]);
    if (statusFilter) f.push(["status", "=", statusFilter]);
    return f;
  }, [company, q, statusFilter]);

  const list = useDocList<Row>(DT.eInvoiceLog, {
    fields: ["name", "status", "reference_name", "reference_doctype", "company", "modified", "asp_document_id"],
    filters,
    orderBy: { field: "modified", order: "desc" },
    limit: PAGE,
    limit_start: start,
  }, paused ? null : undefined);

  const count = useDocCount(DT.eInvoiceLog, filters, undefined, paused ? null : undefined);
  const rows = list.data ?? [];
  const total = count.data ?? 0;

  function toggleSelect(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === rows.length) setSelected(new Set());
    else setSelected(new Set(rows.map((r) => r.name)));
  }

  async function retrySelected() {
    if (!selected.size) return;
    setBusy(true); setActionError(null);
    try {
      for (const logName of selected) {
        const row = rows.find((r) => r.name === logName);
        if (row?.reference_name) {
          await generateCall.call({ invoice_name: row.reference_name });
        }
      }
      setSelected(new Set());
      list.mutate();
    } catch (e) { setActionError(e); } finally { setBusy(false); }
  }

  async function syncSelected() {
    if (!selected.size) return;
    setBusy(true); setActionError(null);
    try {
      for (const logName of selected) {
        const row = rows.find((r) => r.name === logName);
        if (row?.asp_document_id) {
          await syncCall.call({ document_id: row.asp_document_id });
        }
      }
      setSelected(new Set());
      list.mutate();
    } catch (e) { setActionError(e); } finally { setBusy(false); }
  }

  const columns: Column<Row>[] = [
    {
      key: "select",
      header: <input type="checkbox" checked={selected.size === rows.length && rows.length > 0} onChange={toggleAll} aria-label={t("list.selectAll")} />,
      cell: (r) => <input type="checkbox" checked={selected.has(r.name)} onChange={() => toggleSelect(r.name)} aria-label={r.name} />,
    },
    { key: "reference_name", header: t("elog.col.invoice"), cell: (r) => r.reference_name ?? "—" },
    {
      key: "status",
      header: t("elog.col.status"),
      cell: (r) => <Pill cls={elogPill(r.status)}>{r.status ?? "—"}</Pill>,
    },
    { key: "modified", header: t("elog.col.updated"), cell: (r) => datetime(r.modified) },
    { key: "asp_document_id", header: t("einv.col.aspId"), cell: (r) => r.asp_document_id ? r.asp_document_id.slice(0, 12) + "…" : "—" },
  ];

  return (
    <>
      <PageHead title={t("nav.eInvoiceLog")} />
      {actionError && <ErrorBox error={actionError} />}
      <Card bodyClass={null as unknown as string}>
        <FilterBar>
          <SearchFilter value={q} onChange={(v) => set("q", v)} placeholder={t("elog.search")} />
          <SelectFilter value={statusFilter} onChange={(v) => set("status", v)} allLabel={t("elog.col.status")} options={STATUS_OPTIONS.map((o) => ({ value: o.value, label: t(o.labelKey) }))} />
        </FilterBar>
        {selected.size > 0 && (
          <div className="flex gap-2 p-2 bg-surface-muted border-b">
            <span className="text-sm text-muted self-center">{selected.size} {t("inv.bulk.selected")}</span>
            <button className="btn btn-secondary btn-sm" onClick={retrySelected} disabled={busy}>
              {busy ? t("common.saving") : t("elog.retry")}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={syncSelected} disabled={busy}>
              {t("elog.sync")}
            </button>
          </div>
        )}
        <DataTable
          rows={rows}
          columns={columns}
          rowKey={(r) => r.name}
          state={{ isLoading: paused || list.isLoading, error: list.error, onRetry: () => list.mutate() }}
          emptyLabel={t("elog.empty")}
          onOpen={(r) => {
            if (r.reference_doctype === DT.salesInvoice && r.reference_name) {
              nav(`/invoices/${encodeURIComponent(r.reference_name)}`);
            }
          }}
        />
        <ListFooter shown={rows.length} total={total} page={page} pageSize={PAGE} onPage={setPage} />
      </Card>
    </>
  );
}
