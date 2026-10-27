import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";
import { DT, METHOD } from "../../lib/frappe";
import { useOpenMapped } from "../../lib/openMapped";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { UAE_EMIRATES } from "../../types/uae";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import LinkField from "../../components/LinkField";

type SupplierDoc = {
  name: string;
  supplier_name?: string;
  supplier_type?: string;
  supplier_group?: string;
  tax_id?: string;
  payment_terms?: string;
  trade_license_number?: string;
  legal_registration_identifier?: string;
  legal_registration_identifier_type?: string;
  uae_peppol_id?: string;
  uae_fz_beneficiary_id?: string;
  uae_in_designated_zone?: 0 | 1;
  territory?: string;
  country?: string;
  tax_category?: string;
  supplier_primary_address?: string;
  supplier_primary_contact?: string;
  disabled?: 0 | 1;
  on_hold?: 0 | 1;
};

type AddressDoc = {
  name?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  emirate?: string;
  country?: string;
  email_id?: string;
  phone?: string;
};

export default function SupplierForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const isNew = name === "new";

  const existing = useDoc<SupplierDoc>(DT.supplier, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const settings = useDoc<{ supplier_group?: string }>(DT.buyingSettings, DT.buyingSettings);
  const groups = useDocList<{ name: string }>(DT.supplierGroup, {
    fields: ["name"],
    filters: [["is_group", "=", 0]],
    limit: 50,
  });
  const territories = useDocList<{ name: string }>(DT.territory, {
    fields: ["name"],
    filters: [["is_group", "=", 0]],
    limit: 50,
  });
  const terms = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });
  const create = useInsert();
  const update = useSave();
  const makeRfq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSupplierRfq);
  const rfq = useOpenMapped("/request-for-quotations");

  const [form, setForm] = useState({
    supplier_name: "",
    supplier_type: "Company",
    supplier_group: "",
    tax_id: "",
    payment_terms: "",
    territory: "",
    country: "United Arab Emirates",
    tax_category: "",
    trade_license_number: "",
    legal_registration_identifier: "",
    legal_registration_identifier_type: "CRN",
    uae_peppol_id: "",
    uae_fz_beneficiary_id: "",
    uae_in_designated_zone: 0 as 0 | 1,
    disabled: 0 as 0 | 1,
    on_hold: 0 as 0 | 1,
    address_line1: "",
    city: "",
    state: "",
    email_id: "",
    phone: "",
  });
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setForm((f) => ({
      ...f,
      supplier_name: d.supplier_name || "",
      supplier_type: d.supplier_type || "Company",
      supplier_group: d.supplier_group || "",
      tax_id: d.tax_id || "",
      payment_terms: d.payment_terms || "",
      territory: d.territory || "",
      country: d.country || "United Arab Emirates",
      tax_category: d.tax_category || "",
      trade_license_number: d.trade_license_number || "",
      legal_registration_identifier: d.legal_registration_identifier || "",
      legal_registration_identifier_type: d.legal_registration_identifier_type || "CRN",
      uae_peppol_id: d.uae_peppol_id || "",
      uae_fz_beneficiary_id: d.uae_fz_beneficiary_id || "",
      uae_in_designated_zone: d.uae_in_designated_zone || 0,
      disabled: (d.disabled ? 1 : 0) as 0 | 1,
      on_hold: (d.on_hold ? 1 : 0) as 0 | 1,
    }));
  }, [existing.data]);

  const addrName = existing.data?.supplier_primary_address;
  const address = useDoc<AddressDoc>(DT.address, addrName, addrName || null, {
    isPaused: () => !addrName,
  });
  useEffect(() => {
    const a = address.data;
    if (!a) return;
    setForm((f) => ({
      ...f,
      address_line1: a.address_line1 || "",
      city: a.city || "",
      state: a.emirate || a.state || "",
      email_id: a.email_id || "",
      phone: a.phone || "",
    }));
  }, [address.data]);

  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));
  const ready = !!form.supplier_name && !!form.supplier_type && !!form.address_line1 && !!form.city && !!form.state;

  async function save() {
    setBusy(true);
    setSaveError(null);
    try {
      const group = form.supplier_group || settings.data?.supplier_group;
      const payload = {
        supplier_name: form.supplier_name,
        territory: form.territory || undefined,
        country: form.country || "United Arab Emirates",
        tax_category: form.tax_category || undefined,
        supplier_type: form.supplier_type,
        supplier_group: group,
        tax_id: form.tax_id || undefined,
        payment_terms: form.payment_terms || undefined,
        trade_license_number: form.trade_license_number || undefined,
        legal_registration_identifier: form.legal_registration_identifier || undefined,
        legal_registration_identifier_type: form.legal_registration_identifier_type || undefined,
        uae_peppol_id: form.uae_peppol_id || undefined,
        uae_fz_beneficiary_id: form.uae_fz_beneficiary_id || undefined,
        uae_in_designated_zone: form.uae_in_designated_zone,
        disabled: form.disabled,
        on_hold: form.on_hold,
      };
      const supp = isNew
        ? await create.createDoc(DT.supplier, payload)
        : await update.updateDoc(DT.supplier, name, payload);
      const suppName = (supp as { name: string }).name;

      const addrPayload = {
        address_title: form.supplier_name,
        address_type: "Billing",
        address_line1: form.address_line1,
        city: form.city,
        state: form.state,
        emirate: form.state,
        country: "United Arab Emirates",
        email_id: form.email_id || undefined,
        phone: form.phone || undefined,
        links: [{ link_doctype: "Supplier", link_name: suppName }],
      };
      let primaryAddress = existing.data?.supplier_primary_address;
      if (primaryAddress) {
        await update.updateDoc(DT.address, primaryAddress, addrPayload);
      } else {
        const addr = await create.createDoc(DT.address, addrPayload);
        primaryAddress = (addr as { name: string }).name;
      }

      let primaryContact = existing.data?.supplier_primary_contact;
      if (form.email_id || form.phone) {
        const contactPayload = {
          first_name: form.supplier_name,
          email_id: form.email_id || undefined,
          mobile_no: form.phone || undefined,
          links: [{ link_doctype: "Supplier", link_name: suppName }],
        };
        if (primaryContact) {
          await update.updateDoc(DT.contact, primaryContact, contactPayload);
        } else {
          const contact = await create.createDoc(DT.contact, contactPayload);
          primaryContact = (contact as { name: string }).name;
        }
      }

      await update.updateDoc(DT.supplier, suppName, {
        supplier_primary_address: primaryAddress,
        supplier_primary_contact: primaryContact,
      });
      nav(`/suppliers/${encodeURIComponent(suppName)}`);
    } catch (err) {
      setSaveError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/suppliers")}>{t("nav.suppliers")}</button>
        }
        title={isNew ? t("supp.new") : form.supplier_name || name}
        actions={
          <>
            {!isNew ? (<DocHistory doctype={DT.supplier} name={name} />) : null}
            {!isNew ? (
              <>
                <button type="button" className="btn ghost" onClick={() => nav("/purchase-orders/new", { state: { mapped: { supplier: name } } })}>{t("nav.purchaseOrders")}</button>
                <button type="button" className="btn ghost" onClick={() => nav("/purchase-invoices/new", { state: { mapped: { supplier: name } } })}>{t("nav.purchaseInvoices")}</button>
                <button type="button" className="btn ghost" onClick={() => nav("/supplier-quotations/new", { state: { mapped: { supplier: name } } })}>{t("nav.supplierQuotations")}</button>
                <button type="button" className="btn ghost" disabled={rfq.busy} onClick={() => void rfq.open(() => makeRfq.call({ supplier: name }))}>Request for Quotation</button>
              </>
            ) : null}

            <button type="button" className="btn ghost" onClick={() => nav("/suppliers")}>{t("soc.discard")}</button>
            <button type="button" className="btn" disabled={busy || !ready} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
          </>
        }
      />
      {(saveError || rfq.error) && <ErrorBox error={saveError || rfq.error} />}

      <Card num={1} title={t("cust.identity")}>
        <div className="grid2">
          <Field label={t("cust.col.name")} required>
            <input className="ctl" value={form.supplier_name} onChange={(e) => set("supplier_name", e.target.value)} />
          </Field>
          <CheckField
            label={t("supp.onHold")}
            checked={!!form.on_hold}
            onChange={(on) => set("on_hold", on ? 1 : 0)}
          />
          <CheckField
            label={t("common.disabled")}
            hint={t("doc.offHint")}
            checked={!!form.disabled}
            onChange={(on) => set("disabled", on ? 1 : 0)}
          />
          <Field label={t("cust.type")} required>
            <select className="ctl" value={form.supplier_type} onChange={(e) => set("supplier_type", e.target.value)}>
              <option value="Company">{t("cust.type.company")}</option>
              <option value="Individual">{t("cust.type.individual")}</option>
              <option value="Partnership">{t("cust.type.partnership")}</option>
            </select>
          </Field>
          <Field label={t("cust.col.group")}>
            <select className="ctl" value={form.supplier_group} onChange={(e) => set("supplier_group", e.target.value)}>
              <option value="" />
              {(groups.data ?? []).map((g) => <option key={g.name} value={g.name}>{g.name}</option>)}
            </select>
          </Field>
          <Field label={t("cust.col.trn")}>
            <input className="ctl" value={form.tax_id} onChange={(e) => set("tax_id", e.target.value)} />
          </Field>
          <Field label={t("f.paymentTerms")}>
            <select className="ctl" value={form.payment_terms} onChange={(e) => set("payment_terms", e.target.value)}>
              <option value="" />
              {(terms.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
            </select>
          </Field>
          <Field label={t("f.territory")}>
            <select className="ctl" value={form.territory} onChange={(e) => set("territory", e.target.value)}>
              <option value="" />
              {(territories.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
            </select>
          </Field>
          <Field label={t("f.country")}>
            <input className="ctl" value={form.country} onChange={(e) => set("country", e.target.value)} />
          </Field>
          <Field label={t("f.taxCategory")}>
            <LinkField doctype={DT.taxCategory} value={form.tax_category}
              onChange={(v) => set("tax_category", v)} />
          </Field>
        </div>
      </Card>

      <Card num={2} title={t("cust.legal")}>
        <div className="grid2">
          <Field label={t("cust.license")}>
            <input className="ctl" value={form.trade_license_number} onChange={(e) => set("trade_license_number", e.target.value)} />
          </Field>
          <Field label={t("cust.legalId")}>
            <input className="ctl" value={form.legal_registration_identifier} onChange={(e) => set("legal_registration_identifier", e.target.value)} />
          </Field>
          <Field label={t("cust.legalType")}>
            <select className="ctl" value={form.legal_registration_identifier_type}
              onChange={(e) => set("legal_registration_identifier_type", e.target.value)}>
              <option value="CRN">CRN</option>
              <option value="OTH">OTH</option>
            </select>
          </Field>
          <Field label={t("cust.peppol")}>
            <input className="ctl" value={form.uae_peppol_id} onChange={(e) => set("uae_peppol_id", e.target.value)} />
          </Field>
          <Field label={t("cust.fz")}>
            <input className="ctl" value={form.uae_fz_beneficiary_id} onChange={(e) => set("uae_fz_beneficiary_id", e.target.value)} />
          </Field>
          <Field label={t("cust.dz")}>
            <select className="ctl" value={String(form.uae_in_designated_zone)}
              onChange={(e) => set("uae_in_designated_zone", Number(e.target.value))}>
              <option value="0">{t("no")}</option>
              <option value="1">{t("yes")}</option>
            </select>
          </Field>
        </div>
      </Card>

      <Card num={3} title={t("cust.address")}>
        <div className="grid2">
          <Field label={t("cust.line")} required>
            <input className="ctl" value={form.address_line1} onChange={(e) => set("address_line1", e.target.value)} />
          </Field>
          <Field label={t("cust.col.city")} required>
            <input className="ctl" value={form.city} onChange={(e) => set("city", e.target.value)} />
          </Field>
          <Field label={t("f.emirate")} required>
            <select className="ctl" value={form.state} onChange={(e) => set("state", e.target.value)}>
              <option value="" />
              {UAE_EMIRATES.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </Field>
          <Field label={t("cust.email")}>
            <input className="ctl" type="email" value={form.email_id} onChange={(e) => set("email_id", e.target.value)} />
          </Field>
          <Field label={t("cust.phone")}>
            <input className="ctl" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
          </Field>
        </div>
      </Card>
    </>
  );
}
