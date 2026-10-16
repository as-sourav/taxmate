/**
 * LeadForm — Phase 21. Create/edit Lead.
 * Callers: App.tsx /leads/new, /leads/:name/edit
 * API: taxmate.api.resource.insert / save on "Lead"
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import LinkField from "../../components/LinkField";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import { FormActions, FormLayout } from "../../components/form";

const STATUSES = ["Open", "Replied", "Opportunity", "Interested", "Converted", "Do Not Contact", "Lost Quotation"];

type Doc = { name: string; lead_name?: string; company_name?: string; email_id?: string; mobile_no?: string; phone?: string; territory?: string; request_type?: string; status?: string; city?: string; country?: string; disabled?: 0 | 1 };

export default function LeadForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const isNew = name === "new";

  const existing = useDoc<Doc>(DT.lead, isNew ? undefined : name, isNew ? null : name, { isPaused: () => isNew });
  const create = useInsert();
  const update = useSave();

  const [form, setForm] = useState({ lead_name: "", company_name: "", email_id: "", mobile_no: "", phone: "", territory: "", request_type: "", status: "Open", city: "", country: "United Arab Emirates", disabled: 0 as 0 | 1 });
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const d = existing.data;
    if (!d || loaded) return;
    setForm({
      lead_name: d.lead_name || "",
      company_name: d.company_name || "",
      email_id: d.email_id || "",
      mobile_no: d.mobile_no || "",
      phone: d.phone || "",
      territory: d.territory || "",
      request_type: d.request_type || "",
      status: d.status || "Open",
      city: d.city || "",
      country: d.country || "United Arab Emirates",
      disabled: (d.disabled ? 1 : 0) as 0 | 1,
    });
    setLoaded(true);
  }, [existing.data, loaded]);

  const setField = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const ready = !!form.lead_name.trim();

  async function saveFn() {
    if (!ready) return;
    setBusy(true); setSaveError(null);
    try {
      if (isNew) {
        const doc = (await create.createDoc(DT.lead, form)) as { name: string };
        nav(`/leads/${encodeURIComponent(doc.name)}`);
      } else {
        await update.updateDoc(DT.lead, name, form);
        nav(`/leads/${encodeURIComponent(name)}`);
      }
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/leads")}>{t("lead.title")}</button>}
        title={isNew ? t("lead.new") : form.lead_name || name}
        actions={
          !isNew ? (<DocHistory doctype={DT.lead} name={name} />) : null
        }
      />
      {saveError ? <ErrorBox error={saveError} /> : null}
      <FormLayout>
        <Card>
          <div className="fg">
            <CheckField
              label={t("common.disabled")}
              hint={t("doc.offHint")}
              checked={!!form.disabled}
              onChange={(on) => setForm((f) => ({ ...f, disabled: on ? 1 : 0 }))}
            />
            <Field label={t("lead.col.name")} required>
              <input className="ctl" value={form.lead_name} onChange={(e) => setField("lead_name", e.target.value)} placeholder={t("lead.namePh")} />
            </Field>
            <Field label={t("lead.col.company")}>
              <input className="ctl" value={form.company_name} onChange={(e) => setField("company_name", e.target.value)} />
            </Field>
            <Field label={t("lead.col.email")}>
              <input className="ctl" type="email" value={form.email_id} onChange={(e) => setField("email_id", e.target.value)} />
            </Field>
            <Field label={t("lead.col.mobile")}>
              <input className="ctl" type="tel" value={form.mobile_no} onChange={(e) => setField("mobile_no", e.target.value)} />
            </Field>
            <Field label={t("lead.phone")}>
              <input className="ctl" type="tel" value={form.phone} onChange={(e) => setField("phone", e.target.value)} />
            </Field>
            <Field label={t("f.territory")}>
              <LinkField doctype={DT.territory} value={form.territory} onChange={(v) => setField("territory", v)} />
            </Field>
            <Field label={t("lead.request")}>
              <select className="ctl" value={form.request_type} onChange={(e) => setField("request_type", e.target.value)}>
                <option value="" />
                <option value="Product Enquiry">{t("lead.src.productEnquiry")}</option>
                <option value="Request for Information">{t("lead.src.rfi")}</option>
                <option value="Suggestions">{t("lead.src.suggestions")}</option>
                <option value="Other">{t("lead.src.other")}</option>
              </select>
            </Field>
            <Field label={t("lead.col.status")}>
              <select className="ctl" value={form.status} onChange={(e) => setField("status", e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <Field label={t("lead.col.city")}>
              <input className="ctl" value={form.city} onChange={(e) => setField("city", e.target.value)} />
            </Field>
            <Field label={t("lead.col.country")}>
              <input className="ctl" value={form.country} onChange={(e) => setField("country", e.target.value)} />
            </Field>
          </div>
        </Card>
        <FormActions
          onSave={() => void saveFn()}
          onDiscard={() => nav(isNew ? "/leads" : `/leads/${encodeURIComponent(name)}`)}
          busy={busy}
          ready={ready}
        />
      </FormLayout>
    </>
  );
}
