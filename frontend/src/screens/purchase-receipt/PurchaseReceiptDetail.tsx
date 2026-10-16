/**
 * Purchase Receipt detail — submit, cancel, edit draft, PR → PI.
 * Callers: App.tsx /purchase-receipts/:name.
 * API: METHOD.submit, METHOD.cancel, METHOD.makePrPurchaseInvoice; insert Purchase Invoice.
 * Schema: Doc { name, supplier, docstatus, per_billed, items[] }.
 * User instruction: "Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself. … Don't stop until you have completed all the to-dos."
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { printDocUrl } from "../../lib/printDoc";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { TxnTotals } from "../../components/txnFields";
import { productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { isNative } from "../../mobile/platform";

type Line = { item_code?: string; item_name?: string; qty?: number; uom?: string; rate?: number; amount?: number; warehouse?: string; price_list_rate?: number; discount_percentage?: number; discount_amount?: number };
type Doc = {
  name: string; supplier?: string; supplier_name?: string; posting_date?: string;
  company?: string; status?: string; currency?: string; docstatus?: number;
  total?: number; grand_total?: number; net_total?: number; total_taxes_and_charges?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  per_billed?: number; is_return?: number; set_warehouse?: string; items?: Line[];
};

function prPill(status?: string): string {
  if (status === "Draft") return "p-draft";
  if (status === "Completed") return "p-done";
  if (status === "Cancelled" || status === "Closed") return "p-cxl";
  if (status === "Return" || status === "Return Issued") return "p-warn";
  return "p-open";
}

export default function PurchaseReceiptDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.purchaseReceipt, name, listPath: "/purchase-receipts" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.purchaseReceipt, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const makePi = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePrPurchaseInvoice);
  const create = useInsert();
  const [busyPi, setBusyPi] = useState(false);
  const [mapError, setMapError] = useState<unknown>(null);

  async function createInvoice() {
    setBusyPi(true);
    setMapError(null);
    try {
      const res = await makePi.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("doc.err.mapFailed"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.purchaseInvoice, body) as { name: string };
      nav(`/purchase-invoices/${encodeURIComponent(created.name)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusyPi(false);
    }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.currency || session.currency || "";
  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const writable = canWrite(session);
  const busyError = deleteAction.error || submitCall.error || cancelCall.error || makePi.error || mapError;

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/purchase-receipts")}>
            {t("nav.purchaseReceipts")}
          </button>
        }
        title={data.supplier_name || data.supplier || data.name}
        actions={
          <DetailActions
            doctype={DT.purchaseReceipt}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={writable}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || busyPi || deleteAction.loading}
            onEdit={() => nav(`/purchase-receipts/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.purchaseReceipt, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.purchaseReceipt, name }).then(() => mutate())}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.purchaseReceipt, name });
              const newName = res?.message?.name;
              if (newName) nav(`/purchase-receipts/${encodeURIComponent(newName)}/edit`);
              else mutate();
            }}
            extra={
              <>
                {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                {!isNative() && (
                <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.purchaseReceipt, name), "_blank", "noopener")}>
                  {t("inv.print")}
                </button>
                )}
                {submitted && writable && (data.per_billed ?? 0) < 100 && (
                  <button type="button" className="btn" disabled={busyPi} onClick={() => void createInvoice()}>
                    {busyPi ? t("soc.saving") : t("pr.createPi")}
                  </button>
                )}
                {submitted && !data.is_return && writable && (
                  <button type="button" className="btn ghost"
                    onClick={() => nav(`/purchase-receipts/${encodeURIComponent(name)}/return`)}>
                    {t("pr.return")}
                  </button>
                )}
              </>
            }
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={prPill(data.status)}>{data.status || "—"}</Pill>
        </p>
      </PageHead>

      {busyError && <ErrorBox error={busyError} />}

      <FormLayout
        aside={
          <Card title={t("dn.summary")}>
            <ReadRow k={t("inv.col.date")} v={date(data.posting_date)} />
            <ReadRow k={t("nav.warehouses")} v={data.set_warehouse || "—"} />
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
            />
          </Card>
        }
      >
        <Card title={t("dn.items")}>
          {/* What was received, read-only. No add or remove, and
              collapse={false} so the warehouse stays visible on a phone. */}
          <LineItems<Line>
            rows={data.items ?? []}
            collapse={false}
            fields={[
              {
                key: "item", label: t("dn.item"), slot: "title",
                render: (row) => row.item_name || row.item_code,
              },
              {
                key: "warehouse", label: t("nav.warehouses"),
                render: (row) => row.warehouse || data.set_warehouse || "—",
              },
              {
                key: "qty", label: t("dn.qty"), slot: "primary", numeric: true,
                render: (row) => <>{qty(row.qty)} {row.uom}</>,
              },
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
