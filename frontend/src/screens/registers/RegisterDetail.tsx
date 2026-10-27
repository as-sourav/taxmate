/**
 * Detail for one of the eight Desk documents.
 * Callers: App.tsx /:name. API: taxmate.api.resource.get, taxmate.api.workflow.*,
 * taxmate.api.linked_docs for the next Desk document.
 * Schema: parent doc plus items, delivery_stops, or suppliers.
 * User: build Opportunity, Request for Quotation, Shipment, Installation Note,
 * Delivery Trip, Payment Request, and the two subcontracting documents.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { Card, ErrorBox, Field, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import { t } from "../../i18n/strings";
import { date, money } from "../../lib/format";
import { DT, METHOD } from "../../lib/frappe";
import { useInsertMapped, useOpenMapped } from "../../lib/openMapped";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { useDoc, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { REGISTERS } from "./config";

type Line = {
  name?: string;
  item_code?: string;
  item_name?: string;
  qty?: number;
  customer?: string;
  address?: string;
  delivery_note?: string;
};
type SupplierRow = { supplier?: string };
type Doc = Record<string, unknown> & {
  name: string;
  status?: string;
  docstatus?: number;
  items?: Line[];
  delivery_stops?: Line[];
  suppliers?: SupplierRow[];
  currency?: string;
  payment_request_type?: string;
  lost_reasons?: unknown;
};

function statusPill(status?: string): string {
  if (status === "Draft" || status === "Open") return "p-open";
  if (status === "Completed" || status === "Paid" || status === "Converted") return "p-done";
  if (status === "Cancelled" || status === "Closed" || status === "Lost" || status === "Stopped") return "p-cxl";
  return "p-flat";
}

const lineFields: LineField<Line>[] = [
  { key: "item", label: "Item", slot: "title", render: (row) => row.item_code || row.item_name || row.delivery_note || row.customer || row.address || "—" },
  { key: "qty", label: "Qty", slot: "primary", render: (row) => row.qty ?? "—" },
];

export default function RegisterDetail({ specKey }: { specKey: string }) {
  const spec = REGISTERS[specKey];
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const doc = useDoc<Doc>(spec.doctype, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const quote = useInsertMapped(DT.quotation, "/quotations");
  const supplierQuote = useInsertMapped(DT.supplierQuotation, "/supplier-quotations");
  const payment = useInsertMapped(DT.paymentEntry, "/payments");
  const rfq = useOpenMapped("/request-for-quotations");
  const makeQuote = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeOpportunityQuotation);
  const makeSq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeOpportunitySupplierQuotation);
  const makeRfq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeOpportunityRfq);
  const makeSqFromRfq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeRfqSupplierQuotation);
  const makePay = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePaymentEntryFromRequest);
  const statusSave = useSave();
  const deleteAction = useDeleteDraftAction({ doctype: spec.doctype, name, listPath: spec.path });
  const [supplier, setSupplier] = useState("");
  const [statusError, setStatusError] = useState<unknown>(null);

  const data = doc.data;
  const writable = canWrite(session);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const rawLines = spec.linesKey ? data?.[spec.linesKey] : undefined;
  const lines = Array.isArray(rawLines) ? rawLines as Line[] : [];
  const lost = data?.status === "Lost";
  const hasItems = (data?.items?.length ?? 0) > 0;
  const suppliers = data?.suppliers ?? [];
  const canPay = spec.doctype === "Payment Request"
    && data?.docstatus === 1
    && data?.payment_request_type === "Outward"
    && (data?.status === "Initiated" || data?.status === "Partially Paid");

  async function setOpportunityStatus(status: string) {
    setStatusError(null);
    try {
      await statusSave.updateDoc(spec.doctype, name, { status, lost_reasons: status === "Open" ? [] : data?.lost_reasons });
      await doc.mutate();
    } catch (err) {
      setStatusError(err);
    }
  }

  if (doc.isLoading) return <Loading />;
  if (doc.error) return <ErrorBox error={doc.error} onRetry={() => doc.mutate()} />;
  if (!data) return null;

  const busy = quote.busy || supplierQuote.busy || payment.busy || rfq.busy || statusSave.loading
    || submitCall.loading || cancelCall.loading || amendCall.loading || deleteAction.loading;
  const actionError = quote.error || supplierQuote.error || payment.error || rfq.error || statusError
    || submitCall.error || cancelCall.error || amendCall.error || deleteAction.error;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav(spec.path)}>{t(spec.titleKey)}</button>}
        title={data.name}
        actions={(
          <DetailActions
            doctype={spec.doctype}
            name={name}
            draft={!spec.submittable || data.docstatus === 0}
            submitted={spec.submittable ? data.docstatus === 1 : false}
            cancelled={spec.submittable ? data.docstatus === 2 : false}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={writable}
            busy={busy}
            onEdit={writable ? () => nav(`${spec.path}/${encodeURIComponent(name)}/edit`) : undefined}
            onSubmit={spec.submittable ? () => void submitCall.call({ doc: { doctype: spec.doctype, name } }).then(() => doc.mutate()) : undefined}
            onDelete={spec.submittable ? deleteAction.onDelete : undefined}
            onCancel={spec.submittable ? () => void cancelCall.call({ doctype: spec.doctype, name }).then(() => doc.mutate()) : undefined}
            onAmend={spec.submittable ? async () => {
              const res = await amendCall.call({ doctype: spec.doctype, name });
              const next = res?.message?.name;
              if (next) nav(`${spec.path}/${encodeURIComponent(next)}/edit`);
              else await doc.mutate();
            } : undefined}
            extra={(
              <>
                {spec.doctype === "Opportunity" && !lost && (
                  <button type="button" className="btn ghost" disabled={busy} onClick={() => void quote.open(() => makeQuote.call({ source_name: name }))}>
                    Quotation
                  </button>
                )}
                {spec.doctype === "Opportunity" && !lost && hasItems && (
                  <>
                    <button type="button" className="btn ghost" disabled={busy} onClick={() => void rfq.open(() => makeRfq.call({ source_name: name }))}>
                      Request for Quotation
                    </button>
                    <button type="button" className="btn ghost" disabled={busy} onClick={() => void supplierQuote.open(() => makeSq.call({ source_name: name }))}>
                      Supplier Quotation
                    </button>
                  </>
                )}
                {spec.doctype === "Opportunity" && writable && data.status === "Open" && (
                  <button type="button" className="btn ghost" disabled={busy} onClick={() => void setOpportunityStatus("Closed")}>{t("hist.close")}</button>
                )}
                {spec.doctype === "Opportunity" && writable && data.status && data.status !== "Open" && (
                  <button type="button" className="btn ghost" disabled={busy} onClick={() => void setOpportunityStatus("Open")}>Reopen</button>
                )}
                {spec.doctype === "Request for Quotation" && data.docstatus === 1 && suppliers.length > 0 && (
                  <>
                    <Field label="Supplier">
                      <select className="ctl" aria-label="Supplier" value={supplier} onChange={(event) => setSupplier(event.target.value)}>
                        <option value="">—</option>
                        {suppliers.map((row) => (
                          <option key={row.supplier} value={row.supplier}>{row.supplier}</option>
                        ))}
                      </select>
                    </Field>
                    <button
                      type="button"
                      className="btn ghost"
                      disabled={busy || !supplier}
                      onClick={() => void supplierQuote.open(() => makeSqFromRfq.call({ source_name: name, for_supplier: supplier }))}
                    >
                      Supplier Quotation
                    </button>
                  </>
                )}
                {canPay && (
                  <button type="button" className="btn ghost" disabled={busy} onClick={() => void payment.open(() => makePay.call({ source_name: name }))}>
                    {t("sod.createPayment")}
                  </button>
                )}
              </>
            )}
          />
        )}
      />
      {actionError ? <ErrorBox error={actionError} /> : null}
      <Card>
        <div className="grid2">
          <ReadRow k="Status" v={<Pill cls={statusPill(data.status)}>{data.status || "—"}</Pill>} />
          {spec.facts.map((fact) => {
            const value = data[fact.field];
            const shown = fact.date
              ? date(typeof value === "string" ? value : "")
              : fact.money
                ? money(typeof value === "number" || typeof value === "string" ? value : 0)
                : (value == null || value === "" ? "—" : String(value));
            return <ReadRow key={fact.key} k={fact.label} v={shown} />;
          })}
        </div>
      </Card>
      {lines.length > 0 ? <LineItems rows={lines} fields={lineFields} /> : null}
    </>
  );
}
