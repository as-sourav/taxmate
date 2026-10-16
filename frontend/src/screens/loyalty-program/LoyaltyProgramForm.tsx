/**
 * Loyalty Program form — new and edit.
 * Importers: App.tsx routes /loyalty-programs/new and /loyalty-programs/:name/edit.
 * API: taxmate.api.resource.insert / save.
 * Schema: loyalty_program_name (Data), loyalty_program_type (Select),
 *   from_date (Date), to_date (Date), company (Link), conversion_factor (Float),
 *   expiry_duration (Int), expense_account (Link), cost_center (Link).
 * User: "Implement the plan… complete all the to-dos."
 */
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { parseNum, toIsoDate } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormActions, FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";

const LP_TYPES = ["Single Tier Program", "Multiple Tier Program"] as const;

type Doc = {
  name: string;
  loyalty_program_name?: string;
  loyalty_program_type?: string;
  from_date?: string;
  to_date?: string;
  company?: string;
  conversion_factor?: number;
  expiry_duration?: number;
  expense_account?: string;
  cost_center?: string;
};

export default function LoyaltyProgramForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<Doc>(DT.loyaltyProgram, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });

  const [lpName, setLpName] = useState("");
  const [lpType, setLpType] = useState<string>("Single Tier Program");
  const [fromDate, setFromDate] = useState(toIsoDate(new Date()));
  const [toDate, setToDate] = useState("");
  const [company, setCompany] = useState(session.company ?? "");
  const [convFactor, setConvFactor] = useState(1);
  const [expiry, setExpiry] = useState(0);
  const [expenseAccount, setExpenseAccount] = useState("");
  const [costCenter, setCostCenter] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const insert = useInsert();
  const save = useSave();

  useEffect(() => {
    if (!isNew && existing.data) {
      const d = existing.data;
      setLpName(d.loyalty_program_name ?? d.name ?? "");
      setLpType(d.loyalty_program_type ?? "Single Tier Program");
      setFromDate(d.from_date ?? toIsoDate(new Date()));
      setToDate(d.to_date ?? "");
      setCompany(d.company ?? "");
      setConvFactor(d.conversion_factor ?? 1);
      setExpiry(d.expiry_duration ?? 0);
      setExpenseAccount(d.expense_account ?? "");
      setCostCenter(d.cost_center ?? "");
    }
  }, [isNew, existing.data]);

  if (!session.user) return <Navigate to="/" />;
  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;

  async function handleSave() {
    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, unknown> = {
        doctype: DT.loyaltyProgram,
        loyalty_program_name: lpName || (isNew ? undefined : name),
        loyalty_program_type: lpType,
        from_date: fromDate,
        ...(toDate ? { to_date: toDate } : {}),
        company,
        conversion_factor: convFactor,
        ...(expiry ? { expiry_duration: expiry } : {}),
        ...(expenseAccount ? { expense_account: expenseAccount } : {}),
        ...(costCenter ? { cost_center: costCenter } : {}),
      };
      if (isNew) {
        const created = await insert.createDoc(DT.loyaltyProgram, body);
        nav(`/loyalty-programs/${encodeURIComponent((created as { name: string }).name)}`);
      } else {
        await save.updateDoc(DT.loyaltyProgram, name, body);
        nav(`/loyalty-programs/${encodeURIComponent(name)}`);
      }
    } catch (e) { setSaveError(e); } finally { setSaving(false); }
  }

  return (
    <>
      <PageHead title={isNew ? t("lp.new") : name} eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/loyalty-programs")}>{t("lp.title")}</button>} />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout>
        <Card title={t("lp.title")}>
          <Field label={t("lp.col.name")}>
            <input className="inp" value={lpName} onChange={(e) => setLpName(e.target.value)} placeholder={t("lp.namePh")} />
          </Field>
          <Field label={t("lp.col.type")}>
            <select className="inp" value={lpType} onChange={(e) => setLpType(e.target.value)}>
              {LP_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
          <Field label={t("lp.col.company")}>
            <LinkField doctype="Company" value={company} onChange={setCompany} placeholder={t("lp.ph.company")} />
          </Field>
          <Field label={t("lp.col.from")}>
            <input className="inp" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </Field>
          <Field label={t("lp.col.to")}>
            <input className="inp" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </Field>
          <Field label={t("lp.col.convFactor")}>
            <input className="inp" type="number" min={0.001} step={0.001} value={convFactor}
              onChange={(e) => setConvFactor(parseNum(e.target.value))} />
          </Field>
          <Field label={t("lp.col.expiry")}>
            <input className="inp" type="number" min={0} step={1} value={expiry}
              onChange={(e) => setExpiry(parseNum(e.target.value))} />
          </Field>
          <Field label={t("lp.col.expenseAccount")}>
            <LinkField doctype={DT.account} value={expenseAccount} onChange={setExpenseAccount} placeholder={t("lp.ph.expenseAccount")} />
          </Field>
        </Card>
        <FormActions
          onDiscard={() => nav(isNew ? "/loyalty-programs" : `/loyalty-programs/${encodeURIComponent(name)}`)}
          onSave={handleSave}
          busy={saving}
        />
      </FormLayout>
    </>
  );
}
