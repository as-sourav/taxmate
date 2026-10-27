/**
 * Purchase Invoice create/edit. Catalog txn helpers + get-items-from.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { applyLineRate, linePayload, mappedItem, orderDiscountFields, productDiscountTotal, readDiscountBasis, stampItemDetails, usePaymentSchedule, useTotalsPreview, useTransactionRpc, type DiscountBasis, type PartyDetails, type TxnLine } from "../../lib/txn";
import { LineDiscountInput, LineTrack, OrderDiscountFields, PartyFields, PaymentScheduleTable, TxnTotals } from "../../components/txnFields";
import { UAE_EMIRATES } from "../../types/uae";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";
import SourceDocPicker from "../../components/SourceDocPicker";

type InvoiceDoc = {
  name: string;
  supplier?: string;
  supplier_name?: string;
  posting_date?: string;
  due_date?: string;
  bill_no?: string;
  bill_date?: string;
  company?: string;
  vat_emirate?: string;
  taxes_and_charges?: string;
  tax_id?: string;
  payment_terms_template?: string;
  additional_discount_percentage?: number;
  apply_discount_on?: string;
  on_hold?: number;
  net_total?: number;
  total_taxes_and_charges?: number;
  grand_total?: number;
  currency?: string;
  conversion_rate?: number;
  update_stock?: number;
  set_warehouse?: string;
  docstatus?: 0 | 1 | 2;
  items?: TxnLine[];
};

export default function PurchaseInvoiceForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const location = useLocation();
  const existing = useDoc<InvoiceDoc>(DT.purchaseInvoice, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const defaults = useFrappePostCall<{ message: { company?: string; currency?: string; tax_id?: string } }>(METHOD.getDefaults);
  const submitCall = useFrappePostCall<{ message: InvoiceDoc }>(METHOD.submit);
  const create = useInsert();
  const update = useSave();
  const templates = useDocList<{ name: string }>(DT.purchaseTaxTemplate, { fields: ["name"], limit: 50 });
  const terms = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });

  const [supplier, setSupplier] = useState("");
  useEffect(() => {
    if (!isNew) return;
    const mapped = (location.state as { mapped?: { supplier?: string } } | null)?.mapped;
    if (mapped?.supplier) setSupplier(mapped.supplier);
  }, [isNew, location.state]);
  const [postingDate, setPostingDate] = useState(toIsoDate(new Date()));
  const [dueDate, setDueDate] = useState("");
  const [billNo, setBillNo] = useState("");
  const [billDate, setBillDate] = useState("");
  const [emirate, setEmirate] = useState("");
  const [taxTemplate, setTaxTemplate] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [discountPct, setDiscountPct] = useState(0);
  const [discountOn, setDiscountOn] = useState<DiscountBasis>("Net Total");
  const [onHold, setOnHold] = useState<0 | 1>(0);
  const [currency, setCurrency] = useState("");
  const [conversionRate, setConversionRate] = useState(1);
  const [updateStock, setUpdateStock] = useState(false);
  const [setWarehouse, setSetWarehouse] = useState("");
  const [party, setParty] = useState<PartyDetails>({});
  const [companyDefaults, setCompanyDefaults] = useState<{ company?: string; currency?: string; tax_id?: string }>({});
  const [lines, setLines] = useState<TxnLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [skipReprice, setSkipReprice] = useState(false);

  const company = companyDefaults.company || session.company;
  const companyCurrency = companyDefaults.currency || session.currency || "";
  const txn = useTransactionRpc({ doctype: DT.purchaseInvoice, side: "buying", company });

  useEffect(() => {
    defaults.call({}).then((r) => setCompanyDefaults(r?.message ?? {})).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    setSupplier(d.supplier || "");
    setPostingDate(d.posting_date || toIsoDate(new Date()));
    setDueDate(d.due_date || "");
    setBillNo(d.bill_no || "");
    setBillDate(d.bill_date || "");
    setEmirate(d.vat_emirate || "");
    setTaxTemplate(d.taxes_and_charges || "");
    setPaymentTerms(d.payment_terms_template || "");
    setDiscountPct(Number(d.additional_discount_percentage || 0));
    setDiscountOn(readDiscountBasis(d.apply_discount_on, Number(d.additional_discount_percentage) > 0));
    setOnHold(d.on_hold ? 1 : 0);
    setCurrency(d.currency || "");
    setConversionRate(Number(d.conversion_rate) || 1);
    setUpdateStock(!!d.update_stock);
    setSetWarehouse(d.set_warehouse || "");
    setLines((d.items ?? []).map((l) => mappedItem(l, d.set_warehouse || "")));
    setSkipReprice(true);
  }, [existing.data]);

  useEffect(() => {
    if (!supplier) return;
    void txn.fetchParty(supplier, postingDate).then(async (m) => {
      if (!m) return;
      if (skipReprice) { setSkipReprice(false); return; }
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
        setLines(await txn.repriceLines({ party: m, lines, transactionDate: postingDate, currency: cur, conversionRate: rate, supplier }));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplier]);


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
      item_code, supplier,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: conversionRate,
      buying_price_list: party.buying_price_list,
      warehouse: updateStock ? (setWarehouse || undefined) : undefined,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  function applyMapped(mapped: Record<string, unknown>) {
    setSkipReprice(true);
    if (mapped.supplier) setSupplier(String(mapped.supplier));
    if (mapped.posting_date) setPostingDate(String(mapped.posting_date));
    if (mapped.due_date) setDueDate(String(mapped.due_date));
    if (mapped.vat_emirate) setEmirate(String(mapped.vat_emirate));
    if (mapped.taxes_and_charges) setTaxTemplate(String(mapped.taxes_and_charges));
    if (mapped.bill_no) setBillNo(String(mapped.bill_no));
    if (mapped.bill_date) setBillDate(String(mapped.bill_date));
    if (mapped.update_stock != null) setUpdateStock(!!mapped.update_stock);
    if (mapped.set_warehouse) setSetWarehouse(String(mapped.set_warehouse));
    const items = (mapped.items as TxnLine[] | undefined) ?? [];
    setLines(items.map((l) => mappedItem(l, String(mapped.set_warehouse || ""))));
  }

  const buildPreviewDoc = useCallback(() => {
    if (!supplier || !lines.some((l) => l.item_code)) return null;
    return {
      supplier,
      posting_date: postingDate,
      due_date: dueDate || undefined,
      company,
      vat_emirate: emirate || undefined,
      taxes_and_charges: taxTemplate || undefined,
      payment_terms_template: paymentTerms || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      credit_to: party.credit_to,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: (!currency || currency === companyCurrency) ? 1 : conversionRate,
      ...orderDiscountFields(discountPct, discountOn),
      update_stock: updateStock ? 1 : 0,
      set_warehouse: updateStock ? (setWarehouse || undefined) : undefined,
      items: lines.filter((l) => l.item_code).map((l) => ({
        item_code: l.item_code, qty: l.qty, rate: l.rate, uom: l.uom,
        price_list_rate: l.price_list_rate, discount_percentage: l.discount_percentage, discount_amount: l.discount_amount,
        expense_account: l.expense_account, cost_center: l.cost_center,
        item_tax_template: l.item_tax_template,
        warehouse: l.warehouse || (updateStock ? setWarehouse || undefined : undefined),
      })),
    };
  }, [supplier, postingDate, dueDate, company, emirate, taxTemplate, paymentTerms, party, companyDefaults, session.currency, discountPct, discountOn, lines, currency, conversionRate, companyCurrency, updateStock, setWarehouse]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [supplier, postingDate, taxTemplate, emirate, discountPct, discountOn, lines, currency, conversionRate, updateStock, setWarehouse],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const scheduleGrand = preview?.grand_total ?? net;
  const schedule = usePaymentSchedule(paymentTerms || undefined, postingDate, scheduleGrand, scheduleGrand * (conversionRate || 1));
  const doc = existing.data;
  const canSubmit = canSubmitSales(session.roles);
  const ready = !!supplier && !!postingDate && !!emirate && !!taxTemplate && lines.length > 0 && lines.every((l) => l.item_code)
    && (!currency || currency === companyCurrency || conversionRate > 0);
  const displayCurrency = currency || doc?.currency || party.currency || companyDefaults.currency || session.currency || undefined;
  const showNet = preview?.net_total ?? doc?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? doc?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? doc?.grand_total ?? net;

  function payload() {
    return {
      supplier,
      posting_date: postingDate,
      due_date: dueDate || undefined,
      bill_no: billNo || undefined,
      bill_date: billDate || undefined,
      company,
      vat_emirate: emirate,
      taxes_and_charges: taxTemplate || undefined,
      payment_terms_template: paymentTerms || undefined,
      ...orderDiscountFields(discountPct, discountOn),
      on_hold: onHold,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      credit_to: party.credit_to,
      currency: currency || party.currency || companyDefaults.currency || session.currency,
      conversion_rate: (!currency || currency === companyCurrency) ? 1 : conversionRate,
      update_stock: updateStock ? 1 : 0,
      set_warehouse: updateStock ? (setWarehouse || undefined) : undefined,
      contact_person: party.contact_person,
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

  async function save() {
    setBusy(true); setSaveError(null);
    try {
      const docname = isNew
        ? (await create.createDoc(DT.purchaseInvoice, payload()) as { name: string }).name
        : (await update.updateDoc(DT.purchaseInvoice, name, payload()), name);
      nav(`/purchase-invoices/${encodeURIComponent(docname)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  async function submitDoc() {
    setBusy(true); setSaveError(null);
    try {
      let docname = name;
      if (isNew) {
        const created = await create.createDoc(DT.purchaseInvoice, payload());
        docname = (created as { name: string }).name;
      } else {
        await update.updateDoc(DT.purchaseInvoice, name, payload());
      }
      await submitCall.call({ doc: { doctype: DT.purchaseInvoice, name: docname } });
      nav(`/purchase-invoices/${encodeURIComponent(docname)}`);
    } catch (err) {
      setSaveError(err);
      if (!isNew) await existing.mutate();
    } finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data && existing.data.docstatus !== 0) {
    return <Navigate to={`/purchase-invoices/${encodeURIComponent(name)}`} replace />;
  }

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/purchase-invoices")}>{t("nav.purchaseInvoices")}</button>}
        title={isNew ? t("pi.new") : (doc?.supplier_name || supplier || name)}
        actions={
          <>
            <button type="button" className="btn ghost" onClick={() => nav("/purchase-invoices")}>{t("soc.discard")}</button>
            <button type="button" className="btn ghost" disabled={busy || !ready} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
            {canSubmit && (
              <button type="button" className="btn" disabled={busy || !ready} onClick={() => void submitDoc()}>
                {t("inv.submit")}
              </button>
            )}
          </>
        }
      />

      {(saveError || txn.pricingError || txn.partyCall.error || submitCall.error) && (
        <ErrorBox error={saveError || txn.pricingError || txn.partyCall.error || submitCall.error} />
      )}

      <FormLayout aside={
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
      }>
        {isNew && (
          <Card title={t("txn.getItemsFrom")}>
            <SourceDocPicker
              sources={[
                {
                  label: t("nav.purchaseOrders"), doctype: DT.purchaseOrder,
                  method: METHOD.makePurchaseInvoice, arg: "source_name",
                  filters: [["docstatus", "=", 1], ["status", "not in", ["Closed", "On Hold"]], ["per_billed", "<", 99.99]],
                },
                {
                  label: t("nav.purchaseReceipts"), doctype: DT.purchaseReceipt,
                  method: METHOD.makePrPurchaseInvoice, arg: "source_name",
                  filters: [["docstatus", "=", 1], ["is_return", "=", 0], ["status", "not in", ["Closed", "Completed", "Return Issued"]]],
                },
              ]}
              onMapped={applyMapped}
            />
          </Card>
        )}

        <Card num={1} title={t("pi.who")}>
          <div className="grid2">
            <Field label={t("nav.suppliers")} required>
              <LinkField doctype={DT.supplier} value={supplier} onChange={setSupplier} />
            </Field>
            <Field label={t("inv.date")} required>
              <input className="ctl" type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} />
            </Field>
            <Field label={t("inv.due")}>
              <input className="ctl" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </Field>
            <Field label={t("pi.billNo")} htmlFor="pi-bill-no">
              <input id="pi-bill-no" name="bill_no" className="ctl" value={billNo} onChange={(e) => setBillNo(e.target.value)} />
            </Field>
            <Field label={t("pi.billDate")} htmlFor="pi-bill-date">
              <input id="pi-bill-date" name="bill_date" className="ctl" type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} />
            </Field>
          </div>
          <PartyFields side="buying" partyName={supplier} party={party} onChange={(patch) => setParty((p) => ({ ...p, ...patch }))} />
          <div className="numblk">
            <span className="infochip"><span className="k2">T</span>{t("pi.supplierTrn")} <b>{party.tax_id || doc?.tax_id || "—"}</b></span>
            <span className="infochip"><span className="k2">C</span>{t("f.companyTrn")} <b>{companyDefaults.tax_id || "—"}</b></span>
            <span className="infochip"><span className="k2">$</span>{t("f.currency")} <b>{currency || companyCurrency || "—"}</b></span>
          </div>
        </Card>

        <Card num={2} title={t("soc.b2")}>
          <div className="grid2">
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
            <OrderDiscountFields
              percent={discountPct}
              basis={discountOn}
              onPercent={setDiscountPct}
              onBasis={setDiscountOn}
            />
            <CheckField label={t("supp.onHold")} checked={!!onHold} onChange={(on) => setOnHold(on ? 1 : 0)} />
            <Field label={t("f.paymentTerms")}>
              <select className="ctl" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)}>
                <option value="" />
                {(terms.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
            {currency && currency !== companyCurrency ? (
              <Field label={t("f.conversionRate")}>
                <input className="ctl" type="number" min={0} step={0.000001} value={conversionRate}
                  onChange={(e) => setConversionRate(parseNum(e.target.value) || 1)} />
              </Field>
            ) : null}
            <Field label={t("pi.updateStock")}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 36 }}>
                <input type="checkbox" checked={updateStock}
                  onChange={(e) => setUpdateStock(e.target.checked)} />
                <span>{t("pi.updateStock")}</span>
              </label>
            </Field>
            {updateStock ? (
              <Field label={t("dn.warehouse")}>
                <LinkField doctype={DT.warehouse} value={setWarehouse} onChange={setSetWarehouse}
                  filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
              </Field>
            ) : null}
          </div>
          <PaymentScheduleTable rows={schedule} />
        </Card>

        <Card num={3} title={t("inv.lines")} bodyClass={null}>
          {/* Item, Quantity and Amount on the face of a phone card; rate, the
              HS/SAC codes, the expense account and the cost centre behind
              "More" — they are set once and rarely changed per line. */}
          <LineItems<TxnLine>
            rows={lines}
            showIndex
            onRemove={(i) => setLines((ls) => ls.filter((_, j) => j !== i))}
            addLabel={t("soc.addLine")}
            onAdd={() => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }])}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title", td: { minWidth: 180 },
                render: (l, i) => (
                  <>
                    <LinkField doctype={DT.item} value={l.item_code} onChange={(v) => void pickItem(i, v)} />
                    <LineTrack line={l} onChange={(patch) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, ...patch } : x))} />
                  </>
                ),
              },
              {
                key: "hssac", label: t("pi.hsSac"),
                render: (l, i) => (
                  <>
                    {l.uae_item_type !== "Service" && (
                      <input className="ctl mini" style={{ width: 88 }}
                        aria-label={t("item.hs")} placeholder={t("item.hs")} value={l.hs_code || ""}
                        onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, hs_code: e.target.value } : x))} />
                    )}
                    {l.uae_item_type !== "Goods" && (
                      <input className="ctl mini" style={{ width: 88, marginTop: l.uae_item_type === "Both" || !l.uae_item_type ? 4 : 0 }}
                        aria-label={t("item.sac")} placeholder={t("item.sac")} value={l.sac_code || ""}
                        onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, sac_code: e.target.value } : x))} />
                    )}
                  </>
                ),
              },
              {
                key: "expense", label: t("f.expenseAccount"), td: { minWidth: 140 },
                render: (l, i) => (
                  <LinkField doctype={DT.account} value={l.expense_account || ""}
                    onChange={(v) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, expense_account: v } : x))}
                    filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
                ),
              },
              {
                key: "cc", label: t("f.costCenter"), td: { minWidth: 120 },
                render: (l, i) => (
                  <LinkField doctype={DT.costCenter} value={l.cost_center || ""}
                    onChange={(v) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, cost_center: v } : x))}
                    filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
                ),
              },
              {
                key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 72 }} value={l.qty}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, qty: parseNum(e.target.value) } : x))} />
                ),
              },
              {
                key: "rate", label: t("sod.col.rate"), numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 96 }} value={l.rate}
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
                render: (l) => <span>{money(l.qty * l.rate)}</span>,
              },
            ] as LineField<TxnLine>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
