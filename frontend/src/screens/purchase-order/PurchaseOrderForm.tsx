/**
 * Purchase Order create/edit. Catalog txn helpers + get-items-from.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { applyLineRate, linePayload, orderDiscountFields, productDiscountTotal, readDiscountBasis, stampItemDetails, usePaymentSchedule, useTotalsPreview, useTransactionRpc, type DiscountBasis, type PartyDetails, type TxnLine } from "../../lib/txn";
import { ExchangeRateField, LineDiscountInput, LineTrack, OrderDiscountFields, PartyFields, PaymentScheduleTable, TxnTotals } from "../../components/txnFields";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, PageHead } from "../../components/ui";
import { FormActions, FormLayout, ReadinessCard } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";
import SourceDocPicker from "../../components/SourceDocPicker";

const today = toIsoDate(new Date());
const plus = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
};

export default function PurchaseOrderForm() {
  const nav = useNavigate();
  const location = useLocation();
  const session = useSession();
  const canSubmit = canSubmitSales(session.roles);
  const { name: editName } = useParams<{ name?: string }>();
  const isEdit = !!editName;
  const company = session.company;

  const [supplier, setSupplier] = useState("");
  const [orderDate, setOrderDate] = useState(today);
  const [requiredBy, setRequiredBy] = useState(plus(14));
  const [taxTemplate, setTaxTemplate] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [discountPct, setDiscountPct] = useState(0);
  const [discountOn, setDiscountOn] = useState<DiscountBasis>("Net Total");
  const [warehouse, setWarehouse] = useState("");
  const [party, setParty] = useState<PartyDetails>({});
  const [conversionRate, setConversionRate] = useState(1);
  const [lines, setLines] = useState<TxnLine[]>([]);
  const [skipReprice, setSkipReprice] = useState(false);

  type PoDoc = {
    name: string; supplier?: string; transaction_date?: string; schedule_date?: string;
    taxes_and_charges?: string; payment_terms_template?: string; additional_discount_percentage?: number; apply_discount_on?: string; set_warehouse?: string; docstatus?: number; items?: TxnLine[];
  };
  const existing = useDoc<PoDoc>(DT.purchaseOrder, isEdit ? editName : undefined, isEdit ? editName : null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (isEdit && existing.data && !loaded) {
      const d = existing.data;
      if (d.docstatus !== 0) { nav(`/purchase-orders/${encodeURIComponent(editName!)}`, { replace: true }); return; }
      setSupplier(d.supplier ?? "");
      setOrderDate(d.transaction_date ?? today);
      setRequiredBy(d.schedule_date ?? plus(14));
      setTaxTemplate(d.taxes_and_charges ?? "");
      setPaymentTerms(d.payment_terms_template ?? "");
      setDiscountPct(Number(d.additional_discount_percentage || 0));
      setDiscountOn(readDiscountBasis(d.apply_discount_on, Number(d.additional_discount_percentage) > 0));
      setWarehouse(d.set_warehouse ?? "");
      setLines((d.items ?? []).map((l) => ({
        item_code: l.item_code ?? "", item_name: l.item_name, uom: l.uom,
        qty: l.qty ?? 1, rate: l.rate ?? 0,
        price_list_rate: l.price_list_rate, discount_percentage: l.discount_percentage,
        discount_amount: l.discount_amount,
      })));
      setSkipReprice(true);
      setLoaded(true);
    }
  }, [isEdit, existing.data, loaded, nav, editName]);

  const templates = useDocList<{ name: string }>(DT.purchaseTaxTemplate, { fields: ["name"], limit: 50 });
  const termsList = useDocList<{ name: string }>(DT.paymentTerms, { fields: ["name"], limit: 50 });
  const txn = useTransactionRpc({ doctype: DT.purchaseOrder, side: "buying", company });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall<{ message: { name: string } }>(METHOD.submit);
  const busy = create.loading || update.loading || submitCall.loading;

  useEffect(() => {
    if (!supplier) return;
    void txn.fetchParty(supplier, orderDate).then(async (m) => {
      if (!m) return;
      if (skipReprice && isEdit) { setSkipReprice(false); return; }
      if (skipReprice) setSkipReprice(false);
      setParty(m);
      if (m.taxes_and_charges) setTaxTemplate(m.taxes_and_charges);
      if (m.payment_terms_template) setPaymentTerms(m.payment_terms_template);
      const cur = m.currency || session.currency || "";
      const rate = await txn.fetchExchangeRate(cur, session.currency || cur, orderDate);
      setConversionRate(rate);
      if (lines.some((l) => l.item_code)) {
        setLines(await txn.repriceLines({ party: m, lines, transactionDate: orderDate, currency: m.currency, conversionRate: rate, supplier }));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplier]);

  async function pickItem(idx: number, item_code: string) {
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, item_code } : l)));
    const m = await txn.fetchItem({
      item_code, supplier,
      buying_price_list: party.buying_price_list,
      currency: party.currency,
      transaction_date: orderDate,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  function applyMapped(mapped: Record<string, unknown>) {
    setSkipReprice(true);
    if (mapped.supplier) setSupplier(String(mapped.supplier));
    if (mapped.transaction_date) setOrderDate(String(mapped.transaction_date));
    const items = (mapped.items as Record<string, unknown>[] | undefined) ?? [];
    const lineDate = items.find((l) => l.schedule_date)?.schedule_date;
    if (mapped.schedule_date) setRequiredBy(String(mapped.schedule_date).slice(0, 10));
    else if (lineDate) setRequiredBy(String(lineDate).slice(0, 10));
    if (mapped.taxes_and_charges) setTaxTemplate(String(mapped.taxes_and_charges));
    if (mapped.set_warehouse) setWarehouse(String(mapped.set_warehouse));
    setLines(items.map((l) => ({
      item_code: String(l.item_code || ""),
      item_name: l.item_name ? String(l.item_name) : undefined,
      description: l.description ? String(l.description) : undefined,
      qty: Number(l.qty) || 1,
      rate: Number(l.rate) || 0,
      price_list_rate: Number(l.price_list_rate) || undefined,
      discount_percentage: Number(l.discount_percentage) || undefined,
      discount_amount: Number(l.discount_amount) || undefined,
      uom: l.uom ? String(l.uom) : undefined,
      warehouse: l.warehouse ? String(l.warehouse) : undefined,
      expense_account: l.expense_account ? String(l.expense_account) : undefined,
      cost_center: l.cost_center ? String(l.cost_center) : undefined,
      material_request: l.material_request ? String(l.material_request) : undefined,
      material_request_item: l.material_request_item ? String(l.material_request_item) : undefined,
      schedule_date: l.schedule_date ? String(l.schedule_date).slice(0, 10) : undefined,
    })));
  }

  const mappedOnce = useRef(false);
  useEffect(() => {
    if (isEdit || mappedOnce.current) return;
    const mapped = (location.state as { mapped?: Record<string, unknown> } | null)?.mapped;
    if (!mapped) return;
    mappedOnce.current = true;
    applyMapped(mapped);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, location.state]);

  const buildPreviewDoc = useCallback(() => {
    if (!lines.some((l) => l.item_code)) return null;
    if (!supplier && !taxTemplate) return null;
    return {
      supplier,
      transaction_date: orderDate,
      schedule_date: requiredBy,
      company,
      taxes_and_charges: taxTemplate || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      currency: party.currency || session.currency,
      conversion_rate: conversionRate,
      ...orderDiscountFields(discountPct, discountOn),
      items: lines.filter((l) => l.item_code).map((l) => ({
        ...linePayload(l),
        schedule_date: l.schedule_date || requiredBy,
      })),
    };
  }, [supplier, orderDate, requiredBy, company, taxTemplate, party, session.currency, conversionRate, discountPct, discountOn, lines]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [supplier, orderDate, taxTemplate, discountPct, discountOn, lines],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const showNet = preview?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? net;
  const schedule = usePaymentSchedule(
    paymentTerms || undefined,
    orderDate,
    showGrand,
    showGrand * (conversionRate || 1),
  );

  const checks = [
    [t("nav.suppliers"), !!supplier],
    [t("so.col.orderDate"), !!orderDate],
    [t("po.required"), !!requiredBy],
    [t("inv.lines"), lines.length > 0 && lines.every((l) => l.item_code)],
  ] as const;
  const ready = checks.every(([, ok]) => ok);

  async function save(shouldSubmit: boolean) {
    const doc = {
      supplier,
      transaction_date: orderDate,
      schedule_date: requiredBy,
      company,
      taxes_and_charges: taxTemplate || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      payment_terms_template: paymentTerms || undefined,
      ...orderDiscountFields(discountPct, discountOn),
      set_warehouse: warehouse || undefined,
      currency: party.currency || session.currency,
      conversion_rate: conversionRate,
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
      items: lines.map((l) => ({ ...linePayload(l), schedule_date: l.schedule_date || requiredBy })),
    };
    let finalName: string;
    if (isEdit && editName) {
      await update.updateDoc(DT.purchaseOrder, editName, doc);
      finalName = editName;
    } else {
      const created = await create.createDoc(DT.purchaseOrder, doc) as { name: string };
      finalName = created.name;
    }
    if (shouldSubmit) {
      await submitCall.call({ doc: { doctype: DT.purchaseOrder, name: finalName } });
    }
    nav(`/purchase-orders/${encodeURIComponent(finalName)}`);
  }

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/purchase-orders")}>{t("nav.purchaseOrders")}</button>}
        title={t("po.new")}
        actions={
          <FormActions
            onDiscard={() => nav("/purchase-orders")}
            onSave={() => void save(false)}
            onSubmit={canSubmit ? () => void save(true) : undefined}
            busy={busy} ready={ready} submitLabel={t("soc.submit")}
          />
        }
      />
      {(txn.pricingError || create.error || submitCall.error || txn.partyCall.error) && (
        <ErrorBox error={txn.pricingError || create.error || submitCall.error || txn.partyCall.error} />
      )}
      <FormLayout
        aside={
          <>
            <Card bodyClass="cbody">
              <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>
                {t("soc.summary")}{previewing ? "…" : ""}
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
            <ReadinessCard
              checks={checks.map(([label, ok]) => ({ label, ok }))}
              title={t("soc.ready")} caption={t("soc.readyCap")}
            />
          </>
        }
      >
        {!isEdit && (
          <Card title={t("txn.getItemsFrom")}>
            <SourceDocPicker
              sources={[
                { label: t("nav.supplierQuotations"), doctype: DT.supplierQuotation, method: METHOD.makeSupplierQuotationPO, arg: "source_name" },
                { label: t("nav.materialRequests"), doctype: DT.materialRequest, method: METHOD.makeMrPO, arg: "source_name" },
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
            <Field label={t("pi.supplierTrn")}>
              <input className="ctl readonly" readOnly value={party.tax_id || ""} />
            </Field>
            <Field label={t("so.col.orderDate")} required htmlFor="po-order-date">
              <input id="po-order-date" name="transaction_date" className="ctl" type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} />
            </Field>
            <Field label={t("po.required")} required htmlFor="po-required-by">
              <input id="po-required-by" name="schedule_date" className="ctl" type="date" value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)} />
            </Field>
            <Field label={t("f.taxTemplate")} htmlFor="po-tax-template">
              <select id="po-tax-template" name="taxes_and_charges" className="ctl" value={taxTemplate} onChange={(e) => setTaxTemplate(e.target.value)} aria-label={t("f.taxTemplate")}>
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
            <Field label={t("dn.warehouse")}>
              <LinkField doctype={DT.warehouse} value={warehouse} onChange={setWarehouse}
                filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
            </Field>
            <Field label={t("f.paymentTerms")}>
              <select className="ctl" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)}>
                <option value="" />
                {(termsList.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
          </div>
          <PartyFields side="buying" partyName={supplier} party={party} onChange={(patch) => setParty((p) => ({ ...p, ...patch }))} />
          <div className="grid3" style={{ marginBlockStart: 14 }}>
            <ExchangeRateField currency={party.currency || session.currency || undefined} companyCurrency={session.currency || undefined} value={conversionRate} onChange={setConversionRate} />
          </div>
          <PaymentScheduleTable rows={schedule} />
        </Card>
        <Card num={2} title={t("inv.lines")} bodyClass={null as unknown as string}>
          {/* Item, Quantity and Amount on the face of a phone card; the rate
              sits behind "More" — it arrives priced from the price list. */}
          <LineItems<TxnLine>
            rows={lines}
            showIndex
            onRemove={(i) => setLines((ls) => ls.filter((_, j) => j !== i))}
            addLabel={t("soc.addLine")}
            onAdd={() => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }])}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title", td: { minWidth: 220 },
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
                  <LineDiscountInput
                    line={l}
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
