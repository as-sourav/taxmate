/**
 * POS Invoice create/submit form.
 * Importers: App.tsx routes /pos-invoices/new and /pos-invoices/:name/edit.
 * API: taxmate.api.resource.insert; taxmate.api.workflow.submit.
 * Schema: customer (optional walk-in), pos_profile, posting_date, vat_emirate (mandatory),
 *   items[item_code, qty, rate], payments[mode_of_payment, amount].
 * User: "Implement the plan… complete all the to-dos."
 */
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { UAE_EMIRATES } from "../../types/uae";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead, SumRow } from "../../components/ui";
import { FormActions, FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";

type Line = { item_code: string; qty: number; rate: number };
type Payment = { mode_of_payment: string; amount: number };

type Doc = {
  name: string;
  customer?: string;
  pos_profile?: string;
  posting_date?: string;
  vat_emirate?: string;
  docstatus?: number;
  items?: { item_code?: string; qty?: number; rate?: number }[];
  payments?: { mode_of_payment?: string; amount?: number }[];
  selling_price_list?: string;
};

export default function PosInvoiceForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<Doc>(DT.posInvoice, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const submitCall = useFrappePostCall(METHOD.submit);

  const [customer, setCustomer] = useState("");
  const [posProfile, setPosProfile] = useState("");
  const [postingDate, setPostingDate] = useState(toIsoDate(new Date()));
  const [vatEmirate, setVatEmirate] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item_code: "", qty: 1, rate: 0 }]);
  const [payments, setPayments] = useState<Payment[]>([{ mode_of_payment: "Cash", amount: 0 }]);
  const [priceList, setPriceList] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const insert = useInsert();
  const canSubmit = canSubmitSales(session.roles);

  useEffect(() => {
    if (!isNew && existing.data) {
      const d = existing.data;
      setCustomer(d.customer ?? "");
      setPosProfile(d.pos_profile ?? "");
      setPostingDate(d.posting_date ?? toIsoDate(new Date()));
      setVatEmirate(d.vat_emirate ?? "");
      setLines((d.items ?? []).map((l) => ({ item_code: l.item_code ?? "", qty: l.qty ?? 1, rate: l.rate ?? 0 })));
      setPayments((d.payments ?? []).map((p) => ({ mode_of_payment: p.mode_of_payment ?? "Cash", amount: p.amount ?? 0 })));
      setPriceList(d.selling_price_list ?? "");
    }
  }, [isNew, existing.data]);

  if (!session.user) return <Navigate to="/" />;
  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data?.docstatus !== 0) return <Navigate to={`/pos-invoices/${encodeURIComponent(name)}`} />;

  const netTotal = lines.reduce((s, l) => s + l.qty * l.rate, 0);

  function addLine() { setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }]); }
  function removeLine(i: number) { setLines((ls) => ls.filter((_, j) => j !== i)); }
  function setLine<K extends keyof Line>(i: number, k: K, v: Line[K]) {
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  }

  async function handleSave(andSubmit = false) {
    if (!vatEmirate) { setSaveError(new Error(t("pos.errEmirate"))); return; }
    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, unknown> = {
        doctype: DT.posInvoice,
        is_pos: 1,
        posting_date: postingDate,
        vat_emirate: vatEmirate,
        ...(customer ? { customer } : {}),
        ...(posProfile ? { pos_profile: posProfile } : {}),
        ...(priceList ? { selling_price_list: priceList } : {}),
        items: lines.filter((l) => l.item_code).map((l) => ({
          doctype: "POS Invoice Item",
          item_code: l.item_code,
          qty: l.qty,
          rate: l.rate,
        })),
        payments: payments.filter((p) => p.mode_of_payment).map((p) => ({
          doctype: "Sales Invoice Payment",
          mode_of_payment: p.mode_of_payment,
          amount: p.amount,
        })),
      };
      const created = await insert.createDoc(DT.posInvoice, body);
      const newName = (created as { name: string }).name;
      if (andSubmit && canSubmit) {
        await submitCall.call({ doc: { doctype: DT.posInvoice, name: newName } });
      }
      nav(`/pos-invoices/${encodeURIComponent(newName)}`);
    } catch (e) { setSaveError(e); } finally { setSaving(false); }
  }

  return (
    <>
      <PageHead title={isNew ? t("pos.new") : name} eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/pos-invoices")}>{t("pos.title")}</button>} />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout>
        <Card title={t("pos.title")}>
          <Field label={t("posp.col.priceList")}>
            <LinkField doctype={DT.priceList} value={priceList} onChange={setPriceList} placeholder={t("posp.col.priceList")} />
          </Field>
          <Field label={t("pos.col.profile")}>
            <LinkField doctype={DT.posProfile} value={posProfile} onChange={setPosProfile} placeholder={t("pos.col.profile")} />
          </Field>
          <Field label={`${t("pos.col.customer")} (${t("pos.walkInHint")})`}>
            <LinkField doctype={DT.customer} value={customer} onChange={setCustomer} placeholder={t("pos.walkIn")} />
          </Field>
          <Field label={t("pos.col.date")}>
            <input className="inp" type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} />
          </Field>
          <Field label={`${t("pos.col.emirate")} *`}>
            <select className="inp" value={vatEmirate} onChange={(e) => setVatEmirate(e.target.value)} required>
              <option value="">— {t("pos.col.emirate")} —</option>
              {UAE_EMIRATES.map((em) => <option key={em} value={em}>{em}</option>)}
            </select>
          </Field>
        </Card>
        <Card title={t("pos.col.items")}>
          {lines.map((ln, i) => (
            <div key={i} className="flex gap-2 mb-2 items-end">
              <Field label={i === 0 ? t("inv.col.item") : ""}>
                <LinkField doctype={DT.item} value={ln.item_code} onChange={(v) => setLine(i, "item_code", v)} placeholder={t("pos.ph.item")} />
              </Field>
              <Field label={i === 0 ? t("inv.col.qty") : ""}>
                <input className="inp" type="number" min={0.001} step={0.001} value={ln.qty}
                  onChange={(e) => setLine(i, "qty", parseNum(e.target.value))} />
              </Field>
              <Field label={i === 0 ? t("inv.col.rate") : ""}>
                <input className="inp" type="number" min={0} step={0.01} value={ln.rate}
                  onChange={(e) => setLine(i, "rate", parseNum(e.target.value))} />
              </Field>
              <button type="button" className="btn btn-ghost text-red-500" onClick={() => removeLine(i)} aria-label={t("common.remove")}>✕</button>
            </div>
          ))}
          <button type="button" className="btn btn-ghost text-sm mt-1" onClick={addLine}>+ {t("common.addLine")}</button>
          <SumRow k={t("inv.col.net")} v={money(netTotal)} />
        </Card>
        <Card title={t("pos.col.payments")}>
          {payments.map((p, i) => (
            <div key={i} className="flex gap-2 mb-2 items-end">
              <Field label={i === 0 ? t("pos.col.mop") : ""}>
                <LinkField
                  doctype={DT.modeOfPayment}
                  value={p.mode_of_payment}
                  onChange={(v) => setPayments((ps) => ps.map((x, j) => j === i ? { ...x, mode_of_payment: v } : x))}
                  placeholder={t("pos.ph.mop")}
                />
              </Field>
              <Field label={i === 0 ? t("pos.col.amount") : ""}>
                <input className="inp" type="number" min={0} step={0.01} value={p.amount}
                  onChange={(e) => setPayments((ps) => ps.map((x, j) => j === i ? { ...x, amount: parseNum(e.target.value) } : x))} />
              </Field>
            </div>
          ))}
          <button type="button" className="btn btn-ghost text-sm mt-1"
            onClick={() => setPayments((ps) => [...ps, { mode_of_payment: "", amount: 0 }])}>
            + {t("common.addLine")}
          </button>
        </Card>
        <FormActions
          onDiscard={() => nav(isNew ? "/pos-invoices" : `/pos-invoices/${encodeURIComponent(name)}`)}
          onSave={() => handleSave(false)}
          onSubmit={canSubmit ? () => handleSave(true) : undefined}
          submitLabel={t("pos.saveSubmit")}
          busy={saving}
        />
      </FormLayout>
    </>
  );
}
