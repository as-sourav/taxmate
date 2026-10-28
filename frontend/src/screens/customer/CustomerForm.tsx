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

type CreditLimitRow = {
  _key: string;
  company: string;
  credit_limit: number;
  bypass_credit_limit_check: 0 | 1;
};

type CustomerDoc = {
  name: string;
  customer_name?: string;
  customer_type?: string;
  customer_group?: string;
  territory?: string;
  tax_id?: string;
  payment_terms?: string;
  trade_license_number?: string;
  legal_registration_identifier?: string;
  legal_registration_identifier_type?: string;
  uae_peppol_id?: string;
  uae_fz_beneficiary_id?: string;
  uae_in_designated_zone?: 0 | 1;
  selling_price_list?: string;
  tax_category?: string;
  customer_primary_address?: string;
  customer_primary_contact?: string;
  credit_limits?: { company?: string; credit_limit?: number; bypass_credit_limit_check?: 0 | 1 }[];
  disabled?: 0 | 1;
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

export default function CustomerForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const isNew = name === "new";

  const existing = useDoc<CustomerDoc>(DT.customer, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const settings = useDoc<{ customer_group?: string; territory?: string; selling_price_list?: string }>(DT.sellingSettings, DT.sellingSettings);
  const groups = useDocList<{ name: string }>(DT.customerGroup, {
    fields: ["name"],
    filters: [["is_group", "=", 0]],
    limit: 50,
  });
  const territories = useDocList<{ name: string }>(DT.territory, {
    fields: ["name"],
    filters: [["is_group", "=", 0]],
    limit: 50,
  });
  const priceLists = useDocList<{ name: string }>(DT.priceList, {
    fields: ["name"],
    filters: [["selling", "=", 1]],
    limit: 50,
  });
  const terms = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });
  const create = useInsert();
  const makeQuote = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeCustomerQuotation);
  const makeOpp = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeOpportunityFromCustomer);
  const opportunity = useOpenMapped("/opportunities");
  const update = useSave();

  const [form, setForm] = useState({
    customer_name: "",
    customer_type: "Company",
    customer_group: "",
    tax_id: "",
    payment_terms: "",
    territory: "",
    selling_price_list: "",
    tax_category: "",
    trade_license_number: "",
    legal_registration_identifier: "",
    legal_registration_identifier_type: "CRN",
    uae_peppol_id: "",
    uae_fz_beneficiary_id: "",
    uae_in_designated_zone: 0 as 0 | 1,
    disabled: 0 as 0 | 1,
    address_line1: "",
    city: "",
    state: "",
    email_id: "",
    phone: "",
  });
  const [creditLimits, setCreditLimits] = useState<CreditLimitRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  let _clKey = 0;
  const newClKey = () => `cl${++_clKey}`;

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setForm((f) => ({
      ...f,
      customer_name: d.customer_name || "",
      customer_type: d.customer_type || "Company",
      customer_group: d.customer_group || "",
      tax_id: d.tax_id || "",
      payment_terms: d.payment_terms || "",
      territory: d.territory || "",
      selling_price_list: d.selling_price_list || "",
      tax_category: d.tax_category || "",
      trade_license_number: d.trade_license_number || "",
      legal_registration_identifier: d.legal_registration_identifier || "",
      legal_registration_identifier_type: d.legal_registration_identifier_type || "CRN",
      uae_peppol_id: d.uae_peppol_id || "",
      uae_fz_beneficiary_id: d.uae_fz_beneficiary_id || "",
      uae_in_designated_zone: d.uae_in_designated_zone || 0,
      disabled: (d.disabled ? 1 : 0) as 0 | 1,
    }));
    setCreditLimits(
      (d.credit_limits ?? []).map((r) => ({
        _key: `cl${Math.random()}`,
        company: r.company || "",
        credit_limit: Number(r.credit_limit) || 0,
        bypass_credit_limit_check: (r.bypass_credit_limit_check ?? 0) as 0 | 1,
      }))
    );
  }, [existing.data]);

  const addrName = existing.data?.customer_primary_address;
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
  const ready = !!form.customer_name && !!form.customer_type && !!form.address_line1 && !!form.city && !!form.state;

  async function save() {
    setBusy(true);
    setSaveError(null);
    try {
      const group = form.customer_group || settings.data?.customer_group;
      const territory = settings.data?.territory;
      const payload = {
        customer_name: form.customer_name,
        customer_type: form.customer_type,
        customer_group: group,
        territory: form.territory || territory,
        selling_price_list: form.selling_price_list || undefined,
        tax_category: form.tax_category || undefined,
        tax_id: form.tax_id || undefined,
        payment_terms: form.payment_terms || undefined,
        trade_license_number: form.trade_license_number || undefined,
        legal_registration_identifier: form.legal_registration_identifier || undefined,
        legal_registration_identifier_type: form.legal_registration_identifier_type || undefined,
        uae_peppol_id: form.uae_peppol_id || undefined,
        uae_fz_beneficiary_id: form.uae_fz_beneficiary_id || undefined,
        uae_in_designated_zone: form.uae_in_designated_zone,
        disabled: form.disabled,
        credit_limits: creditLimits.length > 0
          ? creditLimits.map(({ _key: _k, ...r }) => r)
          : undefined,
      };
      const cust = isNew
        ? await create.createDoc(DT.customer, payload)
        : await update.updateDoc(DT.customer, name, payload);
      const custName = (cust as { name: string }).name;

      const addrPayload = {
        address_title: form.customer_name,
        address_type: "Billing",
        address_line1: form.address_line1,
        city: form.city,
        state: form.state,
        emirate: form.state,
        country: "United Arab Emirates",
        email_id: form.email_id || undefined,
        phone: form.phone || undefined,
        links: [{ link_doctype: "Customer", link_name: custName }],
      };
      let primaryAddress = existing.data?.customer_primary_address;
      if (primaryAddress) {
        await update.updateDoc(DT.address, primaryAddress, addrPayload);
      } else {
        const addr = await create.createDoc(DT.address, addrPayload);
        primaryAddress = (addr as { name: string }).name;
      }

      let primaryContact = existing.data?.customer_primary_contact;
      if (form.email_id || form.phone) {
        const contactPayload = {
          first_name: form.customer_name,
          email_id: form.email_id || undefined,
          mobile_no: form.phone || undefined,
          links: [{ link_doctype: "Customer", link_name: custName }],
        };
        if (primaryContact) {
          await update.updateDoc(DT.contact, primaryContact, contactPayload);
        } else {
          const contact = await create.createDoc(DT.contact, contactPayload);
          primaryContact = (contact as { name: string }).name;
        }
      }

      await update.updateDoc(DT.customer, custName, {
        customer_primary_address: primaryAddress,
        customer_primary_contact: primaryContact,
      });
      nav(`/customers/${encodeURIComponent(custName)}`);
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
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/customers")}>{t("nav.customers")}</button>}
        title={isNew ? t("cust.new") : form.customer_name || name}
        actions={
          <>
            {!isNew ? (<DocHistory doctype={DT.customer} name={name} />) : null}
            {!isNew ? (
              <>
                <button type="button" className="btn ghost" onClick={() => void makeQuote.call({ source_name: name }).then(async (res) => {
                  const mapped = res?.message;
                  if (!mapped) throw new Error(t("doc.err.mapFailed"));
                  const body: Record<string, unknown> = { ...mapped };
                  delete body.name; delete body.doctype; delete body.__islocal; delete body.__unsaved;
                  const created = await create.createDoc(DT.quotation, body) as { name: string };
                  nav(`/quotations/${encodeURIComponent(created.name)}/edit`);
                }).catch((err) => setSaveError(err))}>{t("nav.quotations")}</button>
                <button type="button" className="btn ghost" onClick={() => nav("/orders/new", { state: { mapped: { customer: name } } })}>{t("nav.salesOrders")}</button>
                <button type="button" className="btn ghost" disabled={opportunity.busy} onClick={() => void opportunity.open(() => makeOpp.call({ source_name: name }))}>Opportunity</button>
                <button type="button" className="btn ghost" onClick={() => nav(`/payments/new?type=Receive&party=${encodeURIComponent(name)}`)}>{t("sod.createPayment")}</button>
              </>
            ) : null}

            <button className="btn ghost" onClick={() => nav("/customers")}>{t("soc.discard")}</button>
            <button className="btn" disabled={busy || !ready} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
          </>
        }
      />
      {(saveError || opportunity.error) && <ErrorBox error={saveError || opportunity.error} />}

      <Card num={1} title={t("cust.identity")}>
        <div className="grid2">
          <Field label={t("cust.col.name")} required>
            <input className="ctl" value={form.customer_name} onChange={(e) => set("customer_name", e.target.value)} />
          </Field>
          <CheckField
            label={t("common.disabled")}
            hint={t("doc.offHint")}
            checked={!!form.disabled}
            onChange={(on) => set("disabled", on ? 1 : 0)}
          />
          <Field label={t("cust.type")} required>
            <select className="ctl" value={form.customer_type} onChange={(e) => set("customer_type", e.target.value)}>
              <option value="Company">{t("cust.type.company")}</option>
              <option value="Individual">{t("cust.type.individual")}</option>
              <option value="Partnership">{t("cust.type.partnership")}</option>
            </select>
          </Field>
          <Field label={t("cust.col.group")}>
            <select className="ctl" value={form.customer_group} onChange={(e) => set("customer_group", e.target.value)}>
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
          <Field label={t("f.sellingPriceList")}>
            <select className="ctl" value={form.selling_price_list} onChange={(e) => set("selling_price_list", e.target.value)}>
              <option value="" />
              {(priceLists.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
            </select>
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

      <Card num={4} title={t("cust.creditLimits")}>
        {creditLimits.length === 0 ? (
          <p style={{ color: "var(--faint)", marginBottom: 8 }}>{t("cust.noCreditLimits")}</p>
        ) : (
          <table className="data-table" style={{ marginBottom: 8 }}>
            <thead>
              <tr>
                <th>{t("cust.cl.company")}</th>
                <th>{t("cust.cl.limit")}</th>
                <th>{t("cust.cl.bypass")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {creditLimits.map((r) => (
                <tr key={r._key}>
                  <td>
                    <input
                      className="ctl"
                      value={r.company}
                      onChange={(e) =>
                        setCreditLimits((ls) =>
                          ls.map((l) => l._key === r._key ? { ...l, company: e.target.value } : l)
                        )
                      }
                      placeholder={t("cust.cl.company")}
                    />
                  </td>
                  <td>
                    <input
                      className="ctl"
                      type="number"
                      min={0}
                      value={r.credit_limit}
                      onChange={(e) =>
                        setCreditLimits((ls) =>
                          ls.map((l) => l._key === r._key ? { ...l, credit_limit: Number(e.target.value) } : l)
                        )
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!r.bypass_credit_limit_check}
                      onChange={(e) =>
                        setCreditLimits((ls) =>
                          ls.map((l) => l._key === r._key ? { ...l, bypass_credit_limit_check: e.target.checked ? 1 : 0 } : l)
                        )
                      }
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => setCreditLimits((ls) => ls.filter((l) => l._key !== r._key))}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button
          type="button"
          className="btn ghost"
          onClick={() =>
            setCreditLimits((ls) => [
              ...ls,
              { _key: newClKey(), company: "", credit_limit: 0, bypass_credit_limit_check: 0 },
            ])
          }
        >
          {t("cust.addCreditLimit")}
        </button>
      </Card>
    </>
  );
}
