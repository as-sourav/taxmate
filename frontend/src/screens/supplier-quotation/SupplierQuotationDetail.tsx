/**
 * SupplierQuotationDetail — Phase 16.
 * Callers: App.tsx /supplier-quotations/:name
 * API: taxmate.api.resource.get on "Supplier Quotation"
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { printDocUrl } from "../../lib/printDoc";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { confirmCancel } from "../../lib/workflow";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import { TxnTotals } from "../../components/txnFields";
import { productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import DocHistory from "../../components/DocHistory";
import UpdateItems from "../../components/UpdateItems";
import LineItems, { type LineField } from "../../components/LineItems";
import { isNative } from "../../mobile/platform";

type Line = {
  item_code?: string; item_name?: string; qty?: number; rate?: number; amount?: number; uom?: string;
  price_list_rate?: number; discount_percentage?: number; discount_amount?: number;
};
type Doc = {
  name: string; supplier?: string; supplier_name?: string; transaction_date?: string;
  valid_till?: string; status?: string; total?: number; grand_total?: number; net_total?: number;
  total_taxes_and_charges?: number; currency?: string; docstatus?: number; items?: Line[];
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
};

function sqPill(status?: string): string {
  if (!status || status === "Draft") return "p-draft";
  if (status === "Ordered") return "p-done";
  if (status === "Cancelled" || status === "Expired") return "p-cxl";
  return "p-open";
}

export default function SupplierQuotationDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.supplierQuotation, name, listPath: "/supplier-quotations" });
  const nav = useNavigate();
  const session = useSession();
  const writable = canWrite(session);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.supplierQuotation, name);
  const makePo = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSupplierQuotationPO);
  const makeQuote = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSupplierQuotationQuotation);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const create = useInsert();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  async function createPO() {
    setBusy(true);
    setActionError(null);
    try {
      const res = await makePo.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("doc.err.mapFailed"));
      const body: Record<string, unknown> = { ...(mapped as Record<string, unknown>) };
      delete body.name; delete body.doctype; delete body.__islocal; delete body.__unsaved;
      const created = await create.createDoc(DT.purchaseOrder, body);
      nav(`/purchase-orders/${encodeURIComponent((created as { name: string }).name)}`);
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  async function createQuotation() {
    setBusy(true);
    setActionError(null);
    try {
      const res = await makeQuote.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("doc.err.mapFailed"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name; delete body.doctype; delete body.__islocal; delete body.__unsaved;
      nav("/quotations/new", { state: { mapped: body } });
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  async function doSubmit() {
    setBusy(true); setActionError(null);
    try { await submitCall.call({ doc: { doctype: DT.supplierQuotation, name } }); mutate(); }
    catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  async function doCancel() {
    if (!confirmCancel(name)) return;
    setBusy(true); setActionError(null);
    try { await cancelCall.call({ doctype: DT.supplierQuotation, name }); mutate(); }
    catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  async function doAmend() {
    setBusy(true); setActionError(null);
    try {
      const res = await amendCall.call({ doctype: DT.supplierQuotation, name });
      const next = res?.message?.name;
      if (next) nav(`/supplier-quotations/${encodeURIComponent(next)}`);
      else mutate();
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.currency || "";

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/supplier-quotations")}>{t("sq.title")}</button>}
        title={data.name}
        actions={<DocHistory doctype={DT.supplierQuotation} name={name} />}
      >
        <Pill cls={sqPill(data.status)}>{data.status || "Draft"}</Pill>
        {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
        {!isNative() && (
        <button type="button" className="btn ghost" onClick={() => window.open(printDocUrl(DT.supplierQuotation, name), "_blank", "noopener")}>
          {t("inv.print")}
        </button>
        )}
        {writable && data.docstatus === 0 && (
          <>
            <button className="btn ghost" onClick={() => nav(`/supplier-quotations/${encodeURIComponent(name)}/edit`)}>{t("edit")}</button>
            {canSubmit && (
            <button className="btn" onClick={() => void doSubmit()} disabled={busy}>{t("sq.submit")}</button>
            )}
            <button type="button" className="btn quiet" disabled={deleteAction.loading || busy}
              onClick={deleteAction.onDelete}>
              {deleteAction.loading ? t("soc.saving") : t("inv.delete")}
            </button>
          </>
        )}
        {data.docstatus === 1 && (
          <>
            {writable && (
            <>
            <button className="btn" onClick={() => void createPO()} disabled={busy}>{t("sq.makePO")}</button>
            <button className="btn ghost" onClick={() => void createQuotation()} disabled={busy}>{t("nav.quotations")}</button>
            </>
            )}
            {canCancel && (
            <button className="btn ghost" onClick={() => void doCancel()} disabled={busy}>{t("sq.cancel")}</button>
            )}
          </>
        )}
        {canSubmit && data.docstatus === 2 && (
          <button className="btn ghost" onClick={() => void doAmend()} disabled={busy}>{t("inv.amend")}</button>
        )}
      </PageHead>
      {actionError ? <ErrorBox error={actionError} /> : null}
      <Card>
        <div className="fg">
          <ReadRow k={t("sq.col.supplier")} v={data.supplier_name || data.supplier || "—"} />
          <ReadRow k={t("sq.col.date")} v={date(data.transaction_date)} />
          <ReadRow k={t("sq.col.validTill")} v={date(data.valid_till)} />
        </div>
      </Card>
      {data.docstatus === 1 && writable && (
        <UpdateItems doctype={DT.supplierQuotation} name={name} items={data.items ?? []} onSaved={() => void mutate()} />
      )}
      <Card title={t("sq.items")}>
        {/* Read-only quotation lines: no add, no remove, collapse off. The
            SumRows below were never a <tfoot> — they stay card siblings. */}
        <LineItems<Line>
          rows={data.items ?? []}
          collapse={false}
          fields={[
            {
              key: "item", label: t("sq.col.item"), slot: "title",
              render: (l) => <>{l.item_name || l.item_code || "—"}</>,
            },
            {
              key: "qty", label: t("sq.col.qty"), slot: "primary", numeric: true,
              render: (l) => <>{l.qty}</>,
            },
            {
              key: "rate", label: t("sq.col.rate"), numeric: true,
              render: (l) => <>{cur} {money(l.rate)}</>,
            },
            {
              key: "amount", label: t("sq.col.amount"), slot: "primary", numeric: true,
              tdClass: "tot",
              render: (l) => <>{cur} {money(l.amount)}</>,
            },
          ] as LineField<Line>[]}
        />
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
          vatLabel={t("sq.taxes")}
          grandLabel={t("sq.total")}
        />
      </Card>
    </>
  );
}
