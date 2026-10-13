/**
 * Quotation detail. Importers: App.tsx.
 * API: taxmate.api.resource.get; taxmate.api.quotation.make_sales_order; workflow submit/cancel.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales } from "../../lib/roles";
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

type Line = { item_code?: string; item_name?: string; qty?: number; uom?: string; rate?: number; amount?: number; price_list_rate?: number; discount_percentage?: number; discount_amount?: number; };
type Doc = {
  name: string; party_name?: string; customer_name?: string; transaction_date?: string;
  valid_till?: string; status?: string; total?: number; grand_total?: number; net_total?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  total_taxes_and_charges?: number; vat_emirate?: string; docstatus?: number; items?: Line[];
};

function quotPill(status?: string): string {
  if (status === "Cancelled") return "p-cxl";
  if (status === "Ordered") return "p-done";
  if (status === "Open") return "p-open";
  return "p-draft";
}

export default function QuotationDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.quotation, name, listPath: "/quotations" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.quotation, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const makeSO = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeQuotationSO);
  const [mapBusy, setMapBusy] = useState(false);
  const [mapError, setMapError] = useState<unknown>(null);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;

  // Delivery Date is mandatory on Sales Order, not Quotation. Open the SO
  // form with the mapped draft (same pattern as Material Request → PO) so
  // the operator can confirm or change the date without amending the Quotation.
  async function createSO() {
    setMapBusy(true); setMapError(null);
    try {
      const res = await makeSO.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("txn.mapEmpty"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      nav("/orders/new", { state: { mapped: body } });
    } catch (err) {
      setMapError(err);
    } finally {
      setMapBusy(false);
    }
  }

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/quotations")}>{t("nav.quotations")}</button>}
        title={data.customer_name || data.party_name || data.name}
        actions={
          <DetailActions
            doctype={DT.quotation}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={true}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || mapBusy || deleteAction.loading}
            onEdit={() => nav(`/quotations/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.quotation, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.quotation, name }).then(() => mutate())}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.quotation, name });
              const newName = res?.message?.name;
              if (newName) nav(`/quotations/${encodeURIComponent(newName)}/edit`);
              else mutate();
            }}
            extra={
              <>
                {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                {!isNative() && (
                <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.quotation, name), "_blank", "noopener")}>
                  {t("inv.print")}
                </button>
                )}
                {submitted ? (
                  <button type="button" className="btn" disabled={mapBusy}
                    onClick={() => void createSO()}>
                    {mapBusy ? t("soc.saving") : t("quot.makeSO")}
                  </button>
                ) : null}
              </>
            }
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={quotPill(data.status)}>{data.status || t("pay.status.Draft")}</Pill>
        </p>
      </PageHead>

      {(submitCall.error || cancelCall.error || mapError) && (
        <ErrorBox error={submitCall.error || cancelCall.error || mapError} />
      )}

      <FormLayout aside={
        <Card bodyClass="cbody">
          <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("quot.summary")}</h2>
          <TxnTotals
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
      }>
        <Card>
          <div className="fg">
            <ReadRow k={t("quot.customer")} v={data.customer_name || data.party_name || "—"} />
            <ReadRow k={t("quot.date")} v={date(data.transaction_date)} />
            <ReadRow k={t("quot.validTill")} v={date(data.valid_till)} />
            <ReadRow k={t("f.emirate")} v={data.vat_emirate || "—"} />
          </div>
        </Card>
        <Card title={t("inv.lines")}>
          {/* The quoted lines, read-only — the quotation is edited on its own
              form. collapse={false} keeps the rate on the card. */}
          <LineItems<Line>
            rows={data.items ?? []}
            showIndex
            collapse={false}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title",
                render: (l) => <><div className="icode">{l.item_code}</div><div className="iname">{l.item_name}</div></>,
              },
              {
                key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                render: (l) => <>{qty(l.qty)}<div style={{ fontSize: 11, color: "var(--faint)" }}>{l.uom}</div></>,
              },
              {
                key: "rate", label: t("sod.col.rate"), numeric: true,
                render: (l) => money(l.rate),
              },
              {
                key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                td: { fontWeight: 600 },
                render: (l) => money(l.amount),
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
