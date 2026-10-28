/**
 * Sales Invoice create/edit. Catalog: resource + workflow + accounts preview helpers.
 * Routes: /invoices/new, /invoices/:name/edit
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { INV_PILL_CLASS, invoiceUiStatus } from "../../lib/status";
import { applyLineRate, linePayload, mappedItem, orderDiscountFields, productDiscountTotal, readDiscountBasis, stampItemDetails, useCreditBalance, usePaymentSchedule, useTotalsPreview, useTransactionRpc, type DiscountBasis, type PartyDetails, type TxnLine } from "../../lib/txn";
import { CreditLimitNotice, LineDiscountInput, LineTrack, OrderDiscountFields, PartyFields, PaymentScheduleTable, TxnTotals } from "../../components/txnFields";
import { UAE_EMIRATES } from "../../types/uae";
import { t } from "../../i18n/strings";
import { CREDIT_NOTE_REASON_LABELS, CREDIT_NOTE_REASONS, creditNoteReasonCode } from "../../lib/creditNoteReason";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead, Pill } from "../../components/ui";
import { FormLayout, MissingSummary, ReadinessCard, type Check } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";
import SourceDocPicker from "../../components/SourceDocPicker";

type InvoiceDoc = {
  name: string;
  customer?: string;
  customer_name?: string;
  posting_date?: string;
  due_date?: string;
  po_no?: string;
  company?: string;
  vat_emirate?: string;
  taxes_and_charges?: string;
  tax_id?: string;
  company_trn?: string;
  payment_terms_template?: string;
  selling_price_list?: string;
  customer_address?: string;
  shipping_address_name?: string;
  contact_person?: string;
  debit_to?: string;
  additional_discount_percentage?: number;
  apply_discount_on?: string;
  update_stock?: number;
  set_warehouse?: string;
  net_total?: number;
  total_taxes_and_charges?: number;
  grand_total?: number;
  outstanding_amount?: number;
  currency?: string;
  conversion_rate?: number;
  docstatus?: 0 | 1 | 2;
  status?: string;
  is_return?: number;
  return_against?: string;
  uae_e_invoice_status?: string;
  uae_credit_note_reason?: string;
  items?: TxnLine[];
};

export default function InvoiceForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<InvoiceDoc>(DT.salesInvoice, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const defaults = useFrappePostCall<{ message: { company?: string; currency?: string; tax_id?: string } }>(METHOD.getDefaults);
  const submitCall = useFrappePostCall<{ message: InvoiceDoc }>(METHOD.submit);
  const create = useInsert();
  const update = useSave();
  const templates = useDocList<{ name: string }>(DT.taxTemplate, { fields: ["name"], limit: 50 });
  const terms = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });

  const [customer, setCustomer] = useState("");
  const [postingDate, setPostingDate] = useState(toIsoDate(new Date()));
  const [dueDate, setDueDate] = useState("");
  const [poNo, setPoNo] = useState("");
  const [emirate, setEmirate] = useState("");
  const [taxTemplate, setTaxTemplate] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [discountPct, setDiscountPct] = useState(0);
  const [discountOn, setDiscountOn] = useState<DiscountBasis>("Net Total");
  const [updateStock, setUpdateStock] = useState<0 | 1>(0);
  const [setWarehouse, setSetWarehouse] = useState("");
  const [currency, setCurrency] = useState("");
  const [conversionRate, setConversionRate] = useState(1);
  const [party, setParty] = useState<PartyDetails>({});
  const [companyDefaults, setCompanyDefaults] = useState<{ company?: string; currency?: string; tax_id?: string }>({});
  const [lines, setLines] = useState<TxnLine[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [skipReprice, setSkipReprice] = useState(false);
  const [showMissing, setShowMissing] = useState(false);
  const missingRef = useRef<HTMLDivElement>(null);

  const company = companyDefaults.company || session.company;
  const companyCurrency = companyDefaults.currency || session.currency || "";
  const txn = useTransactionRpc({ doctype: DT.salesInvoice, side: "selling", company });

  useEffect(() => {
    defaults.call({}).then((r) => setCompanyDefaults(r?.message ?? {})).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setCustomer(d.customer || "");
    setPostingDate(d.posting_date || toIsoDate(new Date()));
    setDueDate(d.due_date || "");
    setPoNo(d.po_no || "");
    setEmirate(d.vat_emirate || "");
    setParty({
      customer_address: d.customer_address,
      shipping_address_name: d.shipping_address_name,
      contact_person: d.contact_person,
      selling_price_list: d.selling_price_list,
      debit_to: d.debit_to,
    });
    setTaxTemplate(d.taxes_and_charges || "");
    setPaymentTerms(d.payment_terms_template || "");
    setDiscountPct(Number(d.additional_discount_percentage || 0));
    setDiscountOn(readDiscountBasis(d.apply_discount_on, Number(d.additional_discount_percentage) > 0));
    setUpdateStock(d.update_stock ? 1 : 0);
    setSetWarehouse(d.set_warehouse || "");
    setCurrency(d.currency || "");
    setConversionRate(Number(d.conversion_rate) || 1);
    setReason(creditNoteReasonCode(d.uae_credit_note_reason));
    setLines((d.items ?? []).map((l) => ({
      ...l,
      qty: l.qty,
      rate: l.rate,
      is_free_item: l.is_free_item ? 1 : 0,
      uae_is_margin_scheme: l.uae_is_margin_scheme ? 1 : 0,
      has_batch_no: l.batch_no ? 1 : 0,
      has_serial_no: l.serial_no ? 1 : 0,
    })));
    setSkipReprice(true);
  }, [existing.data]);

  useEffect(() => {
    if (!customer) return;
    void txn.fetchParty(customer, postingDate).then(async (m) => {
      if (!m) return;
      if (skipReprice) {
        setSkipReprice(false);
        return;
      }
      setParty(m);
      if (m.taxes_and_charges) setTaxTemplate(m.taxes_and_charges);
      if (m.vat_emirate) setEmirate(m.vat_emirate);
      if (m.payment_terms_template) setPaymentTerms(m.payment_terms_template);
      if (m.due_date && !dueDate) setDueDate(m.due_date);
      const cur = m.currency || companyCurrency;
      if (cur) setCurrency(cur);
      const rate = await txn.fetchExchangeRate(cur || companyCurrency, companyCurrency, postingDate);
      setConversionRate(rate);
      if (lines.some((l) => l.item_code)) {
        const next = await txn.repriceLines({
          party: m,
          lines,
          transactionDate: postingDate,
          currency: cur,
          conversionRate: rate,
          customer,
        });
        setLines(next);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer]);


  const keepSavedRate = useRef(name !== "new");
  useEffect(() => {
    if (keepSavedRate.current) {
      if (existing.data) keepSavedRate.current = false;
      return;
    }
    if (!currency || !companyCurrency || currency === companyCurrency) {
      setConversionRate(1);
      return;
    }
    let cancelled = false;
    void txn.fetchExchangeRate(currency, companyCurrency, postingDate).then((rate) => {
      if (!cancelled && rate > 0) setConversionRate(rate);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currency, companyCurrency, postingDate, existing.data]);

  async function pickItem(idx: number, item_code: string) {
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, item_code } : l)));
    const m = await txn.fetchItem({
      item_code,
      customer,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: conversionRate,
      selling_price_list: party.selling_price_list,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  const buildPreviewDoc = useCallback(() => {
    if (!customer || !lines.some((l) => l.item_code)) return null;
    return {
      customer,
      posting_date: postingDate,
      due_date: dueDate || undefined,
      company,
      vat_emirate: emirate || undefined,
      taxes_and_charges: taxTemplate || undefined,
      payment_terms_template: paymentTerms || undefined,
      customer_address: party.customer_address,
      shipping_address_name: party.shipping_address_name,
      contact_person: party.contact_person,
      selling_price_list: party.selling_price_list,
      debit_to: party.debit_to,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: (!currency || currency === companyCurrency) ? 1 : conversionRate,
      ...orderDiscountFields(discountPct, discountOn),
      update_stock: updateStock,
      set_warehouse: updateStock ? setWarehouse || undefined : undefined,
      items: lines.filter((l) => l.item_code).map((l) => linePayload(l)),
    };
  }, [
    customer, postingDate, dueDate, company, emirate, taxTemplate, paymentTerms,
    party, companyDefaults, session.currency, discountPct, discountOn, lines, currency, conversionRate, companyCurrency,
  ]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [customer, postingDate, taxTemplate, emirate, discountPct, discountOn, updateStock, setWarehouse, lines, currency, conversionRate],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const scheduleGrand = preview?.grand_total ?? net;
  const baseGrand = scheduleGrand * (conversionRate || 1);
  const schedule = usePaymentSchedule(paymentTerms || undefined, postingDate, scheduleGrand, baseGrand);
  const credit = useCreditBalance(customer || undefined, company, baseGrand);
  const doc = existing.data;
  const locked = false;
  const canSubmit = canSubmitSales(session.roles);
  const ready =
    !!customer &&
    !!postingDate &&
    !!emirate &&
    !!taxTemplate &&
    lines.length > 0 &&
    lines.every((l) => l.item_code) &&
    (!currency || currency === companyCurrency || conversionRate > 0);
  const checks: Check[] = [
    { ok: !!customer, label: t("f.customer") },
    { ok: !!postingDate, label: t("inv.date") },
    { ok: !!emirate, label: t("f.emirate") },
    { ok: !!taxTemplate, label: t("f.taxTemplate") },
    { ok: lines.length > 0 && lines.every((l) => l.item_code), label: t("inv.lines") },
    { ok: !currency || currency === companyCurrency || conversionRate > 0, label: t("f.conversionRate") },
  ];
  const displayCurrency = currency || doc?.currency || party.currency || companyDefaults.currency || session.currency || undefined;

  function requireReady(): boolean {
    if (ready) {
      setShowMissing(false);
      return true;
    }
    setShowMissing(true);
    queueMicrotask(() => missingRef.current?.focus());
    return false;
  }

  function payload() {
    return {
      customer,
      posting_date: postingDate,
      due_date: dueDate || undefined,
      po_no: poNo || undefined,
      company,
      vat_emirate: emirate,
      taxes_and_charges: taxTemplate || undefined,
      payment_terms_template: paymentTerms || undefined,
      customer_address: party.customer_address,
      shipping_address_name: party.shipping_address_name,
      contact_person: party.contact_person,
      selling_price_list: party.selling_price_list,
      debit_to: party.debit_to,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: (!currency || currency === companyCurrency) ? 1 : conversionRate,
      ...orderDiscountFields(discountPct, discountOn),
      update_stock: updateStock,
      set_warehouse: updateStock ? setWarehouse || undefined : undefined,
      uae_credit_note_reason: reason || undefined,
      payment_schedule: schedule.length
        ? schedule.map((r) => ({
            payment_term: r.payment_term,
            description: r.description,
            due_date: r.due_date,
            invoice_portion: r.invoice_portion,
            payment_amount: r.payment_amount,
            mode_of_payment: r.mode_of_payment,
          }))
        : undefined,
      items: lines.map((l) => ({
        ...linePayload(l),
        warehouse: l.warehouse || (updateStock ? setWarehouse || undefined : undefined),
      })),
    };
  }

  async function applyMapped(mapped: Record<string, unknown>) {
    setSkipReprice(true);
    if (mapped.customer) setCustomer(String(mapped.customer));
    if (mapped.posting_date) setPostingDate(String(mapped.posting_date));
    if (mapped.due_date) setDueDate(String(mapped.due_date));
    if (mapped.vat_emirate) setEmirate(String(mapped.vat_emirate));
    if (mapped.taxes_and_charges) setTaxTemplate(String(mapped.taxes_and_charges));
    if (mapped.payment_terms_template) setPaymentTerms(String(mapped.payment_terms_template));
    if (mapped.po_no) setPoNo(String(mapped.po_no));
    if (mapped.update_stock != null) setUpdateStock(mapped.update_stock ? 1 : 0);
    if (mapped.set_warehouse) setSetWarehouse(String(mapped.set_warehouse));
    const items = (mapped.items as TxnLine[] | undefined) ?? [];
    setLines(items.map((l) => mappedItem(l, String(mapped.set_warehouse || ""))));
  }

  async function save() {
    if (!requireReady()) return;
    setBusy(true); setSaveError(null);
    try {
      const docname = isNew
        ? ((await create.createDoc(DT.salesInvoice, payload())) as { name: string }).name
        : (await update.updateDoc(DT.salesInvoice, name, payload()), name);
      nav(`/invoices/${encodeURIComponent(docname)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  async function submitDoc() {
    if (!requireReady()) return;
    setBusy(true); setSaveError(null);
    try {
      let docname = name;
      if (isNew) {
        const created = await create.createDoc(DT.salesInvoice, payload());
        docname = (created as { name: string }).name;
      } else {
        await update.updateDoc(DT.salesInvoice, name, payload());
      }
      await submitCall.call({ doc: { doctype: DT.salesInvoice, name: docname } });
      nav(`/invoices/${encodeURIComponent(docname)}`);
    } catch (err) {
      setSaveError(err);
      if (!isNew) await existing.mutate();
    } finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data && existing.data.docstatus !== 0) {
    return <Navigate to={`/invoices/${encodeURIComponent(name)}`} replace />;
  }

  const ui = invoiceUiStatus(doc ?? { docstatus: 0 });
  const showNet = preview?.net_total ?? doc?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? doc?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? doc?.grand_total ?? net;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/invoices")}>{t("nav.invoices")}</button>}
        title={isNew ? t("inv.new") : (doc?.customer_name || customer || name)}
        actions={
          <>
            <button className="btn ghost" onClick={() => nav("/invoices")}>{t("soc.discard")}</button>
            {!locked && (
              <button className="btn ghost" disabled={busy} onClick={() => void save()}>
                {busy ? t("soc.saving") : t("soc.save")}
              </button>
            )}
            {!locked && canSubmit && (
              <button className="btn" disabled={busy} onClick={() => void submitDoc()}>{t("inv.submit")}</button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <Pill cls={INV_PILL_CLASS[ui]}>{t(`inv.status.${ui}`)}</Pill>
        </p>
      </PageHead>

      {(saveError || txn.pricingError || txn.partyCall.error || submitCall.error) && (
        <ErrorBox error={saveError || txn.pricingError || txn.partyCall.error || submitCall.error} />
      )}
      <MissingSummary checks={checks} active={showMissing} summaryRef={missingRef} />

      <FormLayout aside={
        <>
          <ReadinessCard checks={checks} title={t("soc.ready")} caption={t("soc.readyCap")} />
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>
              {t("inv.totals")}{previewing ? "…" : ""}
            </h2>
            <TxnTotals
              currency={displayCurrency}
              itemsTotal={preview?.total ?? net}
              productDiscount={productDiscountTotal(lines)}
              orderDiscount={preview?.discount_amount}
              orderDiscountPercent={discountPct}
              discountOn={discountOn}
              net={showNet}
              vat={showVat}
              grand={showGrand}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("sod.grand")}
            />
          </Card>
        </>
      }>
          {isNew && (
            <Card title={t("txn.getItemsFrom")}>
              <SourceDocPicker
                sources={[
                  { label: t("nav.salesOrders"), doctype: DT.salesOrder, method: METHOD.makeSalesInvoice, arg: "source_name",
                    filters: [["docstatus", "=", 1], ["status", "not in", ["Closed", "On Hold"]], ["per_billed", "<", 99.99]] },
                  { label: t("nav.deliveryNotes"), doctype: DT.deliveryNote, method: METHOD.makeDnSalesInvoice, arg: "source_name",
                    filters: [["docstatus", "=", 1], ["is_return", "=", 0], ["status", "not in", ["Stopped", "Closed"]], ["per_billed", "<", 100]] },
                ]}
                onMapped={(m) => void applyMapped(m)}
              />
            </Card>
          )}

          <Card num={1} title={t("inv.who")}>
            <div className="grid2">
              <Field label={t("f.customer")} required>
                <LinkField doctype={DT.customer} value={customer} onChange={setCustomer} disabled={locked} />
              </Field>
              <Field label={t("inv.date")} required>
                <input className="ctl" type="date" value={postingDate} disabled={locked}
                  onChange={(e) => setPostingDate(e.target.value)} />
              </Field>
              <Field label={t("inv.due")}>
                <input className="ctl" type="date" value={dueDate} disabled={locked}
                  onChange={(e) => setDueDate(e.target.value)} />
              </Field>
              <Field label={t("f.poNo")}>
                <input className="ctl" value={poNo} disabled={locked} onChange={(e) => setPoNo(e.target.value)} />
              </Field>
            </div>
            <PartyFields
              side="selling"
              partyName={customer}
              party={party}
              disabled={locked}
              onChange={(patch) => setParty((p) => ({ ...p, ...patch }))}
            />
            <div className="numblk">
              <span className="infochip"><span className="k2">T</span>{t("f.customerTrn")} <b>{party.tax_id || doc?.tax_id || "—"}</b></span>
              <span className="infochip"><span className="k2">C</span>{t("f.companyTrn")} <b>{companyDefaults.tax_id || doc?.company_trn || "—"}</b></span>
              <span className="infochip"><span className="k2">P</span>{t("f.priceList")} <b>{party.selling_price_list || "—"}</b></span>
              <span className="infochip"><span className="k2">$</span>{t("f.currency")} <b>{currency || companyCurrency || "—"}</b></span>
            </div>
          </Card>

          <Card num={2} title={t("soc.b2")}>
            <div className="grid2">
              <Field label={t("f.emirate")} required>
                <select className="ctl" value={emirate} disabled={locked} onChange={(e) => setEmirate(e.target.value)}>
                  <option value="" />
                  {UAE_EMIRATES.map((e) => <option key={e} value={e}>{e}</option>)}
                </select>
              </Field>
              <Field label={t("f.taxTemplate")} required>
                <select className="ctl" value={taxTemplate} disabled={locked} onChange={(e) => setTaxTemplate(e.target.value)}>
                  <option value="" />
                  {(templates.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
                </select>
              </Field>
              <Field label={t("f.paymentTerms")}>
                <select className="ctl" value={paymentTerms} disabled={locked} onChange={(e) => setPaymentTerms(e.target.value)}>
                  <option value="" />
                  {(terms.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
                </select>
              </Field>
              <OrderDiscountFields
                percent={discountPct}
                basis={discountOn}
                onPercent={setDiscountPct}
                onBasis={setDiscountOn}
                disabled={locked}
              />
              <CheckField
                label={t("txn.updateStock")}
                checked={!!updateStock}
                onChange={(on) => setUpdateStock(on ? 1 : 0)}
              />
              {updateStock ? (
                <Field label={t("dn.warehouse")}>
                  <LinkField doctype={DT.warehouse} value={setWarehouse} onChange={setSetWarehouse}
                    filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
                </Field>
              ) : null}
              {currency && currency !== companyCurrency ? (
                <Field label={t("f.conversionRate")}>
                  <input className="ctl" type="number" min={0} step={0.000001} value={conversionRate} disabled={locked}
                    onChange={(e) => setConversionRate(parseNum(e.target.value) || 1)} />
                </Field>
              ) : null}
              {!!doc?.is_return && (
                <Field label={t("inv.reason")} required hint={t("inv.reasonHint")}>
                  <select className="ctl" value={creditNoteReasonCode(reason)} disabled={locked} onChange={(e) => setReason(e.target.value)}>
                    <option value="">Choose a reason</option>
                    {CREDIT_NOTE_REASONS.map((code) => (
                      <option key={code} value={code}>{CREDIT_NOTE_REASON_LABELS[code]}</option>
                    ))}
                  </select>
                </Field>
              )}
            </div>
            <PaymentScheduleTable rows={schedule} />
            <CreditLimitNotice balance={credit} />
          </Card>

          <Card num={3} title={t("inv.lines")} bodyClass={null}>
            {/* Slots chosen with Priti: Item, Quantity and Amount on the face
                of a phone card; rate and the HS/SAC codes behind "More". */}
            <LineItems<TxnLine>
              rows={lines}
              showIndex
              onRemove={locked ? undefined : (i) => setLines((ls) => ls.filter((_, j) => j !== i))}
              addLabel={locked ? undefined : t("soc.addLine")}
              onAdd={locked ? undefined : () => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }])}
              fields={[
                {
                  key: "item", label: t("soc.pickItem"), slot: "title", td: { minWidth: 220 },
                  render: (l, i) => (
                    <>
                      {locked ? (l.item_name || l.item_code) : (
                        <LinkField doctype={DT.item} value={l.item_code} onChange={(v) => void pickItem(i, v)} />
                      )}
                      <LineTrack
                        line={l}
                        disabled={locked}
                        onChange={(patch) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, ...patch } : x))}
                      />
                    </>
                  ),
                },
                {
                  key: "hssac", label: t("pi.hsSac"),
                  render: (l, i) => (
                    <>
                      {l.uae_item_type !== "Service" && (
                        <input className="ctl mini" style={{ width: 88 }}
                          aria-label={t("item.hs")}
                          placeholder={t("item.hs")}
                          value={l.hs_code || ""}
                          disabled={locked}
                          onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, hs_code: e.target.value } : x))} />
                      )}
                      {l.uae_item_type !== "Goods" && (
                        <input className="ctl mini" style={{ width: 88, marginTop: l.uae_item_type === "Both" || !l.uae_item_type ? 4 : 0 }}
                          aria-label={t("item.sac")}
                          placeholder={t("item.sac")}
                          value={l.sac_code || ""}
                          disabled={locked}
                          onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, sac_code: e.target.value } : x))} />
                      )}
                    </>
                  ),
                },
                {
                  key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                  render: (l, i) => (
                    <input className="ctl mini nn" style={{ width: 80 }} value={l.qty} disabled={locked}
                      onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, qty: parseNum(e.target.value) } : x))} />
                  ),
                },
                {
                  key: "rate", label: t("sod.col.rate"), numeric: true,
                  render: (l, i) => (
                    <input className="ctl mini nn" style={{ width: 104 }} value={l.rate} disabled={locked}
                      onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? applyLineRate(x, parseNum(e.target.value)) : x))} />
                  ),
                },
                {
                  key: "discount", label: t("txn.lineDiscount"), numeric: true,
                  render: (l, i) => (
                    <LineDiscountInput
                      line={l}
                      disabled={locked}
                      onChange={(next) => setLines((ls) => ls.map((x, j) => j === i ? next : x))}
                    />
                  ),
                },
                {
                  key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                  td: { fontWeight: 600 },
                  render: (l) => <span>{money(l.qty * l.rate)}</span>,
                },
              ] as LineField<TxnLine>[]}
            />
          </Card>
      </FormLayout>
    </>
  );
}
