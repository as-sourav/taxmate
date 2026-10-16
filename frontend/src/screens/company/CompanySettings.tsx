/**
 * Company Settings — curated tabbed Company form for Owner, Accountant, Administrator.
 *
 * Importers: App.tsx /company. API: taxmate.api.resource.get/save, list_company_addresses,
 * upload_company_logo (all on get_catalog). Schema: ERPNext Company + TaxMate UAE custom fields.
 * No Company child tables — addresses via Dynamic Link.
 */

import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { DT, METHOD, readableError } from "../../lib/frappe";
import { useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canEditCompanyAccounts, canManageCompany, canViewTeam } from "../../lib/roles";
import { t } from "../../i18n/strings";
import { ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import LinkField from "../../components/LinkField";
import { apiFetch, fileUrl } from "../../mobile/http";

type CompanyDoc = {
  name: string;
  company_name: string;
  abbr: string;
  custom_taxmate_owner?: string | null;
  company_logo?: string | null;
  tax_id?: string | null;
  country?: string | null;
  default_currency?: string | null;
  domain?: string | null;
  date_of_establishment?: string | null;
  date_of_incorporation?: string | null;
  default_letter_head?: string | null;
  default_holiday_list?: string | null;
  phone_no?: string | null;
  fax?: string | null;
  email?: string | null;
  website?: string | null;
  default_bank_account?: string | null;
  default_cash_account?: string | null;
  default_receivable_account?: string | null;
  default_payable_account?: string | null;
  default_income_account?: string | null;
  default_expense_account?: string | null;
  default_deferred_revenue_account?: string | null;
  default_deferred_expense_account?: string | null;
  round_off_account?: string | null;
  write_off_account?: string | null;
  exchange_gain_loss_account?: string | null;
  cost_center?: string | null;
  payment_terms?: string | null;
  default_advance_received_account?: string | null;
  default_advance_paid_account?: string | null;
  default_discount_account?: string | null;
  enable_perpetual_inventory?: number | null;
  default_inventory_account?: string | null;
  stock_adjustment_account?: string | null;
  stock_received_but_not_billed?: string | null;
  default_warehouse_for_sales_return?: string | null;
  default_in_transit_warehouse?: string | null;
  default_wip_warehouse?: string | null;
  default_fg_warehouse?: string | null;
  default_scrap_warehouse?: string | null;
  valuation_method?: string | null;
  accumulated_depreciation_account?: string | null;
  depreciation_expense_account?: string | null;
  disposal_account?: string | null;
  capital_work_in_progress_account?: string | null;
  default_selling_terms?: string | null;
  default_buying_terms?: string | null;
  credit_limit?: number | string | null;
  monthly_sales_target?: number | string | null;
  trade_license_number?: string | null;
  legal_registration_identifier_type?: string | null;
  legal_registration_identifier?: string | null;
  uae_peppol_id?: string | null;
  uae_fz_beneficiary_id?: string | null;
  uae_in_designated_zone?: number | null;
  uae_e_invoice_enabled?: number | null;
  uae_is_government_entity?: number | null;
  uae_e_invoice_revenue_band?: string | null;
  uae_e_invoice_cohort_override?: string | null;
  taxmate_vat_filing_frequency?: string | null;
  taxmate_vat_first_period_start?: string | null;
  taxmate_assigned_accountant?: string | null;
  accounts_frozen_till_date?: string | null;
  role_allowed_for_frozen_entries?: string | null;
};

type AddrRow = {
  name: string;
  address_title?: string;
  address_type?: string;
  address_line1?: string;
  city?: string;
  country?: string;
};

type TabId = "identity" | "contact" | "accounts" | "stock" | "buying" | "uae" | "books";

const TABS: { id: TabId; label: string }[] = [
  { id: "identity", label: "cs.tab.identity" },
  { id: "contact", label: "cs.tab.contact" },
  { id: "accounts", label: "cs.tab.accounts" },
  { id: "stock", label: "cs.tab.stock" },
  { id: "buying", label: "cs.tab.buying" },
  { id: "uae", label: "cs.tab.uae" },
  { id: "books", label: "cs.tab.books" },
];

const ACCOUNT_FILTERS = (company: string, accountType?: string) => {
  const f: unknown[][] = [["company", "=", company], ["is_group", "=", 0]];
  if (accountType) f.push(["account_type", "=", accountType]);
  return f;
};

const WH_FILTERS = (company: string) => [
  ["company", "=", company],
  ["is_group", "=", 0],
];

export default function CompanySettings() {
  const session = useSession();
  const canFull = canManageCompany(session);
  const canAccounts = canEditCompanyAccounts(session);
  const canTeam = canViewTeam(session);
  const company = session.company ?? "";
  const fileRef = useRef<HTMLInputElement>(null);

  const res = useFrappeGetCall<{ message: CompanyDoc }>(
    METHOD.get,
    { doctype: DT.company, name: company },
    company ? `company-${company}` : null,
    { revalidateOnFocus: false },
  );
  const addrs = useFrappeGetCall<{ message: AddrRow[] }>(
    METHOD.listCompanyAddresses,
    { company },
    company ? `company-addrs-${company}` : null,
    { revalidateOnFocus: false },
  );
  const team = useFrappeGetCall<{ message: { name: string; full_name?: string; email?: string }[] }>(
    METHOD.listUsers,
    {},
    canTeam ? `company-team-users-${company}` : null,
    { revalidateOnFocus: false },
  );
  const { updateDoc, loading: saving } = useSave();

  const doc = res.data?.message;
  const [tab, setTab] = useState<TabId>("identity");
  const [form, setForm] = useState<Partial<CompanyDoc>>({});
  const [saved, setSaved] = useState(false);
  const [saveErr, setSaveErr] = useState<string[] | null>(null);
  const [uploading, setUploading] = useState(false);

  const val = (field: keyof CompanyDoc): string =>
    String((field in form ? form[field] : doc?.[field]) ?? "");

  const checked = (field: keyof CompanyDoc): boolean => {
    const raw = field in form ? form[field] : doc?.[field];
    return Boolean(Number(raw));
  };

  const touch = (patch: Partial<CompanyDoc>) => {
    setSaved(false);
    setSaveErr(null);
    setForm((f) => ({ ...f, ...patch }));
  };

  const setLink = (field: keyof CompanyDoc, value: string) => touch({ [field]: value });

  const setText =
    (field: keyof CompanyDoc) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      touch({ [field]: e.target.value });

  const setCheck = (field: keyof CompanyDoc) => (e: React.ChangeEvent<HTMLInputElement>) =>
    touch({ [field]: e.target.checked ? 1 : 0 });

  function editableKeys(): (keyof CompanyDoc)[] {
    const accountsKeys: (keyof CompanyDoc)[] = [
      "default_bank_account",
      "default_cash_account",
      "default_receivable_account",
      "default_payable_account",
      "default_income_account",
      "default_expense_account",
      "default_deferred_revenue_account",
      "default_deferred_expense_account",
      "round_off_account",
      "write_off_account",
      "exchange_gain_loss_account",
      "cost_center",
      "payment_terms",
      "default_advance_received_account",
      "default_advance_paid_account",
      "default_discount_account",
      "enable_perpetual_inventory",
      "default_inventory_account",
      "stock_adjustment_account",
      "stock_received_but_not_billed",
      "default_warehouse_for_sales_return",
      "default_in_transit_warehouse",
      "default_wip_warehouse",
      "default_fg_warehouse",
      "default_scrap_warehouse",
      "valuation_method",
      "accumulated_depreciation_account",
      "depreciation_expense_account",
      "disposal_account",
      "capital_work_in_progress_account",
      "default_selling_terms",
      "default_buying_terms",
      "credit_limit",
      "monthly_sales_target",
      "taxmate_vat_filing_frequency",
      "taxmate_vat_first_period_start",
      "taxmate_assigned_accountant",
      "accounts_frozen_till_date",
      "role_allowed_for_frozen_entries",
    ];
    const ownerKeys: (keyof CompanyDoc)[] = [
      "company_name",
      "abbr",
      "company_logo",
      "tax_id",
      "country",
      "default_currency",
      "domain",
      "date_of_establishment",
      "date_of_incorporation",
      "default_letter_head",
      "default_holiday_list",
      "phone_no",
      "fax",
      "email",
      "website",
      "trade_license_number",
      "legal_registration_identifier_type",
      "legal_registration_identifier",
      "uae_peppol_id",
      "uae_fz_beneficiary_id",
      "uae_in_designated_zone",
      "uae_e_invoice_enabled",
      "uae_is_government_entity",
      "uae_e_invoice_revenue_band",
      "uae_e_invoice_cohort_override",
    ];
    if (canFull) return [...ownerKeys, ...accountsKeys];
    if (canAccounts) return accountsKeys;
    return [];
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!doc || (!canFull && !canAccounts)) return;
    const allowed = new Set(editableKeys());
    const payload: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(form)) {
      if (allowed.has(k as keyof CompanyDoc)) payload[k] = v;
    }
    if (!Object.keys(payload).length) return;
    setSaveErr(null);
    setSaved(false);
    try {
      await updateDoc(DT.company, doc.name, payload);
      setSaved(true);
      setForm({});
      void res.mutate();
    } catch (err) {
      setSaveErr(readableError(err));
    }
  }

  async function onLogoPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !company || !canFull) return;
    setUploading(true);
    setSaveErr(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("company", company);
      const resp = await apiFetch(`/api/method/${METHOD.uploadCompanyLogo}`, {
        method: "POST",
        headers: { "X-Frappe-CSRF-Token": window.csrf_token || "" },
        body,
      });
      const data = await resp.json();
      if (!resp.ok || data.exc) {
        throw new Error(typeof data.message === "string" ? data.message : t("cs.logoFailed"));
      }
      const url = String(data.message?.file_url || "");
      if (url) touch({ company_logo: url });
      void res.mutate();
    } catch (err) {
      setSaveErr(readableError(err));
    } finally {
      setUploading(false);
    }
  }

  if (!company) return <div className="page"><p className="od-note">{t("od.noAccess")}</p></div>;
  if (res.error) return <div className="page"><ErrorBox error={res.error} onRetry={() => void res.mutate()} /></div>;
  if (!doc) return <div className="page"><Loading /></div>;

  const abbr = doc.abbr;
  const canSave = canFull || canAccounts;
  const dirty = Object.keys(form).some((k) => editableKeys().includes(k as keyof CompanyDoc));
  const logo = val("company_logo");
  const freq = val("taxmate_vat_filing_frequency");

  function accountField(
    field: keyof CompanyDoc,
    labelKey: string,
    accountType?: string,
  ) {
    return (
      <Field key={field} label={t(labelKey)}>
        <LinkField
          doctype={DT.account}
          value={val(field)}
          disabled={!canAccounts}
          onChange={(v) => setLink(field, v)}
          filters={ACCOUNT_FILTERS(company, accountType)}
        />
      </Field>
    );
  }

  function warehouseField(field: keyof CompanyDoc, labelKey: string) {
    return (
      <Field key={field} label={t(labelKey)}>
        <LinkField
          doctype={DT.warehouse}
          value={val(field)}
          disabled={!canAccounts}
          onChange={(v) => setLink(field, v)}
          filters={WH_FILTERS(company)}
        />
      </Field>
    );
  }

  return (
    <div className="odash">
      <PageHead
        title={t("nav.companySettings")}
        sub={doc.company_name}
        actions={<DocHistory doctype={DT.company} name={doc.name} />}
      />

      <div className="ftabs" role="tablist" aria-label={t("nav.companySettings")}>
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`cs-tab-${item.id}`}
            aria-controls={`cs-panel-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            className={`ftab${tab === item.id ? " on" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {t(item.label)}
          </button>
        ))}
      </div>

      <form onSubmit={(e) => void handleSave(e)}>
        {tab === "identity" && (
          <div role="tabpanel" id="cs-panel-identity" aria-labelledby="cs-tab-identity">
            <section className="card">
              <div className="chead"><h2>{t("cs.identity")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.companyName")} required>
                    <input className="ctl" value={val("company_name")} onChange={setText("company_name")} disabled={!canFull} required={canFull} />
                  </Field>
                  <Field label={t("cs.abbr")} hint={abbr ? t("cs.abbrLocked") : undefined}>
                    <input className={`ctl${abbr ? " readonly" : ""}`} value={val("abbr")} onChange={setText("abbr")} disabled={!canFull || !!abbr} readOnly={!!abbr} />
                  </Field>
                  <Field label={t("cs.logo")}>
                    <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                      {logo ? (
                        <img src={fileUrl(logo)} alt="" style={{ height: 48, maxWidth: 120, objectFit: "contain" }} />
                      ) : (
                        <span className="od-note">{t("cs.logoEmpty")}</span>
                      )}
                      {canFull && (
                        <>
                          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => void onLogoPicked(e)} />
                          <button type="button" className="btn quiet" disabled={uploading} onClick={() => fileRef.current?.click()}>
                            {uploading ? "…" : t("cs.logoUpload")}
                          </button>
                        </>
                      )}
                    </div>
                  </Field>
                  <Field label={t("cs.taxId")}>
                    <input className="ctl" value={val("tax_id")} onChange={setText("tax_id")} disabled={!canFull} placeholder="100XXXXXXXXX0003" />
                  </Field>
                  <Field label={t("cs.country")}>
                    <LinkField doctype="Country" value={val("country")} disabled={!canFull} onChange={(v) => setLink("country", v)} />
                  </Field>
                  <Field label={t("cs.currency")}>
                    <LinkField doctype="Currency" value={val("default_currency")} disabled={!canFull} onChange={(v) => setLink("default_currency", v)} />
                  </Field>
                  <Field label={t("cs.domain")}>
                    <input className="ctl" value={val("domain")} onChange={setText("domain")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.dateOfEstablishment")}>
                    <input className="ctl" type="date" value={val("date_of_establishment")} onChange={setText("date_of_establishment")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.dateOfIncorporation")}>
                    <input className="ctl" type="date" value={val("date_of_incorporation")} onChange={setText("date_of_incorporation")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.letterHead")}>
                    <LinkField doctype="Letter Head" value={val("default_letter_head")} disabled={!canFull} onChange={(v) => setLink("default_letter_head", v)} />
                  </Field>
                  <Field label={t("cs.holidayList")}>
                    <LinkField doctype="Holiday List" value={val("default_holiday_list")} disabled={!canFull} onChange={(v) => setLink("default_holiday_list", v)} />
                  </Field>
                </div>
              </div>
            </section>
          </div>
        )}

        {tab === "contact" && (
          <div role="tabpanel" id="cs-panel-contact" aria-labelledby="cs-tab-contact">
            <section className="card">
              <div className="chead"><h2>{t("cs.contact")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.phone")}>
                    <input className="ctl" type="tel" value={val("phone_no")} onChange={setText("phone_no")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.fax")}>
                    <input className="ctl" value={val("fax")} onChange={setText("fax")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.email")}>
                    <input className="ctl" type="email" value={val("email")} onChange={setText("email")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.website")}>
                    <input className="ctl" type="url" value={val("website")} onChange={setText("website")} disabled={!canFull} placeholder="https://" />
                  </Field>
                </div>
              </div>
            </section>
            <section className="card">
              <div className="chead" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <h2>{t("cs.addresses")}</h2>
                <Link className="btn quiet" to="/addresses">{t("cs.manageAddresses")}</Link>
              </div>
              <div className="cbody">
                {addrs.error && <ErrorBox error={addrs.error} onRetry={() => void addrs.mutate()} />}
                {!addrs.data && !addrs.error && <Loading />}
                {addrs.data?.message?.length === 0 && <p className="od-note">{t("cs.noAddresses")}</p>}
                <ul className="stack" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {(addrs.data?.message || []).map((a) => (
                    <li key={a.name} style={{ marginBottom: 8 }}>
                      <Link to={`/addresses/${encodeURIComponent(a.name)}`} className="ordno">
                        {a.address_title || a.name}
                      </Link>
                      <span className="od-note">
                        {" · "}
                        {[a.address_type, a.address_line1, a.city, a.country].filter(Boolean).join(" · ")}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          </div>
        )}

        {tab === "accounts" && (
          <div role="tabpanel" id="cs-panel-accounts" aria-labelledby="cs-tab-accounts">
            <section className="card">
              <div className="chead"><h2>{t("cs.accounts")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  {accountField("default_bank_account", "cs.bank", "Bank")}
                  {accountField("default_cash_account", "cs.cash", "Cash")}
                  {accountField("default_receivable_account", "cs.receivable", "Receivable")}
                  {accountField("default_payable_account", "cs.payable", "Payable")}
                  {accountField("default_income_account", "cs.income", "Income Account")}
                  {accountField("default_expense_account", "cs.expense", "Expense Account")}
                  {accountField("default_deferred_revenue_account", "cs.deferredRevenue")}
                  {accountField("default_deferred_expense_account", "cs.deferredExpense")}
                  {accountField("round_off_account", "cs.roundOff")}
                  {accountField("write_off_account", "cs.writeOff")}
                  {accountField("exchange_gain_loss_account", "cs.exchangeGainLoss")}
                  {accountField("default_advance_received_account", "cs.advanceReceived")}
                  {accountField("default_advance_paid_account", "cs.advancePaid")}
                  {accountField("default_discount_account", "cs.discountAccount")}
                  <Field label={t("cs.costCenter")}>
                    <LinkField
                      doctype={DT.costCenter}
                      value={val("cost_center")}
                      disabled={!canAccounts}
                      onChange={(v) => setLink("cost_center", v)}
                      filters={[["company", "=", company], ["is_group", "=", 0]]}
                    />
                  </Field>
                  <Field label={t("cs.paymentTerms")}>
                    <LinkField
                      doctype={DT.paymentTerms}
                      value={val("payment_terms")}
                      disabled={!canAccounts}
                      onChange={(v) => setLink("payment_terms", v)}
                    />
                  </Field>
                </div>
              </div>
            </section>
          </div>
        )}

        {tab === "stock" && (
          <div role="tabpanel" id="cs-panel-stock" aria-labelledby="cs-tab-stock">
            <section className="card">
              <div className="chead"><h2>{t("cs.stockAssets")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.perpetualInventory")}>
                    <input className="check" type="checkbox" checked={checked("enable_perpetual_inventory")} onChange={setCheck("enable_perpetual_inventory")} disabled={!canAccounts} />
                  </Field>
                  <Field label={t("cs.valuationMethod")}>
                    <select className="ctl" value={val("valuation_method") || "FIFO"} onChange={setText("valuation_method")} disabled={!canAccounts}>
                      <option value="FIFO">FIFO</option>
                      <option value="Moving Average">{t("item.valuation.moving")}</option>
                      <option value="LIFO">LIFO</option>
                    </select>
                  </Field>
                  {accountField("default_inventory_account", "cs.inventoryAccount", "Stock")}
                  {accountField("stock_adjustment_account", "cs.stockAdjustment")}
                  {accountField("stock_received_but_not_billed", "cs.srnb")}
                  {warehouseField("default_warehouse_for_sales_return", "cs.salesReturnWarehouse")}
                  {warehouseField("default_in_transit_warehouse", "cs.inTransitWarehouse")}
                  {warehouseField("default_wip_warehouse", "cs.wipWarehouse")}
                  {warehouseField("default_fg_warehouse", "cs.fgWarehouse")}
                  {warehouseField("default_scrap_warehouse", "cs.scrapWarehouse")}
                  {accountField("accumulated_depreciation_account", "cs.accumDepreciation")}
                  {accountField("depreciation_expense_account", "cs.depreciationExpense")}
                  {accountField("disposal_account", "cs.disposalAccount")}
                  {accountField("capital_work_in_progress_account", "cs.cwip")}
                </div>
              </div>
            </section>
          </div>
        )}

        {tab === "buying" && (
          <div role="tabpanel" id="cs-panel-buying" aria-labelledby="cs-tab-buying">
            <section className="card">
              <div className="chead"><h2>{t("cs.buyingSelling")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.sellingTerms")}>
                    <LinkField
                      doctype={DT.termsAndConditions}
                      value={val("default_selling_terms")}
                      disabled={!canAccounts}
                      onChange={(v) => setLink("default_selling_terms", v)}
                      filters={[["selling", "=", 1]]}
                    />
                  </Field>
                  <Field label={t("cs.buyingTerms")}>
                    <LinkField
                      doctype={DT.termsAndConditions}
                      value={val("default_buying_terms")}
                      disabled={!canAccounts}
                      onChange={(v) => setLink("default_buying_terms", v)}
                      filters={[["buying", "=", 1]]}
                    />
                  </Field>
                  <Field label={t("cs.creditLimit")}>
                    <input className="ctl" type="number" step="0.01" value={val("credit_limit")} onChange={setText("credit_limit")} disabled={!canAccounts} />
                  </Field>
                  <Field label={t("cs.monthlySalesTarget")}>
                    <input className="ctl" type="number" step="0.01" value={val("monthly_sales_target")} onChange={setText("monthly_sales_target")} disabled={!canAccounts} />
                  </Field>
                </div>
              </div>
            </section>
          </div>
        )}

        {tab === "uae" && (
          <div role="tabpanel" id="cs-panel-uae" aria-labelledby="cs-tab-uae">
            <section className="card">
              <div className="chead"><h2>{t("cs.uaeLegal")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.tradeLicense")}>
                    <input className="ctl" value={val("trade_license_number")} onChange={setText("trade_license_number")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.legalIdType")}>
                    <select className="ctl" value={val("legal_registration_identifier_type")} onChange={setText("legal_registration_identifier_type")} disabled={!canFull}>
                      <option value="">—</option>
                      <option value="CRN">CRN</option>
                      <option value="OTH">OTH</option>
                    </select>
                  </Field>
                  <Field label={t("cs.legalId")}>
                    <input className="ctl" value={val("legal_registration_identifier")} onChange={setText("legal_registration_identifier")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.peppolId")}>
                    <input className="ctl" value={val("uae_peppol_id")} onChange={setText("uae_peppol_id")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.fzBeneficiary")}>
                    <input className="ctl" value={val("uae_fz_beneficiary_id")} onChange={setText("uae_fz_beneficiary_id")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.designatedZone")}>
                    <input className="check" type="checkbox" checked={checked("uae_in_designated_zone")} onChange={setCheck("uae_in_designated_zone")} disabled={!canFull} />
                  </Field>
                </div>
              </div>
            </section>
            <section className="card">
              <div className="chead"><h2>{t("cs.eInvoice")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.eInvoiceEnabled")}>
                    <input className="check" type="checkbox" checked={checked("uae_e_invoice_enabled")} onChange={setCheck("uae_e_invoice_enabled")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.governmentEntity")}>
                    <input className="check" type="checkbox" checked={checked("uae_is_government_entity")} onChange={setCheck("uae_is_government_entity")} disabled={!canFull} />
                  </Field>
                  <Field label={t("cs.revenueBand")}>
                    <select className="ctl" value={val("uae_e_invoice_revenue_band")} onChange={setText("uae_e_invoice_revenue_band")} disabled={!canFull}>
                      <option value="">—</option>
                      <option value="Below AED 50,000,000">{t("co.einv.bandBelow")}</option>
                      <option value="AED 50,000,000 or more">{t("co.einv.bandAtOrAbove")}</option>
                    </select>
                  </Field>
                  <Field label={t("cs.cohortOverride")}>
                    <select className="ctl" value={val("uae_e_invoice_cohort_override") || "Auto"} onChange={setText("uae_e_invoice_cohort_override")} disabled={!canFull}>
                      <option value="Auto">{t("co.einv.cohortAuto")}</option>
                      <option value="Pilot">{t("co.einv.cohortPilot")}</option>
                      <option value="Large">{t("co.einv.cohortLarge")}</option>
                      <option value="SME">{t("co.einv.cohortSme")}</option>
                      <option value="Government">{t("co.einv.cohortGovernment")}</option>
                    </select>
                  </Field>
                </div>
              </div>
            </section>
            <section className="card">
              <div className="chead"><h2>{t("cs.practice")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.vatFrequency")} hint={t("cs.vatFrequencyHelp")}>
                    <select className="ctl" value={freq} onChange={setText("taxmate_vat_filing_frequency")} disabled={!canAccounts}>
                      <option value="">—</option>
                      <option value="Monthly">{t("co.vat.freqMonthly")}</option>
                      <option value="Quarterly">{t("co.vat.freqQuarterly")}</option>
                    </select>
                  </Field>
                  {freq === "Quarterly" && (
                    <Field label={t("cs.vatPeriodStart")}>
                      <input className="ctl" type="date" value={val("taxmate_vat_first_period_start")} onChange={setText("taxmate_vat_first_period_start")} disabled={!canAccounts} />
                    </Field>
                  )}
                  <Field label={t("cs.assignedAccountant")} hint={t("cs.assignedAccountantHelp")}>
                    <select
                      className="ctl"
                      value={val("taxmate_assigned_accountant")}
                      disabled={!canAccounts}
                      onChange={setText("taxmate_assigned_accountant")}
                    >
                      <option value="">—</option>
                      {(team.data?.message || []).map((u) => (
                        <option key={u.name} value={u.name}>
                          {u.full_name || u.email || u.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
              </div>
            </section>
          </div>
        )}

        {tab === "books" && (
          <div role="tabpanel" id="cs-panel-books" aria-labelledby="cs-tab-books">
            <section className="card">
              <div className="chead"><h2>{t("cs.booksLock")}</h2></div>
              <div className="cbody">
                <div className="grid2">
                  <Field label={t("cs.frozenTill")} hint={t("cs.frozenTillHelp")}>
                    <input
                      className="ctl"
                      type="date"
                      value={val("accounts_frozen_till_date")}
                      onChange={setText("accounts_frozen_till_date")}
                      disabled={!canAccounts}
                    />
                  </Field>
                  <Field label={t("cs.frozenRole")} hint={t("cs.frozenRoleHelp")}>
                    <input
                      className="ctl"
                      value={val("role_allowed_for_frozen_entries")}
                      onChange={setText("role_allowed_for_frozen_entries")}
                      disabled={!canAccounts}
                      placeholder={t("co.ph.accountsManager")}
                    />
                  </Field>
                </div>
              </div>
            </section>
          </div>
        )}

        {saveErr && (
          <div className="card">
            <div className="cbody">
              {saveErr.map((e, i) => <p key={i} className="od-bad">{e}</p>)}
            </div>
          </div>
        )}

        {saved && (
          <div className="card">
            <div className="cbody"><p className="od-ok">{t("cs.saved")}</p></div>
          </div>
        )}

        {canSave && (
          <div style={{ display: "flex", gap: 10, paddingBlockStart: 4 }}>
            <button type="submit" className="btn" disabled={saving || !dirty}>
              {saving ? "…" : t("common.save")}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
