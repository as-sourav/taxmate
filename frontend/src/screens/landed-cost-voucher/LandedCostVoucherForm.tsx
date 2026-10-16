/**
 * Landed Cost Voucher form. Routes: /landed-cost-vouchers/new, /landed-cost-vouchers/:name/edit
 * Callers: App.tsx. API: insert/save on "Landed Cost Voucher", workflow.submit. Phase 8.
 */
import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Navigate } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";
import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales, canWrite } from "../../lib/roles";
import { t } from "../../i18n/strings";
import { Card, Loading, ErrorBox, PageHead, Field } from "../../components/ui";
import { FormLayout, ReadinessCard } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";
import { parseNum, toIsoDate } from "../../lib/format";

const today = toIsoDate(new Date());

type Receipt = { receipt_document_type: "Purchase Receipt" | "Purchase Invoice"; receipt_document: string };
type TaxRow = { expense_account: string; description: string; amount: number };

type Doc = {
  posting_date?: string;
  distribute_charges_based_on?: string;
  purchase_receipts?: Receipt[];
  taxes?: TaxRow[];
  docstatus?: number;
};

const DISTRIBUTE_OPTIONS = ["Qty", "Amount", "Distribute Manually"];

export default function LandedCostVoucherForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";

  const existing = useDoc<Doc>(DT.landedCostVoucher, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall(METHOD.submit);

  const [postingDate, setPostingDate] = useState(today);
  const [distributeOn, setDistributeOn] = useState("Amount");
  const [receipts, setReceipts] = useState<Receipt[]>([
    { receipt_document_type: "Purchase Receipt", receipt_document: "" },
  ]);
  const [taxes, setTaxes] = useState<TaxRow[]>([
    { expense_account: "", description: "", amount: 0 },
  ]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setPostingDate(d.posting_date || today);
    setDistributeOn(d.distribute_charges_based_on || "Amount");
    const rs = (d.purchase_receipts ?? []).map((r) => ({
      receipt_document_type: r.receipt_document_type as "Purchase Receipt" | "Purchase Invoice",
      receipt_document: r.receipt_document,
    }));
    setReceipts(rs.length ? rs : [{ receipt_document_type: "Purchase Receipt", receipt_document: "" }]);
    const ts = (d.taxes ?? []).map((tx) => ({
      expense_account: tx.expense_account,
      description: tx.description,
      amount: Number(tx.amount) || 0,
    }));
    setTaxes(ts.length ? ts : [{ expense_account: "", description: "", amount: 0 }]);
  }, [existing.data]);

  const totalTax = useMemo(() => taxes.reduce((s, tx) => s + tx.amount, 0), [taxes]);

  const checks = useMemo(() => [
    { label: t("lcv.check.date"), ok: !!postingDate },
    { label: t("lcv.check.receipts"), ok: receipts.some((r) => r.receipt_document) },
    { label: t("lcv.check.taxes"), ok: taxes.some((tx) => tx.expense_account && tx.amount > 0) },
  ], [postingDate, receipts, taxes]);

  const ready = checks.every((c) => c.ok);

  async function save(shouldSubmit: boolean) {
    setBusy(true); setSaveError(null);
    try {
      const payload = {
        company: session.company,
        posting_date: postingDate,
        distribute_charges_based_on: distributeOn,
        purchase_receipts: receipts.filter((r) => r.receipt_document),
        taxes: taxes.filter((tx) => tx.expense_account),
      };
      const docname = isNew
        ? (await create.createDoc(DT.landedCostVoucher, payload) as { name: string }).name
        : (await update.updateDoc(DT.landedCostVoucher, name, payload), name);
      if (shouldSubmit) {
        await submitCall.call({ doc: { doctype: DT.landedCostVoucher, name: docname } });
      }
      nav(`/landed-cost-vouchers/${encodeURIComponent(docname)}`);
    } catch (err) {
      setSaveError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data && existing.data.docstatus !== 0) {
    return <Navigate to={`/landed-cost-vouchers/${encodeURIComponent(name)}`} replace />;
  }
  if (!canWrite(session)) return <Navigate to="/landed-cost-vouchers" replace />;

  return (
    <>
      <PageHead
        title={isNew ? t("lcv.new") : name}
        actions={
          <>
            <button type="button" className="btn ghost" disabled={busy} onClick={() => nav(-1)}>{t("form.cancel")}</button>
            <button type="button" className="btn ghost" disabled={busy || !ready} onClick={() => void save(false)}>{t("form.save")}</button>
            {canSubmitSales(session.roles) && (
              <button type="button" className="btn" disabled={busy || !ready} onClick={() => void save(true)}>{t("form.saveSubmit")}</button>
            )}
          </>
        }
      />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout>
        <ReadinessCard checks={checks} />
        <Card num={1} title={t("lcv.details")}>
          <div className="fields">
            <Field label={t("lcv.col.date")} required htmlFor="lcv-date">
              <input id="lcv-date" className="ctl" type="date" value={postingDate}
                onChange={(e) => setPostingDate(e.target.value)} />
            </Field>
            <Field label={t("lcv.distributeOn")} htmlFor="lcv-dist">
              <select id="lcv-dist" className="ctl" value={distributeOn}
                onChange={(e) => setDistributeOn(e.target.value)}>
                {DISTRIBUTE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
          </div>
        </Card>
        <Card num={2} title={t("lcv.receipts")}>
          {/* The receipt document names the line. There is no quantity and no
              money here, so nothing else earns the face of the card: the type
              picker sits behind "More". */}
          <LineItems<Receipt>
            rows={receipts}
            onRemove={(i) => setReceipts((rs) => rs.filter((_, j) => j !== i))}
            addLabel={t("lcv.addReceipt")}
            onAdd={() => setReceipts((rs) => [...rs, { receipt_document_type: "Purchase Receipt", receipt_document: "" }])}
            fields={[
              {
                key: "type", label: t("lcv.receiptType"),
                render: (r, i) => (
                  <select className="ctl mini" value={r.receipt_document_type}
                    onChange={(e) => setReceipts((rs) => rs.map((x, j) => j === i ? { ...x, receipt_document_type: e.target.value as "Purchase Receipt" | "Purchase Invoice" } : x))}>
                    <option value="Purchase Receipt">{t("lcv.src.purchaseReceipt")}</option>
                    <option value="Purchase Invoice">{t("lcv.src.purchaseInvoice")}</option>
                  </select>
                ),
              },
              {
                key: "receipt", label: t("lcv.receipt"), slot: "title", td: { minWidth: 220 },
                render: (r, i) => (
                  <LinkField
                    doctype={r.receipt_document_type === "Purchase Receipt" ? DT.purchaseReceipt : DT.purchaseInvoice}
                    value={r.receipt_document}
                    onChange={(v: string) => setReceipts((rs) => rs.map((x, j) => j === i ? { ...x, receipt_document: v } : x))}
                  />
                ),
              },
            ] as LineField<Receipt>[]}
          />
        </Card>
        <Card num={3} title={t("lcv.taxes")}>
          {/* The account names the charge and the amount is what you type;
              the free-text description is the only thing worth collapsing. */}
          <LineItems<TaxRow>
            rows={taxes}
            onRemove={(i) => setTaxes((ts) => ts.filter((_, j) => j !== i))}
            fields={[
              {
                key: "account", label: t("lcv.account"), slot: "title", td: { minWidth: 220 },
                render: (tx, i) => (
                  <LinkField
                    doctype={DT.account}
                    value={tx.expense_account}
                    onChange={(v: string) => setTaxes((ts) => ts.map((x, j) => j === i ? { ...x, expense_account: v } : x))}
                    filters={session.company ? [["company", "=", session.company], ["is_group", "=", 0]] as never : undefined}
                  />
                ),
              },
              {
                key: "description", label: t("lcv.description"),
                render: (tx, i) => (
                  <input className="ctl mini" value={tx.description}
                    onChange={(e) => setTaxes((ts) => ts.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
                ),
              },
              {
                key: "amount", label: t("lcv.amount"), slot: "primary", numeric: true,
                render: (tx, i) => (
                  <input className="ctl mini nn" style={{ width: 100 }} value={tx.amount}
                    onChange={(e) => setTaxes((ts) => ts.map((x, j) => j === i ? { ...x, amount: parseNum(e.target.value) } : x))} />
                ),
              },
            ] as LineField<TaxRow>[]}
            /* The table's own <tfoot> on a desktop; the same figure as a
               strip under the cards on a phone. */
            footer={
              <tr>
                <td colSpan={2} className="n">{t("lcv.total")}</td>
                <td className="n">{totalTax}</td>
                <td />
              </tr>
            }
            footerCard={<><span>{t("lcv.total")}</span><span>{totalTax}</span></>}
            addLabel={t("lcv.addCharge")}
            onAdd={() => setTaxes((ts) => [...ts, { expense_account: "", description: "", amount: 0 }])}
          />
        </Card>
      </FormLayout>
    </>
  );
}
