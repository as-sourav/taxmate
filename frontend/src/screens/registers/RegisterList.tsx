/**
 * List for one of the eight Desk documents.
 * Callers: App.tsx. API: taxmate.api.resource.get_list / get_count / bulk_delete.
 * User: build Opportunity, Request for Quotation, Shipment, Installation Note,
 * Delivery Trip, Payment Request, and the two subcontracting documents.
 */
import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { Filter } from "frappe-react-sdk";

import { useDraftDelete } from "../../lib/useDraftDelete";
import { useSession } from "../../lib/session";
import { canWrite } from "../../lib/roles";
import BulkDraftBar from "../../components/BulkDraftBar";
import { useDocList, useDocCount } from "../../lib/resource";
import { useListParams } from "../../lib/list";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, Pill } from "../../components/ui";
import { ListScreen } from "../../components/screen";
import { DataTable, ListFooter, type Column } from "../../components/DataTable";
import { FilterBar, SearchFilter } from "../../components/filters";
import { IfCanWrite } from "../../components/RoleGate";
import { REGISTERS } from "./config";

const PAGE = 25;

type Row = { name: string; status?: string; docstatus?: number; [key: string]: unknown };

function statusPill(status?: string): string {
  if (status === "Draft" || status === "Open") return "p-open";
  if (status === "Completed" || status === "Paid" || status === "Converted") return "p-done";
  if (status === "Cancelled" || status === "Closed" || status === "Lost" || status === "Stopped") return "p-cxl";
  return "p-flat";
}

export default function RegisterList({ specKey }: { specKey: string }) {
  const spec = REGISTERS[specKey];
  const session = useSession();
  const nav = useNavigate();
  const { get, set, page, setPage, start } = useListParams(PAGE);
  const q = get("q");
  const title = t(spec.titleKey);

  const filters = useMemo(() => {
    const f: [string, string, string][] = [];
    if (q.trim()) f.push([spec.searchField, "like", `%${q.trim()}%`]);
    return f as unknown as Filter<Row>[];
  }, [q, spec.searchField]);

  const fields = useMemo(
    () => Array.from(new Set(["name", "status", "docstatus", ...spec.listFields])),
    [spec.listFields],
  );

  const list = useDocList<Row>(spec.doctype, {
    fields,
    filters,
    orderBy: { field: "modified", order: "desc" },
    limit: PAGE,
    limit_start: start,
  });
  const count = useDocCount(spec.doctype, filters);
  const rows = list.data ?? [];
  const writable = canWrite(session);
  const refreshList = useCallback(() => { void list.mutate(); }, [list]);
  const draftDelete = useDraftDelete({
    doctype: spec.doctype,
    onDone: refreshList,
    enabled: writable,
    mode: spec.submittable ? "draft" : "all",
    clearDeps: [q, page],
  });

  const columns: Column<Row>[] = [
    {
      key: "name",
      header: "Name",
      cell: (row) => <span className="ordno">{row.name}</span>,
    },
    ...spec.columns.filter((col) => col.field !== "name").map((col) => ({
      key: col.key,
      header: col.label,
      cell: (row: Row) => {
        const value = row[col.field];
        if (col.date) return date(typeof value === "string" ? value : "");
        if (col.money) return money(typeof value === "number" || typeof value === "string" ? value : 0);
        if (col.field === "status") return <Pill cls={statusPill(row.status)}>{row.status || "—"}</Pill>;
        return value == null || value === "" ? "—" : String(value);
      },
    })),
  ];

  return (
    <ListScreen
      title={title}
      primary={spec.standalone ? (
        <IfCanWrite>
          <button type="button" className="btn" onClick={() => nav(`${spec.path}/new`)}>New</button>
        </IfCanWrite>
      ) : undefined}
    >
      <Card bodyClass={null as unknown as string}>
        <FilterBar>
          <SearchFilter value={q} onChange={(v) => set("q", v)} placeholder="Search" />
        </FilterBar>
        <BulkDraftBar drafts={draftDelete} />
        <DataTable<Row>
          rows={rows}
          rowKey={(row) => row.name}
          onOpen={(row) => nav(`${spec.path}/${encodeURIComponent(row.name)}`)}
          state={{ isLoading: list.isLoading, error: list.error, onRetry: () => list.mutate() }}
          emptyLabel={spec.empty}
          columns={columns}
          selection={draftDelete.selection(rows)}
        />
        <ListFooter shown={rows.length} total={count.data ?? 0} page={page} pageSize={PAGE} onPage={setPage} />
      </Card>
    </ListScreen>
  );
}
