/**
 * Quotation create/edit. Catalog party/item/tax preview.
 * Routes: /quotations/new, /quotations/:name/edit
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { applyLineRate, linePayload, orderDiscountFields, productDiscountTotal, readDiscountBasis, stampItemDetails, usePaymentSchedule, useTotalsPreview, useTransactionRpc, type DiscountBasis, type PartyDetails, type TxnLine } from "../../lib/txn";
import { ExchangeRateField, LineDiscountInput, LineTrack, OrderDiscountFields, PartyFields, PaymentScheduleTable, TxnTotals } from "../../components/txnFields";
import { UAE_EMIRATES } from "../../types/uae";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormActions, FormLayout, ReadinessCard } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";

type Doc = {
  name: string; party_name?: string; transaction_date?: string; valid_till?: string;
  taxes_and_charges?: string; vat_emirate?: string; docstatus?: number;
  payment_terms_template?: string; additional_discount_percentage?: number; apply_discount_on?: string; tc_name?: string;
  customer_address?: string; shipping_address_name?: string; contact_person?: string;
  company_address?: string; selling_price_list?: string; currency?: string; conversion_rate?: number;
  items?: TxnLine[];
};

const today = toIsoDate(new Date());
const plus = (d: number) => { const dt = new Date(); dt.setDate(dt.getDate() + d); return toIsoDate(dt); };

function mergeDraftParty(saved: PartyDetails, fetched: PartyDetails): PartyDetails {
  return {
    ...fetched,
    customer_address: saved.customer_address ?? fetched.customer_address,
    shipping_address_name: saved.shipping_address_name ?? fetched.shipping_address_name,
    contact_person: saved.contact_person ?? fetched.contact_person,
    company_address: saved.company_address ?? fetched.company_address,
    selling_price_list: saved.selling_price_list ?? fetched.selling_price_list,
    currency: saved.currency ?? fetched.currency,
  };
}

export default function QuotationForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const canSubmit = canSubmitSales(session.roles);
  const company = session.company;

  const existing = useDoc<Doc>(DT.quotation, isNew ? undefined : name, isNew ? null : name, { isPaused: () => isNew });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall(METHOD.submit);
  const templates = useDocList<{ name: string }>(DT.taxTemplate, { fields: ["name"], limit: 50 });
  const terms = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });
  const termDocs = useDocList<{ name: string }>(DT.termsAndConditions, { fields: ["name"], filters: [["selling", "=", 1]], limit: 50 });
  const txn = useTransactionRpc({ doctype: DT.quotation, side: "selling", company });

  const [customer, setCustomer] = useState("");
  const [txDate, setTxDate] = useState(today);
  const [validTill, setValidTill] = useState(plus(30));
  const [taxTemplate, setTaxTemplate] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [discountPct, setDiscountPct] = useState(0);
  const [discountOn, setDiscountOn] = useState<DiscountBasis>("Net Total");
  const [tcName, setTcName] = useState("");
  const [emirate, setEmirate] = useState("");
  const [party, setParty] = useState<PartyDetails>({});
  const [conversionRate, setConversionRate] = useState(1);
  const [lines, setLines] = useState<TxnLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const keepDraftParty = useRef(false);
  const partyFetchId = useRef(0);

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setCustomer(d.party_name || "");
    setTxDate(d.transaction_date || today);
    setValidTill(d.valid_till || plus(30));
    setTaxTemplate(d.taxes_and_charges || "");
    setPaymentTerms(d.payment_terms_template || "");
    setDiscountPct(Number(d.additional_discount_percentage || 0));
    setDiscountOn(readDiscountBasis(d.apply_discount_on, Number(d.additional_discount_percentage) > 0));
    setTcName(d.tc_name || "");
    setEmirate(d.vat_emirate || "");
    setConversionRate(Number(d.conversion_rate) || 1);
    setParty({
      customer_address: d.customer_address,
      shipping_address_name: d.shipping_address_name,
      contact_person: d.contact_person,
      company_address: d.company_address,
      selling_price_list: d.selling_price_list,
      currency: d.currency,
    });
    setLines((d.items ?? []).map((it) => ({
      item_code: it.item_code || "",
      item_name: it.item_name,
      uom: it.uom,
      qty: Number(it.qty) || 1,
      rate: Number(it.rate) || 0,
      price_list_rate: it.price_list_rate,
      discount_percentage: it.discount_percentage,
      discount_amount: it.discount_amount,
    })));
    keepDraftParty.current = true;
  }, [existing.data]);

  useEffect(() => {
    if (!customer) return;
    const fetchId = ++partyFetchId.current;
    void txn.fetchParty(customer, txDate).then(async (m) => {
      if (fetchId !== partyFetchId.current || !m) return;
      if (keepDraftParty.current) {
        keepDraftParty.current = false;
        setParty((saved) => mergeDraftParty(saved, m));
        setEmirate((prev) => prev || m.vat_emirate || "");
        return;
      }
      setParty(m);
      if (m.taxes_and_charges) setTaxTemplate(m.taxes_and_charges);
      if (m.vat_emirate) setEmirate(m.vat_emirate);
      const cur = m.currency || session.currency || "";
      const rate = await txn.fetchExchangeRate(cur, session.currency || cur, txDate);
      setConversionRate(rate);
      if (lines.some((l) => l.item_code)) {
        setLines(await txn.repriceLines({ party: m, lines, transactionDate: txDate, currency: m.currency, conversionRate: rate, customer }));
      }
    });
    return () => {
      partyFetchId.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer]);

  async function pickItem(idx: number, item_code: string) {
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, item_code } : l)));
    const m = await txn.fetchItem({
      item_code, customer,
      currency: party.currency || session.currency,
      selling_price_list: party.selling_price_list,
      transaction_date: txDate,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  const buildPreviewDoc = useCallback(() => {
    if (!customer || !lines.some((l) => l.item_code)) return null;
    return {
      quotation_to: "Customer",
      party_name: customer,
      transaction_date: txDate,
      valid_till: validTill,
      company,
      vat_emirate: emirate,
      company_address: party.company_address || undefined,
      taxes_and_charges: taxTemplate || undefined,
      payment_terms_template: paymentTerms || undefined,
      ...orderDiscountFields(discountPct, discountOn),
      tc_name: tcName || undefined,
      selling_price_list: party.selling_price_list,
      currency: party.currency || session.currency,
      conversion_rate: conversionRate,
      items: lines.filter((l) => l.item_code).map((l) => linePayload(l)),
    };
  }, [customer, txDate, validTill, company, emirate, taxTemplate, paymentTerms, discountPct, discountOn, tcName, party, session.currency, conversionRate, lines]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [customer, txDate, taxTemplate, emirate, discountPct, discountOn, paymentTerms, lines],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const showNet = preview?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? net;
  const schedule = usePaymentSchedule(paymentTerms || undefined, txDate, showGrand, showGrand * (conversionRate || 1));

  const checks = useMemo(() => [
    { label: t("quot.customer"), ok: !!customer },
    { label: t("quot.date"), ok: !!txDate },
    { label: t("f.emirate"), ok: !!emirate },
    { label: t("f.taxTemplate"), ok: !!taxTemplate },
    { label: t("inv.lines"), ok: lines.length > 0 && lines.every((l) => l.item_code) },
  ], [customer, txDate, emirate, taxTemplate, lines]);
  const ready = checks.every((c) => c.ok);

  async function save(shouldSubmit: boolean) {
    setBusy(true); setSaveError(null);
    try {
      const payload = {
        quotation_to: "Customer",
        party_name: customer,
        transaction_date: txDate,
        valid_till: validTill,
        company,
        vat_emirate: emirate,
        company_address: party.company_address || undefined,
        taxes_and_charges: taxTemplate || undefined,
        payment_terms_template: paymentTerms || undefined,
        ...orderDiscountFields(discountPct, discountOn),
        tc_name: tcName || undefined,
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
        selling_price_list: party.selling_price_list || undefined,
        currency: party.currency || session.currency,
        conversion_rate: conversionRate,
        customer_address: party.customer_address,
        shipping_address_name: party.shipping_address_name,
        contact_person: party.contact_person,
        items: lines.map((l) => linePayload(l)),
      };
      const docname = isNew
        ? (await create.createDoc(DT.quotation, payload) as { name: string }).name
        : (await update.updateDoc(DT.quotation, name, payload), name);
      if (shouldSubmit) await submitCall.call({ doc: { doctype: DT.quotation, name: docname } });
      nav(`/quotations/${encodeURIComponent(docname)}`);
    } catch (err) {
      setSaveError(err);
    } finally {
      setBusy(false);
    }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data && existing.data.docstatus !== 0) return <Navigate to={`/quotations/${encodeURIComponent(name)}`} replace />;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/quotations")}>{t("nav.quotations")}</button>}
        title={isNew ? t("quot.new") : t("inv.edit")}
        actions={
          <FormActions
            onDiscard={() => nav("/quotations")}
            onSave={() => void save(false)}
            onSubmit={canSubmit ? () => void save(true) : undefined}
            busy={busy} ready={ready} submitLabel={t("inv.submit")}
          />
        }
      />
      {(saveError || txn.pricingError || txn.partyCall.error) && <ErrorBox error={saveError || txn.pricingError || txn.partyCall.error} />}
      <FormLayout
        aside={
          <>
            <Card bodyClass="cbody">
              <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>
                {t("quot.summary")}{previewing ? "…" : ""}
              </h2>
              <TxnTotals
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
            <ReadinessCard checks={checks} title={t("soc.ready")} caption={t("soc.readyCap")} />
          </>
        }
      >
        <Card num={1} title={t("soc.b1")}>
          <div className="grid2">
            <Field label={t("quot.customer")} required>
              <LinkField doctype={DT.customer} value={customer} onChange={setCustomer} />
            </Field>
            <Field label={t("f.customerTrn")}>
              <input className="ctl readonly" readOnly value={party.tax_id || ""} />
            </Field>
            <Field label={t("quot.date")} required htmlFor="quot-date">
              <input id="quot-date" className="ctl" type="date" value={txDate} onChange={(e) => setTxDate(e.target.value)} />
            </Field>
            <Field label={t("quot.validTill")} htmlFor="quot-valid">
              <input id="quot-valid" className="ctl" type="date" value={validTill} onChange={(e) => setValidTill(e.target.value)} />
            </Field>
            <Field label={t("f.emirate")} required>
              <select className="ctl" value={emirate} onChange={(e) => setEmirate(e.target.value)}>
                <option value="" />
                {UAE_EMIRATES.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </Field>
            <Field label={t("f.taxTemplate")} required>
              <select className="ctl" value={taxTemplate} onChange={(e) => setTaxTemplate(e.target.value)}>
                <option value="" />
                {(templates.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
            <Field label={t("f.paymentTerms")}>
              <select className="ctl" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)}>
                <option value="" />
                {(terms.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
            <OrderDiscountFields
              percent={discountPct}
              basis={discountOn}
              onPercent={setDiscountPct}
              onBasis={setDiscountOn}
            />
            <Field label={t("txn.terms")}>
              <select className="ctl" value={tcName} onChange={(e) => setTcName(e.target.value)}>
                <option value="" />
                {(termDocs.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
          </div>
          <PaymentScheduleTable rows={schedule} />
          <PartyFields side="selling" partyName={customer} party={party} onChange={(patch) => setParty((p) => ({ ...p, ...patch }))} />
          <div className="grid3" style={{ marginBlockStart: 14 }}>
            <ExchangeRateField currency={party.currency || session.currency || undefined} companyCurrency={session.currency || undefined} value={conversionRate} onChange={setConversionRate} />
          </div>
        </Card>
        <Card num={2} title={t("inv.lines")} bodyClass={null as unknown as string}>
          {/* Item, Quantity and Amount on the face of a phone card; the rate
              sits behind "More", as on the sales invoice. */}
          <LineItems<TxnLine>
            rows={lines}
            showIndex
            onRemove={(i) => setLines((ls) => ls.filter((_, j) => j !== i))}
            addLabel={t("soc.addLine")}
            onAdd={() => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }])}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title", td: { minWidth: 200 },
                render: (l, i) => (
                  <>
                    <LinkField doctype={DT.item} value={l.item_code} onChange={(v) => void pickItem(i, v)} />
                    <LineTrack line={l} onChange={(patch) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, ...patch } : x))} />
                  </>
                ),
              },
              {
                key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 80 }} value={l.qty}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, qty: parseNum(e.target.value) } : x))} />
                ),
              },
              {
                key: "rate", label: t("sod.col.rate"), numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 104 }} value={l.rate}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? applyLineRate(x, parseNum(e.target.value)) : x))} />
                ),
              },
              {
                key: "discount", label: t("txn.lineDiscount"), numeric: true,
                render: (l, i) => (
                  <LineDiscountInput line={l} onChange={(next) => setLines((ls) => ls.map((x, j) => j === i ? next : x))} />
                ),
              },
              {
                key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                td: { fontWeight: 600 },
                render: (l) => money(l.qty * l.rate),
              },
            ] as LineField<TxnLine>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
