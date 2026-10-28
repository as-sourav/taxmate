import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useOpenMapped } from "../../lib/openMapped";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canWrite } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { formatLineDiscount, TxnTotals } from "../../components/txnFields";
import { lineHasProductDiscount, productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import UpdateItems from "../../components/UpdateItems";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { printDocUrl } from "../../lib/printDoc";
import { isNative } from "../../mobile/platform";

type Line = {
  name?: string;
  item_code?: string; item_name?: string; qty?: number; received_qty?: number;
  returned_qty?: number; delivered_by_supplier?: number; subcontracted_qty?: number;
  billed_amt?: number; uom?: string; rate?: number; amount?: number;
  price_list_rate?: number; discount_percentage?: number; discount_amount?: number;
};
type Doc = {
  name: string; supplier?: string; supplier_name?: string; transaction_date?: string;
  schedule_date?: string; company?: string; status?: string; currency?: string;
  total?: number; grand_total?: number; net_total?: number; total_taxes_and_charges?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  docstatus?: number; per_received?: number; per_billed?: number;
  is_subcontracted?: number; is_old_subcontracting_flow?: number;
  items?: Line[];
};

function poPill(status?: string): string {
  if (status === "Draft" || status === "On Hold") return "p-draft";
  if (status === "Completed" || status === "Delivered") return "p-done";
  if (status === "Cancelled" || status === "Closed") return "p-cxl";
  return "p-open";
}

export default function PurchaseOrderDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.purchaseOrder, name, listPath: "/purchase-orders" });
  const nav = useNavigate();
  const session = useSession();
  const writable = canWrite(session);
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.purchaseOrder, name);
  const makePr = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePurchaseReceipt);
  const makePi = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePurchaseInvoice);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const canSubmit = canWrite(session);
  const canCancel = canWrite(session);
  const create = useInsert();
  const setStatus = useFrappePostCall(METHOD.setPurchaseOrderStatus);
  const dropshipCall = useFrappePostCall(METHOD.updateDropshipQty);
  const makePayReq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePaymentRequest);
  const makeSub = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSubcontractingOrder);
  const paymentRequest = useOpenMapped("/payment-requests");
  const subcontract = useOpenMapped("/subcontracting-orders");
  const [busy, setBusy] = useState<"" | "pr" | "pi">("");
  const [holdReason, setHoldReason] = useState("");
  const [mapError, setMapError] = useState<unknown>(null);
  const [statusError, setStatusError] = useState<unknown>(null);
  const [dropRows, setDropRows] = useState<{ name: string; item_code?: string; qty?: number; received_qty?: number; qty_change: number; selected: boolean }[] | null>(null);

  async function createDownstream(kind: "pr" | "pi") {
    setBusy(kind);
    setMapError(null);
    try {
      const call = kind === "pr" ? makePr.call : makePi.call;
      const doctype = kind === "pr" ? DT.purchaseReceipt : DT.purchaseInvoice;
      const res = await call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("doc.err.mapFailed"));
      const body: Record<string, unknown> = { ...(mapped as Record<string, unknown>) };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(doctype, body);
      const newName = (created as { name: string }).name;
      if (kind === "pi") nav(`/purchase-invoices/${encodeURIComponent(newName)}`);
      else nav(`/purchase-receipts/${encodeURIComponent(newName)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.currency || "";
  const lines = data.items ?? [];
  const showLineDiscount = lines.some(lineHasProductDiscount);
  const returnedQty = lines.reduce((sum, row) => sum + (Number(row.returned_qty) || 0), 0);
  const held = data.status === "On Hold";
  const stopped = data.status === "Closed" || data.status === "Delivered";
  const stillOpen = (data.per_received ?? 0) < 100 || (data.per_billed ?? 0) < 100;
  const canReceive = data.docstatus === 1 && !held && data.status !== "Closed" && lines.some((row) => {
    if (row.delivered_by_supplier) return false;
    return Number(row.received_qty) < Number(row.qty);
  });
  const canBill = data.docstatus === 1 && !held && data.status !== "Closed" && (data.per_billed ?? 0) < 100;
  const canChange = writable && data.docstatus === 1 && !stopped && stillOpen;
  const canDropship = writable && data.docstatus === 1
    && !["Closed", "Delivered", "Completed"].includes(data.status || "")
    && lines.some((row) => row.delivered_by_supplier);

  async function saveDropship() {
    const chosen = (dropRows ?? []).filter((row) => row.selected && row.qty_change);
    if (!chosen.length) {
      setMapError(new Error(t("doc.err.mapFailed")));
      return;
    }
    setMapError(null);
    try {
      await dropshipCall.call({
        name,
        items: chosen.map((row) => ({ name: row.name, current_qty: row.received_qty || 0, qty_change: row.qty_change })),
      });
      setDropRows(null);
      await mutate();
    } catch (err) {
      setMapError(err);
    }
  }

  async function changeStatus(status: string, reason?: string) {
    setStatusError(null);
    try {
      await setStatus.call({ name, status, reason });
      setHoldReason("");
      await mutate();
    } catch (err) {
      setStatusError(err);
    }
  }

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/purchase-orders")}>
            {t("nav.purchaseOrders")}
          </button>
        }
        title={data.supplier_name || data.supplier || data.name}
        actions={
          writable ? (
            <DetailActions
            doctype={DT.purchaseOrder}
            name={name}
              draft={data.docstatus === 0}
              submitted={data.docstatus === 1}
              cancelled={data.docstatus === 2}
              canSubmit={canSubmit}
              canCancel={canCancel}
              canWrite={writable}
              busy={submitCall.loading || cancelCall.loading || amendCall.loading || setStatus.loading || !!busy || deleteAction.loading}
              onEdit={() => nav(`/purchase-orders/${encodeURIComponent(name)}/edit`)}
              onSubmit={() => void submitCall.call({ doc: { doctype: DT.purchaseOrder, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
              onCancel={() => void cancelCall.call({ doctype: DT.purchaseOrder, name }).then(() => mutate())}
              onAmend={async () => {
                const res = await amendCall.call({ doctype: DT.purchaseOrder, name });
                const newName = res?.message?.name;
                if (newName) nav(`/purchase-orders/${encodeURIComponent(newName)}/edit`);
                else mutate();
              }}
              extra={
                <>
                  {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                  {!isNative() && (
                  <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.purchaseOrder, name), "_blank", "noopener")}>
                    {t("inv.print")}
                  </button>
                  )}
                  {canReceive && (
                  <button type="button" className="btn ghost" disabled={!!busy} onClick={() => void createDownstream("pr")}>
                    {busy === "pr" ? t("soc.saving") : t("po.receive")}
                  </button>
                  )}
                  {canBill && (
                  <button type="button" className="btn" disabled={!!busy} onClick={() => void createDownstream("pi")}>
                    {busy === "pi" ? t("soc.saving") : t("po.bill")}
                  </button>
                  )}
                  {canChange && !held && (
                    <>
                      <input
                        className="ctl"
                        value={holdReason}
                        aria-label="Reason for hold"
                        onChange={(event) => setHoldReason(event.target.value)}
                      />
                      <button type="button" className="btn ghost" disabled={setStatus.loading || !holdReason.trim()} onClick={() => void changeStatus("On Hold", holdReason)}>
                        {t("supp.onHold")}
                      </button>
                    </>
                  )}
                  {canChange && held && (
                    <button type="button" className="btn ghost" disabled={setStatus.loading} onClick={() => void changeStatus("Draft")}>
                      Resume
                    </button>
                  )}
                  {canChange && (
                    <button type="button" className="btn ghost" disabled={setStatus.loading} onClick={() => void changeStatus("Closed")}>
                      {t("hist.close")}
                    </button>
                  )}
                  {canDropship && (
                    <button type="button" className="btn ghost" onClick={() => setDropRows(lines.filter((row) => row.delivered_by_supplier && row.name).map((row) => ({
                      name: row.name || "",
                      item_code: row.item_code,
                      qty: row.qty,
                      received_qty: row.received_qty,
                      qty_change: Number(row.qty || 0) - Number(row.received_qty || 0),
                      selected: Number(row.qty || 0) > Number(row.received_qty || 0),
                    })))}>
                      Deliver
                    </button>
                  )}
                  {data.docstatus === 1 && data.status !== "Closed" && (data.per_billed ?? 0) < 100 && (
                    <button type="button" className="btn ghost"
                      onClick={() => nav(`/payments/new?dt=${encodeURIComponent(DT.purchaseOrder)}&dn=${encodeURIComponent(name)}`)}>
                      {t("pi.pay")}
                    </button>
                  )}
                  {data.docstatus === 1 && !held && data.status !== "Closed" && (data.per_billed ?? 0) < 100 && (
                    <button type="button" className="btn ghost" disabled={paymentRequest.busy}
                      onClick={() => void paymentRequest.open(() => makePayReq.call({ reference_doctype: DT.purchaseOrder, reference_name: name }))}>
                      Payment Request
                    </button>
                  )}
                  {data.docstatus === 1 && !held && data.status !== "Closed" && !!data.is_subcontracted && !data.is_old_subcontracting_flow
                    && (data.items ?? []).some((row) => !row.delivered_by_supplier && Number(row.received_qty || 0) < Number(row.qty || 0))
                    && (data.items ?? []).some((row) => Number(row.qty) !== Number(row.subcontracted_qty || 0)) && (
                    <button type="button" className="btn ghost" disabled={subcontract.busy}
                      onClick={() => void subcontract.open(() => makeSub.call({ source_name: name }))}>
                      Subcontracting Order
                    </button>
                  )}
                  {writable && data.docstatus === 1 && stopped && (
                    <button type="button" className="btn ghost" disabled={setStatus.loading} onClick={() => void changeStatus("Submitted")}>
                      Re-open
                    </button>
                  )}
                </>
              }
            />
          ) : null
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={poPill(data.status)}>{data.status || "—"}</Pill>
        </p>
      </PageHead>

      {(mapError || statusError || makePr.error || makePi.error || paymentRequest.error || subcontract.error) && (
        <ErrorBox error={submitCall.error ?? cancelCall.error ?? amendCall.error ?? statusError ?? mapError ?? makePr.error ?? makePi.error ?? paymentRequest.error ?? subcontract.error} />
      )}

      <FormLayout
        aside={
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("dn.summary")}</h2>
            <ReadRow k={t("so.col.orderDate")} v={date(data.transaction_date)} />
            <ReadRow k={t("po.required")} v={date(data.schedule_date)} />
            <ReadRow k={t("mr.received")} v={`${Number(data.per_received || 0)}%`} />
            <ReadRow k={t("stage.billed")} v={`${Number(data.per_billed || 0)}%`} />
            <TxnTotals
              currency={cur}
              itemsTotal={data.total}
              productDiscount={productDiscountTotal(lines)}
              orderDiscount={data.discount_amount}
              orderDiscountPercent={data.additional_discount_percentage}
              discountOn={readDiscountBasis(data.apply_discount_on, Number(data.discount_amount) > 0)}
              net={data.net_total}
              vat={data.total_taxes_and_charges}
              grand={data.grand_total}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("sod.grand")}
            />
            {returnedQty > 0 && <p className="sub" style={{ margin: "12px 0 0" }}>{t("po.returnNote")}</p>}
          </Card>
        }
      >
        {writable && data.docstatus === 1 && data.status !== "Closed" && data.status !== "Delivered"
          && (data.per_received ?? 0) < 100 && (data.per_billed ?? 0) < 100 && (
          <UpdateItems doctype={DT.purchaseOrder} name={name} items={lines} onSaved={() => void mutate()} />
        )}
        {dropRows && (
          <Card title="Deliver">
            {dropRows.map((row, index) => (
              <div key={row.name} className="grid3" style={{ marginBottom: 8 }}>
                <label className="ctl">
                  <input type="checkbox" checked={row.selected} aria-label={row.item_code || "Item"}
                    onChange={(event) => setDropRows((current) => (current ?? []).map((item, i) => i === index ? { ...item, selected: event.target.checked } : item))} />
                  {" "}{row.item_code}
                </label>
                <span className="ctl readonly">{row.received_qty ?? 0} / {row.qty ?? 0}</span>
                <input className="ctl" type="number" aria-label="Quantity" value={row.qty_change}
                  onChange={(event) => setDropRows((current) => (current ?? []).map((item, i) => i === index ? { ...item, qty_change: Number(event.target.value) } : item))} />
              </div>
            ))}
            <button type="button" className="btn" disabled={dropshipCall.loading} onClick={() => void saveDropship()}>{t("soc.save")}</button>
            <button type="button" className="btn ghost" onClick={() => setDropRows(null)}>{t("soc.discard")}</button>
          </Card>
        )}
        <Card title={t("dn.items")}>
          {/* Read-only progress against the order: ordered, received, billed.
              Nothing is added or removed here, and collapse={false} keeps the
              received and billed figures — the reason to open this screen —
              on the card rather than behind "More". */}
          <LineItems<Line>
            rows={lines}
            collapse={false}
            fields={[
              {
                key: "item", label: t("dn.item"), slot: "title",
                render: (row) => row.item_name || row.item_code,
              },
              {
                key: "qty", label: t("dn.qty"), slot: "primary", numeric: true,
                render: (row) => <>{qty(row.qty)} {row.uom}</>,
              },
              {
                key: "rate", label: t("sod.col.rate"), numeric: true,
                render: (row) => money(row.rate),
              },
              {
                key: "received", label: t("po.received"), numeric: true,
                render: (row) => qty(row.received_qty),
              },
              {
                key: "returned", label: t("po.returned"), numeric: true,
                render: (row) => qty(row.returned_qty),
              },
              {
                key: "billed", label: t("po.billed"), numeric: true,
                render: (row) => money(row.billed_amt),
              },
              ...(showLineDiscount ? [{
                key: "discount", label: t("txn.lineDiscount"), numeric: true,
                render: (row: Line) => formatLineDiscount(row),
              }] : []),
              {
                key: "amount", label: t("dn.amount"), slot: "primary", numeric: true, tdClass: "tot",
                render: (row) => money(row.amount),
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
