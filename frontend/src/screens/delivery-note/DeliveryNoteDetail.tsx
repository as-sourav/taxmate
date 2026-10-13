/**
 * Delivery Note detail — submit, cancel, and bill (DN → SI).
 * Route: App.tsx /delivery-notes/:name. API: METHOD.submit/cancel/makeDnSalesInvoice.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
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
import { printDocUrl } from "../../lib/printDoc";
import { isNative } from "../../mobile/platform";

type Line = { item_code?: string; item_name?: string; qty?: number; uom?: string; rate?: number; amount?: number; warehouse?: string; price_list_rate?: number; discount_percentage?: number; discount_amount?: number };
type Doc = {
  name: string; customer?: string; customer_name?: string; posting_date?: string;
  company?: string; status?: string; docstatus?: number; currency?: string;
  total?: number; grand_total?: number; net_total?: number; total_taxes_and_charges?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  per_billed?: number; is_return?: number; set_warehouse?: string; items?: Line[];
};

function dnPill(status?: string): string {
  if (status === "Draft") return "p-draft";
  if (status === "Completed") return "p-done";
  if (status === "Cancelled" || status === "Closed") return "p-cxl";
  if (status === "Return" || status === "Return Issued") return "p-warn";
  return "p-open";
}

export default function DeliveryNoteDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.deliveryNote, name, listPath: "/delivery-notes" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.deliveryNote, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const makePickList = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makePickListFromDn);
  const makeSi = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeDnSalesInvoice);
  const create = useInsert();
  const [busySi, setBusySi] = useState(false);
  const [busyPick, setBusyPick] = useState(false);
  const [mapError, setMapError] = useState<unknown>(null);

  async function createInvoice() {
    setBusySi(true);
    setMapError(null);
    try {
      const res = await makeSi.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error("The mapper returned nothing.");
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.salesInvoice, body) as { name: string };
      nav(`/invoices/${encodeURIComponent(created.name)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusySi(false);
    }
  }

  async function createPickList() {
    setBusyPick(true);
    setMapError(null);
    try {
      const res = await makePickList.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error("The mapper returned nothing.");
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.pickList, body) as { name: string };
      nav(`/pick-lists/${encodeURIComponent(created.name)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusyPick(false);
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
  const busyError = deleteAction.error || submitCall.error || cancelCall.error || makeSi.error || makePickList.error || mapError;

  return (
    <>
      <PageHead
        title={data.customer_name || data.customer || data.name}
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/delivery-notes")}>
            {t("dn.title")}
          </button>
        }
        actions={
          <DetailActions
            doctype={DT.deliveryNote}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={writable}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || busySi || busyPick || deleteAction.loading}
            onEdit={() => nav(`/delivery-notes/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.deliveryNote, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.deliveryNote, name }).then(() => mutate())}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.deliveryNote, name });
              const newName = res?.message?.name;
              if (newName) nav(`/delivery-notes/${encodeURIComponent(newName)}/edit`);
              else mutate();
            }}
            extra={
              <>
                {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                {!isNative() && (
                <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.deliveryNote, name), "_blank", "noopener")}>
                  {t("inv.print")}
                </button>
                )}
                {submitted && writable && (data.per_billed ?? 0) < 100 && (
                  <button type="button" className="btn" disabled={busySi} onClick={() => void createInvoice()}>
                    {busySi ? t("soc.saving") : t("dn.createSi")}
                  </button>
                )}
                {submitted && writable && (
                  <button type="button" className="btn ghost" disabled={busyPick} onClick={() => void createPickList()}>
                    {busyPick ? t("soc.saving") : t("dn.createPickList")}
                  </button>
                )}
                {submitted && !data.is_return && writable && (
                  <button type="button" className="btn ghost"
                    onClick={() => nav(`/delivery-notes/${encodeURIComponent(name)}/return`)}>
                    {t("dn.return")}
                  </button>
                )}
              </>
            }
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={dnPill(data.status)}>{data.status || "—"}</Pill>
        </p>
      </PageHead>

      {busyError && <ErrorBox error={busyError} />}

      <FormLayout
        aside={
          <Card title={t("dn.summary")}>
            <ReadRow k={t("dn.date")} v={date(data.posting_date)} />
            <ReadRow k={t("dn.status")} v={data.status} />
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
              netLabel={t("dn.net")}
              vatLabel={t("dn.tax")}
              grandLabel={t("dn.grand")}
            />
          </Card>
        }
      >
        <Card title={t("dn.items")}>
          {/* A delivered note's lines are read-only here — no add, no remove —
              and on a phone the warehouse stays on the card rather than behind
              a "More" toggle. */}
          <LineItems<Line>
            rows={data.items ?? []}
            collapse={false}
            fields={[
              {
                key: "item", label: t("dn.item"), slot: "title",
                render: (row) => <>{row.item_name || row.item_code}</>,
              },
              {
                key: "warehouse", label: t("dn.warehouse"),
                render: (row) => <>{row.warehouse || data.set_warehouse || "—"}</>,
              },
              {
                key: "qty", label: t("dn.qty"), slot: "primary", numeric: true,
                render: (row) => <>{qty(row.qty)} {row.uom}</>,
              },
              {
                key: "amount", label: t("dn.amount"), slot: "primary", numeric: true, tdClass: "tot",
                render: (row) => <>{money(row.amount)}</>,
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
