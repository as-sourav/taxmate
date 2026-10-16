import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  useFrappeGetCall, useFrappePostCall,
} from "frappe-react-sdk";

import type { SalesOrder, SalesOrderItem } from "../../types/erpnext";
import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales } from "../../lib/roles";
import { date, money, pct, qty } from "../../lib/format";
import { SO_PILL_CLASS, isLate, toUiStatus } from "../../lib/status";
import { t } from "../../i18n/strings";
import { TxnTotals } from "../../components/txnFields";
import { productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import { Card, ErrorBox, Loading, MiniBar, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { printDocUrl } from "../../lib/printDoc";
import { isNative } from "../../mobile/platform";

type Doc = SalesOrder & { items: SalesOrderItem[] };

export default function SalesOrderDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.salesOrder, name, listPath: "/orders" });
  const nav = useNavigate();

  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.salesOrder, name);

  /* Delivery notes and invoices raised against this order. The link lives on
     the child rows, but listing a child doctype straight from the client is
     refused by has_child_permission (frappe/permissions.py:837) — it came
     back 403 and the panel rendered empty, which reads as "none". The server
     method filters the parent doctypes instead.                          */
  const links = useFrappeGetCall<{ message: { delivery_notes: string[]; sales_invoices: string[] } }>(
    METHOD.salesOrderLinks,
    { sales_order: name },
    name ? `so-links-${name}` : null,
  );

  /* Both mappers return an UNSAVED document — verified in ERPNext v16
     (sales_order.py:1356, :1172). Mapping alone leaves nothing behind, so
     each button maps, inserts the draft, then opens it.                   */
  const makeDn = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeDeliveryNote);
  const makeSi = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSalesInvoice);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const create = useInsert();
  const session = useSession();
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const [busy, setBusy] = useState<"" | "dn" | "si">("");
  const [mapError, setMapError] = useState<unknown>(null);

  async function createDownstream(kind: "dn" | "si") {
    setBusy(kind);
    setMapError(null);
    try {
      const call = kind === "dn" ? makeDn.call : makeSi.call;
      const doctype = kind === "dn" ? DT.deliveryNote : DT.salesInvoice;
      const res = await call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("doc.err.mapFailed"));
      /* The mapped doc carries a placeholder name and local-only flags — drop
         them so the insert autonames instead of colliding.                 */
      const body: Record<string, unknown> = { ...(mapped as Record<string, unknown>) };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(doctype, body);
      const newName = (created as { name: string }).name;
      if (kind === "si") nav(`/invoices/${encodeURIComponent(newName)}`);
      else nav(`/delivery-notes/${encodeURIComponent(newName)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const ui = toUiStatus(data.status);
  const late = isLate(data);
  const vat = data.total_taxes_and_charges ?? 0;
  const net = data.net_total ?? 0;
  const grand = data.grand_total ?? 0;
  const advance = data.advance_paid ?? 0;

  const linked: { name: string; kind: "dn" | "si" }[] = [
    ...(links.data?.message?.delivery_notes ?? []).map((n) => ({ name: n, kind: "dn" as const })),
    ...(links.data?.message?.sales_invoices ?? []).map((n) => ({ name: n, kind: "si" as const })),
  ];

  return (
    <>
      <PageHead
        eyebrow={
          <>
            <button type="button" className="btn quiet" onClick={() => nav("/orders")}>
              {t("nav.salesOrders")}
            </button>{" / "}{data.name}
          </>
        }
        title={data.customer_name || data.customer}
        actions={
          <DetailActions
            doctype={DT.salesOrder}
            name={name}
            draft={data.docstatus === 0}
            submitted={data.docstatus === 1}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={true}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || !!busy || deleteAction.loading}
            onEdit={() => nav(`/orders/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.salesOrder, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.salesOrder, name }).then(() => mutate())}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.salesOrder, name });
              const newName = res?.message?.name;
              if (newName) nav(`/orders/${encodeURIComponent(newName)}/edit`);
              else mutate();
            }}
            extra={
              <>
                {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                {!isNative() && (
                <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.salesOrder, name), "_blank", "noopener")}>
                  {t("inv.print")}
                </button>
                )}
                {/* Same gate ERPNext's own buttons use: at 100% every row's
                    mapper condition is false and the result has no items.   */}
                <button type="button" className="btn ghost"
                  disabled={!!busy || data.docstatus !== 1 || (data.per_delivered ?? 0) >= 100}
                  onClick={() => void createDownstream("dn")}>
                  {busy === "dn" ? t("soc.saving") : t("sod.createDn")}
                </button>
                <button type="button" className="btn"
                  disabled={!!busy || data.docstatus !== 1 || (data.per_billed ?? 0) >= 100}
                  onClick={() => void createDownstream("si")}>
                  {busy === "si" ? t("soc.saving") : t("sod.createSi")}
                </button>
                {data.docstatus === 1 && (
                  <button type="button" className="btn ghost"
                    onClick={() => nav(`/payments/new?type=Receive&party=${encodeURIComponent(data.customer || "")}`)}>
                    {t("sod.createPayment")}
                  </button>
                )}
              </>
            }
          />
        }
      >
        <p className="sub" style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginTop: 7 }}>
          <Pill cls={SO_PILL_CLASS[ui]}>{t(`status.${ui}`)}</Pill>
          {late && <Pill cls="p-overdue">{t("so.late")}</Pill>}
          {data.po_no && <span className="pill p-flat">{t("txn.poLabel")} · {data.po_no}</span>}
        </p>
      </PageHead>

      {(mapError || makeDn.error || makeSi.error) && (
        <ErrorBox error={mapError ?? makeDn.error ?? makeSi.error} />
      )}

      <Card bodyClass="steps">
        <Step colour="var(--c-draft)" mark="✓" name={t("stage.draft")} value={date(data.transaction_date)} pctv={100} />
        <Step colour="var(--c-confirmed)" mark={data.docstatus === 1 ? "✓" : "○"} name={t("stage.confirmed")}
          value={data.docstatus === 1 ? date(data.transaction_date) : "—"} pctv={data.docstatus === 1 ? 100 : 0} />
        <Step colour="var(--c-delivered)" mark="◐" name={t("stage.delivered")}
          value={pct(data.per_delivered)} pctv={data.per_delivered ?? 0} />
        <Step colour="var(--c-billed)" mark="◔" name={t("stage.billed")}
          value={pct(data.per_billed)} pctv={data.per_billed ?? 0} />
      </Card>

      <FormLayout aside={
        <>
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("sod.value")}</h2>
            <TxnTotals
              itemsTotal={data.total}
              productDiscount={productDiscountTotal(data.items ?? [])}
              orderDiscount={data.discount_amount}
              orderDiscountPercent={data.additional_discount_percentage}
              discountOn={readDiscountBasis(data.apply_discount_on, Number(data.discount_amount) > 0)}
              net={net}
              vat={vat}
              grand={grand}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("sod.grand")}
            />
            {advance > 0 && <SumRow k={t("sod.advance")} v={money(advance)} cls="rule" />}
          </Card>

          <Card title={t("sod.linked")} bodyClass="cbody">
            {links.error ? (
              <ErrorBox error={links.error} onRetry={() => links.mutate()} />
            ) : links.isLoading ? (
              <Loading />
            ) : linked.length === 0 ? (
              <span style={{ fontSize: 12.5, color: "var(--faint)" }}>—</span>
            ) : (
              linked.map((p) => (
                <div key={p.name} className="mono" style={{ fontSize: 12 }}>
                  {p.kind === "si" ? (
                    <button type="button" className="btn quiet"
                       onClick={() => nav(`/invoices/${encodeURIComponent(p.name)}`)}>{p.name}</button>
                  ) : (
                    <button type="button" className="btn quiet"
                       onClick={() => nav(`/delivery-notes/${encodeURIComponent(p.name)}`)}>{p.name}</button>
                  )}
                </div>
              ))
            )}
          </Card>
        </>
      }>
          <Card title={t("sod.details")}>
            <div className="fg">
              <ReadRow k={t("f.customer")} v={data.customer_name || data.customer} link />
              <ReadRow k={t("f.customerTrn")} v={<span className="mono">{data.tax_id || "—"}</span>} />
              <ReadRow k={t("f.address")} v={data.customer_address || "—"} />
              <ReadRow k={t("f.orderDate")} v={date(data.transaction_date)} />
              <ReadRow k={t("f.deliveryDate")} v={date(data.delivery_date)} />
              <ReadRow k={t("f.paymentTerms")} v={data.payment_terms_template || "—"} />
              <ReadRow k={t("f.taxTemplate")} v={data.taxes_and_charges || "—"} />
              <ReadRow k={t("f.emirate")} v={(data as unknown as Record<string, string>).vat_emirate || "—"} />
              <ReadRow k={t("f.priceList")} v={data.selling_price_list || "—"} />
            </div>
          </Card>

          {/* bodyClass={null}: LineItems renders its own `.twrap`, so the card
              must not render a second one. Read-only — the order is edited on
              its form — and collapse={false} so delivery progress and the
              remaining quantity stay on the card, which is most of why anyone
              opens this screen on a phone. */}
          <Card title={t("sod.items")} bodyClass={null}>
            <LineItems<SalesOrderItem>
              rows={data.items ?? []}
              showIndex
              collapse={false}
              fields={[
                {
                  key: "item", label: t("soc.pickItem"), slot: "title",
                  render: (l) => (
                    <>
                      <div className="icode">{l.item_code}</div>
                      <div className="iname">{l.item_name}</div>
                    </>
                  ),
                },
                {
                  key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                  render: (l) => <>{qty(l.qty ?? 0)}<div style={{ fontSize: 11, color: "var(--faint)" }}>{l.uom}</div></>,
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
                {
                  key: "delivered", label: t("so.bar.delivered"),
                  render: (l) => {
                    const delivered = l.delivered_qty ?? 0;
                    const ordered = l.qty ?? 0;
                    const p = ordered ? (delivered / ordered) * 100 : 0;
                    return (
                      <div className="prog">
                        <div className="row1">
                          <span className="a">{pct(p)}</span>
                          <span className="b">{qty(delivered)} / {qty(ordered)}</span>
                        </div>
                        <MiniBar value={p} colour="var(--c-delivered)" />
                      </div>
                    );
                  },
                },
                {
                  /* The only cell whose class varied per row (`rem zero` when
                     nothing is left, `rem open` otherwise). `tdClass` is one
                     static string, so the pair moves onto a span inside the
                     cell: `.rem.zero` / `.rem.open` are colour and weight
                     only, so they read the same there — and, unlike a
                     `tdClass`, they now also apply on a phone card. */
                  key: "remaining", label: t("sod.col.remaining"), numeric: true,
                  render: (l) => {
                    const remaining = Math.max(0, (l.qty ?? 0) - (l.delivered_qty ?? 0));
                    return (
                      <span className={`rem ${remaining === 0 ? "zero" : "open"}`}>
                        {remaining === 0 ? "—" : `${qty(remaining)} ${l.uom ?? ""}`}
                      </span>
                    );
                  },
                },
              ] as LineField<SalesOrderItem>[]}
              /* The net total the table carried in its <tfoot>: 4 + 1 + 2 = the
                 seven columns the index column makes. */
              footer={
                <tr>
                  <td colSpan={4} className="n">{t("sod.net")}</td>
                  <td className="n">{money(net)}</td>
                  <td colSpan={2} />
                </tr>
              }
              footerCard={<><span>{t("sod.net")}</span><span>{money(net)}</span></>}
            />
          </Card>
      </FormLayout>
    </>
  );
}

function Step({ colour, mark, name, value, pctv }: {
  colour: string; mark: string; name: string; value: string; pctv: number;
}) {
  return (
    <div className="step">
      <div className="top">
        <span className="dot" style={{ background: colour }}>{mark}</span>
        <span className="nm">{name}</span>
      </div>
      <span className="val">{value}</span>
      <div className="sbar"><i style={{ width: `${pctv}%`, background: colour }} /></div>
    </div>
  );
}
