/**
 * WorkOrderDetail — Phase 18. Work Order detail with SE creation.
 * Callers: App.tsx /work-orders/:name
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { confirmCancel } from "../../lib/workflow";
import { date } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";

type Doc = {
  name: string; bom_no?: string; item_name?: string; qty?: number; produced_qty?: number;
  planned_start_date?: string; wip_warehouse?: string; fg_warehouse?: string;
  company?: string; status?: string; docstatus?: number;
};

function woPill(status?: string): string {
  if (!status || status === "Draft") return "p-draft";
  if (status === "Completed") return "p-done";
  if (status === "Cancelled" || status === "Stopped") return "p-cxl";
  if (status === "In Process") return "p-open";
  return "p-flat";
}

export default function WorkOrderDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.workOrder, name, listPath: "/work-orders" });
  const nav = useNavigate();
  const session = useSession();
  const writable = canWrite(session);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.workOrder, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  async function doAction(kind: "submit" | "cancel") {
    if (kind === "cancel" && !confirmCancel(name)) return;
    setBusy(true); setActionError(null);
    try {
      if (kind === "submit") await submitCall.call({ doc: { doctype: DT.workOrder, name } });
      else await cancelCall.call({ doctype: DT.workOrder, name });
      mutate();
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  async function doAmend() {
    setBusy(true); setActionError(null);
    try {
      const res = await amendCall.call({ doctype: DT.workOrder, name });
      const next = res?.message?.name;
      if (next) nav(`/work-orders/${encodeURIComponent(next)}`);
      else mutate();
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/work-orders")}>{t("wo.title")}</button>}
        title={data.name}
        actions={
          <>
            <DocHistory doctype={DT.workOrder} name={name} />
            {writable && data.docstatus === 0 && (
              <button type="button" className="btn ghost" onClick={() => nav(`/work-orders/${encodeURIComponent(name)}/edit`)}>{t("edit")}</button>
            )}
            {canSubmit && data.docstatus === 0 && (
              <button type="button" className="btn" onClick={() => void doAction("submit")} disabled={busy}>{t("wo.submit")}</button>
            )}
            {writable && data.docstatus === 0 && (
              <button type="button" className="btn quiet" disabled={deleteAction.loading}
                onClick={deleteAction.onDelete}>
                {deleteAction.loading ? t("soc.saving") : t("inv.delete")}
              </button>
            )}
            {canCancel && data.docstatus === 1 && (
              <button type="button" className="btn ghost" onClick={() => void doAction("cancel")} disabled={busy}>{t("wo.cancel")}</button>
            )}
            {canSubmit && data.docstatus === 2 && (
              <button type="button" className="btn ghost" onClick={() => void doAmend()} disabled={busy}>{t("inv.amend")}</button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <Pill cls={woPill(data.status)}>{data.status || "Draft"}</Pill>
        </p>
      </PageHead>
      {actionError ? <ErrorBox error={actionError} /> : null}
      <Card>
        <div className="fg">
          <ReadRow k={t("wo.col.bom")} v={data.bom_no || "—"} />
          <ReadRow k={t("wo.col.item")} v={data.item_name || "—"} />
          <ReadRow k={t("wo.col.qty")} v={`${data.produced_qty ?? 0} / ${data.qty ?? 0}`} />
          <ReadRow k={t("wo.col.start")} v={date(data.planned_start_date)} />
          {data.wip_warehouse ? <ReadRow k={t("wo.col.wip")} v={data.wip_warehouse} /> : null}
          {data.fg_warehouse ? <ReadRow k={t("wo.col.fg")} v={data.fg_warehouse} /> : null}
        </div>
      </Card>
    </>
  );
}
