/**
 * Landed Cost Voucher detail. Route: /landed-cost-vouchers/:name
 * API: useDoc on "Landed Cost Voucher". Submit/cancel via workflow.
 * Callers: App.tsx. Phase 8.
 */
import { useParams, useNavigate, Link } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";
import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { t } from "../../i18n/strings";
import { Card, Loading, ErrorBox, PageHead, Pill } from "../../components/ui";
import { money } from "../../lib/format";
import DetailActions from "../../components/DetailActions";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useState } from "react";

export default function LandedCostVoucherDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.landedCostVoucher, name, listPath: "/landed-cost-vouchers" });
  const nav = useNavigate();
  const session = useSession();
  const doc = useDoc<Record<string, unknown>>(DT.landedCostVoucher, name, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  if (doc.isLoading) return <Loading />;
  if (doc.error) return <ErrorBox error={doc.error} onRetry={() => doc.mutate()} />;
  const d = doc.data ?? {};
  const docstatus = Number(d.docstatus ?? 0);
  const isDraft = docstatus === 0;
  const isSubmitted = docstatus === 1;
  const canSubmitDoc = canSubmitSales(session.roles);
  const canCancelDoc = canCancelSales(session.roles);

  async function doAction(action: "submit" | "cancel") {
    setBusy(true); setErr(null);
    try {
      if (action === "submit") {
        await submitCall.call({ doc: { doctype: DT.landedCostVoucher, name } });
      } else {
        await cancelCall.call({ doctype: DT.landedCostVoucher, name });
      }
      await doc.mutate();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }

  async function amend() {
    setBusy(true); setErr(null);
    try {
      const res = await amendCall.call({ doctype: DT.landedCostVoucher, name });
      const next = res?.message?.name;
      if (next) nav(`/landed-cost-vouchers/${encodeURIComponent(next)}`);
      else await doc.mutate();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }

  const receipts = (d.purchase_receipts as unknown[]) ?? [];
  const taxes = (d.taxes as unknown[]) ?? [];
  const items = (d.items as unknown[]) ?? [];

  const statusCls = docstatus === 1 ? "p-submitted" : docstatus === 2 ? "p-cancelled" : "p-draft";
  const statusLabel = docstatus === 1 ? "Submitted" : docstatus === 2 ? "Cancelled" : "Draft";

  return (
    <>
      <PageHead
        title={name}
        eyebrow={<Link to="/landed-cost-vouchers">{t("lcv.title")}</Link>}
        actions={
          <>
            <Pill cls={statusCls}>{statusLabel}</Pill>
            <DetailActions
            doctype={DT.landedCostVoucher}
            name={name}
              draft={isDraft}
              submitted={isSubmitted}
              cancelled={docstatus === 2}
              canWrite={canWrite(session)}
              canSubmit={canSubmitDoc}
              canCancel={canCancelDoc}
              onEdit={isDraft ? () => nav(`/landed-cost-vouchers/${encodeURIComponent(name)}/edit`) : undefined}
              onSubmit={isDraft ? () => doAction("submit") : undefined}
            onDelete={deleteAction.onDelete}
              onCancel={isSubmitted ? () => doAction("cancel") : undefined}
              onAmend={docstatus === 2 ? amend : undefined}
              busy={busy || deleteAction.loading}
            />
          </>
        }
      />
      {err && <ErrorBox error={err} />}
      <Card num={1} title={t("lcv.details")}>
        <div className="fields">
          <label>{t("lcv.col.date")}<span>{String(d.posting_date ?? "")}</span></label>
          <label>{t("lcv.distributeOn")}<span>{String(d.distribute_charges_based_on ?? "")}</span></label>
          <label>{t("lcv.col.total")}<span>{money(Number(d.total_taxes_and_charges ?? 0))}</span></label>
        </div>
      </Card>
      <Card num={2} title={t("lcv.receipts")}>
        <table className="dtbl">
          <thead><tr><th>{t("lcv.receipt")}</th><th>{t("lcv.receiptType")}</th></tr></thead>
          <tbody>
            {receipts.map((r, i) => {
              const row = r as Record<string, unknown>;
              return (
                <tr key={i}>
                  <td>{String(row.receipt_document ?? "")}</td>
                  <td>{String(row.receipt_document_type ?? "")}</td>
                </tr>
              );
            })}
            {receipts.length === 0 && <tr><td colSpan={2} className="empty">{t("lcv.noReceipts")}</td></tr>}
          </tbody>
        </table>
      </Card>
      <Card num={3} title={t("lcv.taxes")}>
        <table className="dtbl">
          <thead><tr><th>{t("lcv.account")}</th><th className="n">{t("lcv.amount")}</th></tr></thead>
          <tbody>
            {taxes.map((tx, i) => {
              const row = tx as Record<string, unknown>;
              return (
                <tr key={i}>
                  <td>{String(row.expense_account ?? "")}</td>
                  <td className="n">{money(Number(row.amount ?? 0))}</td>
                </tr>
              );
            })}
            {taxes.length === 0 && <tr><td colSpan={2} className="empty">{t("lcv.noTaxes")}</td></tr>}
          </tbody>
        </table>
      </Card>
      <Card num={4} title={t("lcv.itemsDist")}>
        <table className="dtbl">
          <thead><tr><th>{t("lcv.itemCode")}</th><th>{t("lcv.description")}</th><th className="n">{t("lcv.amount")}</th></tr></thead>
          <tbody>
            {items.map((it, i) => {
              const row = it as Record<string, unknown>;
              return (
                <tr key={i}>
                  <td>{String(row.item_code ?? "")}</td>
                  <td>{String(row.description ?? "")}</td>
                  <td className="n">{money(Number(row.applicable_charges ?? 0))}</td>
                </tr>
              );
            })}
            {items.length === 0 && <tr><td colSpan={3} className="empty">{t("lcv.noItems")}</td></tr>}
          </tbody>
        </table>
      </Card>
    </>
  );
}
