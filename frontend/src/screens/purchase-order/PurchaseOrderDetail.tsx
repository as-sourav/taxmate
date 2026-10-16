import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canWrite } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { formatLineDiscount, TxnTotals } from "../../components/txnFields";
import { lineHasProductDiscount, productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { printDocUrl } from "../../lib/printDoc";
import { isNative } from "../../mobile/platform";

type Line = {
  item_code?: string; item_name?: string; qty?: number; received_qty?: number;
  returned_qty?: number;
  billed_amt?: number; uom?: string; rate?: number; amount?: number;
  price_list_rate?: number; discount_percentage?: number; discount_amount?: number;
};
type Doc = {
  name: string; supplier?: string; supplier_name?: string; transaction_date?: string;
  schedule_date?: string; company?: string; status?: string; currency?: string;
  total?: number; grand_total?: number; net_total?: number; total_taxes_and_charges?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  docstatus?: number; per_received?: number; per_billed?: number;
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
  const [busy, setBusy] = useState<"" | "pr" | "pi">("");
  const [mapError, setMapError] = useState<unknown>(null);

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
  const returnedValue = lines.reduce(
    (sum, row) => sum + (Number(row.returned_qty) || 0) * (Number(row.rate) || 0),
    0,
  );
  const receivedValue = lines.reduce(
    (sum, row) => sum + (Number(row.received_qty) || 0) * (Number(row.rate) || 0),
    0,
  );

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
              busy={submitCall.loading || cancelCall.loading || amendCall.loading || !!busy || deleteAction.loading}
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
                  <button type="button" className="btn ghost"
                    disabled={!!busy || data.docstatus !== 1 || (data.per_received ?? 0) >= 100}
                    onClick={() => void createDownstream("pr")}>
                    {busy === "pr" ? t("soc.saving") : t("po.receive")}
                  </button>
                  <button type="button" className="btn"
                    disabled={!!busy || data.docstatus !== 1 || (data.per_billed ?? 0) >= 100}
                    onClick={() => void createDownstream("pi")}>
                    {busy === "pi" ? t("soc.saving") : t("po.bill")}
                  </button>
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

      {(mapError || makePr.error || makePi.error) && (
        <ErrorBox error={mapError ?? makePr.error ?? makePi.error} />
      )}

      <FormLayout
        aside={
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("dn.summary")}</h2>
            <ReadRow k={t("so.col.orderDate")} v={date(data.transaction_date)} />
            <ReadRow k={t("po.required")} v={date(data.schedule_date)} />
            <TxnTotals
              currency={cur}
              itemsTotal={data.total}
              productDiscount={productDiscountTotal(data.items ?? [])}
              orderDiscount={data.discount_amount}
              orderDiscountPercent={data.additional_discount_percentage}
              discountOn={readDiscountBasis(data.apply_discount_on, Number(data.discount_amount) > 0)}
              net={data.net_total}
              vat={data.total_taxes_and_charges}
              grand={data.grand_total}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("sod.grand")}
            >
              {returnedValue > 0.004 && (
                <>
                  <SumRow k={t("po.returnedValue")} v={`−${money(returnedValue)}`} currency={cur} cls="discount" />
                  <SumRow k={t("po.receivedValue")} v={money(receivedValue)} currency={cur} />
                  <p className="sub" role="status">{t("po.returnNote")}</p>
                </>
              )}
            </TxnTotals>
          </Card>
        }
      >
        <Card title={t("dn.items")}>
          {/* Read-only progress against the order: ordered, received, billed.
              Nothing is added or removed here, and collapse={false} keeps the
              received and billed figures — the reason to open this screen —
              on the card rather than behind "More". */}
          <LineItems<Line>
            rows={data.items ?? []}
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
