/**
 * Shared Sales/Purchase transaction helpers.
 *
 * Callers: InvoiceForm, SalesOrderCreate, QuotationForm, DeliveryNoteForm,
 * PurchaseOrderForm, PurchaseInvoiceForm, PurchaseReceiptForm,
 * SupplierQuotationForm (and SourceDocPicker).
 *
 * All RPCs are catalogued taxmate.api.accounts.* methods — never raw erpnext.*.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useFrappePostCall } from "frappe-react-sdk";

import { METHOD } from "./frappe";
import { parseNum } from "./format";

/** Shape of taxmate.api.stock.item_qty message. */
export type ItemQtyMessage = {
  item_code: string;
  company?: string | null;
  total: number;
  warehouses: Array<{
    warehouse: string;
    actual_qty: number;
    reserved_qty?: number;
    ordered_qty?: number;
    projected_qty?: number;
  }>;
};

/** On-hand qty for a warehouse, or company total when warehouse is empty. */
export function availableQty(msg: ItemQtyMessage, warehouse?: string): number {
  if (warehouse) {
    const row = msg.warehouses.find((w) => w.warehouse === warehouse);
    return Number(row?.actual_qty ?? 0);
  }
  return Number(msg.total ?? 0);
}

/**
 * Advisory stock hints per line index (actual_qty < qty).
 * Non-blocking — call after item pick / warehouse / qty change.
 */
export function useItemQtyCheck(company?: string | null) {
  const call = useFrappePostCall<{ message: ItemQtyMessage }>(METHOD.itemQty);
  const [hints, setHints] = useState<Record<number, { avail: number; qty: number }>>({});

  const checkLine = useCallback(
    async (idx: number, item_code: string, qty: number, warehouse?: string) => {
      if (!item_code) {
        setHints((h) => {
          const next = { ...h };
          delete next[idx];
          return next;
        });
        return;
      }
      try {
        const r = await call.call({ item_code, company: company || undefined });
        const m = r?.message;
        if (!m) return;
        const avail = availableQty(m, warehouse || undefined);
        if (avail < qty) {
          setHints((h) => ({ ...h, [idx]: { avail, qty } }));
        } else {
          setHints((h) => {
            const next = { ...h };
            delete next[idx];
            return next;
          });
        }
      } catch {
        /* advisory only */
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [company],
  );

  return { checkLine, hints };
}

export type TxnLine = {
  item_code: string;
  item_name?: string;
  description?: string;
  qty: number;
  rate: number;
  uom?: string;
  stock_uom?: string;
  conversion_factor?: number;
  warehouse?: string;
  income_account?: string;
  expense_account?: string;
  cost_center?: string;
  item_tax_template?: string;
  batch_no?: string;
  serial_no?: string;
  uae_item_type?: string;
  hs_code?: string;
  sac_code?: string;
  price_list_rate?: number;
  discount_percentage?: number;
  discount_amount?: number;
  margin_type?: string;
  margin_rate_or_amount?: number;
  pricing_rules?: string;
  is_free_item?: 0 | 1;
  has_batch_no?: 0 | 1;
  has_serial_no?: 0 | 1;
  uae_is_margin_scheme?: 0 | 1;
  uae_purchase_price?: number;
  material_request?: string;
  material_request_item?: string;
  schedule_date?: string;
  /** Order and receipt links ERPNext reads when stock is posted. */
  sales_order?: string;
  so_detail?: string;
  against_sales_order?: string;
  delivery_note?: string;
  dn_detail?: string;
  purchase_order?: string;
  purchase_order_item?: string;
  po_detail?: string;
  purchase_receipt?: string;
  pr_detail?: string;
  serial_and_batch_bundle?: string;
  use_serial_batch_fields?: 0 | 1;
  rejected_qty?: number;
};

export type PartyDetails = {
  customer_address?: string;
  supplier_address?: string;
  shipping_address_name?: string;
  company_address?: string;
  contact_person?: string;
  taxes_and_charges?: string;
  vat_emirate?: string;
  selling_price_list?: string;
  buying_price_list?: string;
  payment_terms_template?: string;
  tax_id?: string;
  currency?: string;
  debit_to?: string;
  credit_to?: string;
  due_date?: string;
  tax_category?: string;
  price_list_currency?: string;
  customer_name?: string;
  supplier_name?: string;
  territory?: string;
  customer_group?: string;
  supplier_group?: string;
};

export type DiscountBasis = "Net Total" | "Grand Total";

export type TotalsPreview = {
  total?: number;
  net_total?: number;
  discount_amount?: number;
  additional_discount_percentage?: number;
  apply_discount_on?: DiscountBasis | string;
  total_taxes_and_charges?: number;
  grand_total?: number;
  rounded_total?: number;
  taxes?: Record<string, unknown>[];
  items?: { idx?: number; item_code?: string; qty?: number; rate?: number; amount?: number; net_amount?: number }[];
};

/** ERPNext's doctype default is Grand Total. A saved discount with a blank basis was calculated that way. */
export function readDiscountBasis(value: unknown, hasDiscount = false): DiscountBasis {
  if (value === "Grand Total" || value === "Net Total") return value;
  return hasDiscount ? "Grand Total" : "Net Total";
}

/** Header fields for the additional (order) discount. Zero clears a previously saved amount. */
export function orderDiscountFields(percent: number, basis: DiscountBasis): Record<string, unknown> {
  const pct = Number(percent) || 0;
  if (pct <= 0) {
    return {
      additional_discount_percentage: 0,
      apply_discount_on: basis,
      discount_amount: 0,
    };
  }
  return {
    additional_discount_percentage: pct,
    apply_discount_on: basis,
  };
}

/** Percent off the product's list rate. The line rate follows, so the amount column stays the source of the total. */
export function applyLineDiscountPct(line: TxnLine, percent: number): TxnLine {
  const pct = Math.min(100, Math.max(0, Number(percent) || 0));
  const list = Number(line.price_list_rate) || Number(line.rate) || 0;
  const discount = (list * pct) / 100;
  return {
    ...line,
    price_list_rate: Number(line.price_list_rate) || list || undefined,
    discount_percentage: pct,
    discount_amount: discount,
    rate: list - discount,
  };
}

/** Keep the product discount in step when the rate is typed by hand. */
export function applyLineRate(line: TxnLine, rate: number): TxnLine {
  const list = Number(line.price_list_rate) || 0;
  if (list > 0) {
    const cut = Math.max(list - rate, 0);
    return {
      ...line,
      rate,
      discount_amount: cut,
      discount_percentage: Math.round((cut / list) * 10000) / 100,
    };
  }
  return { ...line, rate };
}

type DiscountLine = {
  qty?: number;
  rate?: number;
  price_list_rate?: number;
  discount_percentage?: number;
  discount_amount?: number;
};

/** Sum of per-product discounts (list rate minus selling/buying rate), not the order-level discount. */
export function productDiscountTotal(lines: DiscountLine[]): number {
  return lines.reduce((sum, line) => {
    const qty = Number(line.qty) || 0;
    const list = Number(line.price_list_rate) || 0;
    const rate = Number(line.rate) || 0;
    if (list > rate) return sum + (list - rate) * qty;
    if (!(list > 0) && (Number(line.discount_amount) || 0) > 0) {
      return sum + (Number(line.discount_amount) || 0) * qty;
    }
    return sum;
  }, 0);
}

export function lineHasProductDiscount(line: DiscountLine): boolean {
  const list = Number(line.price_list_rate) || 0;
  const rate = Number(line.rate) || 0;
  if (list > rate) return true;
  if ((Number(line.discount_percentage) || 0) > 0) return true;
  if ((Number(line.discount_amount) || 0) > 0) return true;
  return false;
}

type ReturnQtyLine = {
  qty?: number;
  rate?: number;
  conversion_factor?: number;
  rejected_qty?: number;
  received_qty?: number;
  stock_qty?: number;
  received_stock_qty?: number;
  amount?: number;
};

/**
 * A return line stores a negative quantity. ERPNext requires
 * received_qty = qty + rejected_qty, and stock qty follows the conversion
 * factor. Editing only qty leaves the mapped received qty stale and the
 * return total wrong until the server happens to repair it.
 */
export function applyReturnQty<T extends ReturnQtyLine>(line: T, raw: string | number): T {
  const qty = -Math.abs(parseNum(raw));
  const conv = Number(line.conversion_factor) || 1;
  const rejected = Number(line.rejected_qty) || 0;
  const received = qty + rejected;
  return {
    ...line,
    qty,
    received_qty: received,
    stock_qty: qty * conv,
    received_stock_qty: received * conv,
    amount: qty * (Number(line.rate) || 0),
  };
}

export type TxnSide = "selling" | "buying";

export function taxMasterDoctype(side: TxnSide): string {
  return side === "buying"
    ? "Purchase Taxes and Charges Template"
    : "Sales Taxes and Charges Template";
}

export function priceListField(side: TxnSide): "selling_price_list" | "buying_price_list" {
  return side === "buying" ? "buying_price_list" : "selling_price_list";
}

export function partyTypeFor(side: TxnSide): "Customer" | "Supplier" {
  return side === "buying" ? "Supplier" : "Customer";
}

/** Merge get_item_details response into a line. */
export function stampItemDetails(line: TxnLine, m: Record<string, unknown>): TxnLine {
  return {
    ...line,
    item_name: String(m.item_name ?? line.item_name ?? ""),
    description: String(m.description ?? line.description ?? ""),
    uom: String(m.uom ?? line.uom ?? ""),
    stock_uom: m.stock_uom ? String(m.stock_uom) : line.stock_uom,
    conversion_factor: Number(m.conversion_factor ?? line.conversion_factor ?? 1) || 1,
    rate: Number(m.price_list_rate ?? m.rate ?? line.rate) || line.rate,
    price_list_rate: Number(m.price_list_rate ?? line.price_list_rate ?? 0) || undefined,
    // A new item does not inherit the previous line's product discount.
    discount_percentage: undefined,
    discount_amount: undefined,
    warehouse: m.warehouse ? String(m.warehouse) : line.warehouse,
    income_account: m.income_account ? String(m.income_account) : line.income_account,
    expense_account: m.expense_account ? String(m.expense_account) : line.expense_account,
    cost_center: m.cost_center ? String(m.cost_center) : line.cost_center,
    item_tax_template: m.item_tax_template ? String(m.item_tax_template) : line.item_tax_template,
    has_batch_no: m.has_batch_no ? 1 : line.has_batch_no,
    has_serial_no: m.has_serial_no ? 1 : line.has_serial_no,
    uae_is_margin_scheme: m.uae_is_margin_scheme ? 1 : line.uae_is_margin_scheme,
    uae_item_type: m.uae_item_type ? String(m.uae_item_type) : line.uae_item_type,
    hs_code: m.hs_code ? String(m.hs_code) : line.hs_code,
    sac_code: m.sac_code ? String(m.sac_code) : line.sac_code,
  };
}

type UseTxnArgs = {
  doctype: string;
  side: TxnSide;
  company?: string | null;
};

/**
 * Catalogued party / item / tax / totals helpers for txn forms.
 * Forms own their state; this hook owns the RPCs and side-effect helpers.
 */
function withMargin(price: number, marginType?: string, marginAmt?: number): number {
  const margin = Number(marginAmt) || 0;
  if (marginType === "Percentage") return price * (1 + margin / 100);
  if (marginType === "Amount") return price + margin;
  return price;
}

/** Stamp one ERPNext `apply_pricing_rule` row onto a line. Rate follows Desk: list ± margin − discount. */
export function applyPricingRule(line: TxnLine, rule: Record<string, unknown>): TxnLine {
  const next: TxnLine = { ...line };
  if (rule.price_list_rate != null && rule.price_list_rate !== "") {
    const list = Number(rule.price_list_rate);
    if (Number.isFinite(list)) next.price_list_rate = list;
  }
  if (rule.discount_percentage != null && rule.discount_percentage !== "") {
    next.discount_percentage = Number(rule.discount_percentage) || 0;
  }
  if (rule.discount_amount != null && rule.discount_amount !== "") {
    next.discount_amount = Number(rule.discount_amount) || 0;
  }
  if (rule.pricing_rules) next.pricing_rules = String(rule.pricing_rules);
  if (rule.margin_type) next.margin_type = String(rule.margin_type);
  if (rule.margin_rate_or_amount != null && rule.margin_rate_or_amount !== "") {
    next.margin_rate_or_amount = Number(rule.margin_rate_or_amount) || 0;
  }
  const list = next.price_list_rate ?? next.rate;
  const priced = withMargin(list, next.margin_type, next.margin_rate_or_amount);
  let discount = next.discount_amount || 0;
  if (!discount && next.discount_percentage) discount = (priced * next.discount_percentage) / 100;
  next.rate = priced - discount;
  return next;
}

function freeLinesFrom(rule: Record<string, unknown>): TxnLine[] {
  if (!Array.isArray(rule.free_item_data)) return [];
  return rule.free_item_data.flatMap((row) => {
    if (!row || typeof row !== "object") return [];
    const r = row as Record<string, unknown>;
    const item_code = String(r.item_code || "");
    if (!item_code) return [];
    return [{
      item_code,
      item_name: r.item_name ? String(r.item_name) : undefined,
      description: r.description ? String(r.description) : undefined,
      qty: Number(r.qty) || 1,
      rate: Number(r.rate) || 0,
      uom: r.uom ? String(r.uom) : undefined,
      price_list_rate: Number(r.price_list_rate) || 0,
      pricing_rules: r.pricing_rules ? String(r.pricing_rules) : undefined,
      is_free_item: 1 as const,
      conversion_factor: Number(r.conversion_factor) || 1,
    }];
  });
}

/** Fields the server expects on a sales or purchase item row. */
export function linePayload(l: TxnLine): Record<string, unknown> {
  return {
    item_code: l.item_code,
    item_name: l.item_name,
    qty: l.qty,
    rate: l.rate,
    uom: l.uom,
    description: l.description,
    stock_uom: l.stock_uom,
    conversion_factor: l.conversion_factor,
    warehouse: l.warehouse,
    income_account: l.income_account,
    expense_account: l.expense_account,
    cost_center: l.cost_center,
    item_tax_template: l.item_tax_template,
    price_list_rate: l.price_list_rate,
    discount_percentage: l.discount_percentage,
    discount_amount: l.discount_amount,
    margin_type: l.margin_type,
    margin_rate_or_amount: l.margin_rate_or_amount,
    pricing_rules: l.pricing_rules,
    is_free_item: l.is_free_item ? 1 : 0,
    batch_no: l.batch_no,
    serial_no: l.serial_no,
    material_request: l.material_request,
    material_request_item: l.material_request_item,
    schedule_date: l.schedule_date,
    uae_item_type: l.uae_item_type,
    hs_code: l.hs_code,
    sac_code: l.sac_code,
    uae_is_margin_scheme: l.uae_is_margin_scheme ? 1 : 0,
    uae_purchase_price: l.uae_is_margin_scheme ? l.uae_purchase_price : undefined,
    sales_order: l.sales_order,
    so_detail: l.so_detail,
    against_sales_order: l.against_sales_order,
    delivery_note: l.delivery_note,
    dn_detail: l.dn_detail,
    purchase_order: l.purchase_order,
    purchase_order_item: l.purchase_order_item,
    po_detail: l.po_detail,
    purchase_receipt: l.purchase_receipt,
    pr_detail: l.pr_detail,
    serial_and_batch_bundle: l.serial_and_batch_bundle,
    use_serial_batch_fields: l.use_serial_batch_fields,
    rejected_qty: l.rejected_qty,
  };
}

const _ROW_META = new Set([
  "name", "doctype", "parent", "parentfield", "parenttype", "idx",
  "owner", "creation", "modified", "modified_by", "docstatus",
]);

/** Copy a mapped or saved item, including the order and batch links stock depends on. */
export function mappedItem(row: object, warehouse?: string): TxnLine {
  const src = row as Record<string, unknown>;
  const line: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(src)) {
    if (_ROW_META.has(key) || value == null || value === "") continue;
    line[key] = value;
  }
  line.item_code = String(src.item_code || "");
  line.qty = Number(src.qty) || 1;
  line.rate = Number(src.rate) || 0;
  if (!line.warehouse && warehouse) line.warehouse = warehouse;
  if (src.use_serial_batch_fields != null) line.use_serial_batch_fields = src.use_serial_batch_fields ? 1 : 0;
  return line as TxnLine;
}

export function useTransactionRpc({ doctype, side, company }: UseTxnArgs) {
  const [pricingError, setPricingError] = useState<unknown>(null);
  const partyCall = useFrappePostCall<{ message: PartyDetails }>(METHOD.getPartyDetails);
  const itemCall = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.getItemDetails);
  const priceListCall = useFrappePostCall<{
    message: { parent?: Record<string, unknown>; children?: Record<string, unknown>[] };
  }>(METHOD.applyPriceList);
  const pricingRuleCall = useFrappePostCall<{ message: Record<string, unknown>[] }>(METHOD.applyPricingRule);
  const taxesCall = useFrappePostCall<{ message: Record<string, unknown>[] }>(METHOD.getTaxesAndCharges);
  const conversionCall = useFrappePostCall<{ message: { conversion_factor?: number } }>(METHOD.getConversionFactor);
  const exchangeCall = useFrappePostCall<{ message: number }>(METHOD.getExchangeRate);
  const previewCall = useFrappePostCall<{ message: TotalsPreview }>(METHOD.previewTaxesAndTotals);

  const fetchParty = useCallback(
    async (party: string, postingDate?: string) => {
      if (!party) return null;
      const r = await partyCall.call({
        party,
        party_type: partyTypeFor(side),
        doctype,
        company: company || undefined,
        posting_date: postingDate,
      });
      return r?.message ?? null;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doctype, side, company],
  );

  const fetchItem = useCallback(
    async (ctx: Record<string, unknown>) => {
      const r = await itemCall.call({
        ctx: {
          doctype,
          company: company || undefined,
          conversion_rate: 1,
          qty: 1,
          ...ctx,
        },
      });
      return (r?.message ?? null) as Record<string, unknown> | null;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doctype, company],
  );

  const repriceLines = useCallback(
    async (args: {
      party?: PartyDetails | null;
      lines: TxnLine[];
      transactionDate?: string;
      currency?: string;
      conversionRate?: number;
      customer?: string;
      supplier?: string;
    }) => {
      const coded = args.lines.filter((l) => l.item_code);
      if (!coded.length) return args.lines;
      const plField = priceListField(side);
      const priceList = args.party?.[plField];
      const conversion_rate = args.conversionRate ?? 1;
      try {
        const r = await priceListCall.call({
          ctx: {
            doctype,
            company: company || undefined,
            currency: args.currency || args.party?.currency,
            conversion_rate,
            [plField]: priceList,
            price_list_currency: args.party?.price_list_currency || args.currency,
            plc_conversion_rate: conversion_rate,
            transaction_date: args.transactionDate,
            customer: args.customer,
            supplier: args.supplier,
            items: coded.map((l) => ({
              item_code: l.item_code,
              qty: l.qty,
              uom: l.uom,
            })),
          },
        });
        const children = r?.message?.children ?? [];
        let ci = 0;
        let next = args.lines.map((l) => {
          if (!l.item_code) return l;
          const child = children[ci++];
          if (!child) return l;
          const rate = Number(child.price_list_rate ?? child.rate ?? l.rate);
          return { ...l, rate: Number.isFinite(rate) ? rate : l.rate, price_list_rate: rate };
        });

        try {
          const pr = await pricingRuleCall.call({
            args: {
              doctype,
              company: company || undefined,
              currency: args.currency || args.party?.currency,
              conversion_rate,
              price_list: priceList,
              transaction_date: args.transactionDate,
              customer: args.customer,
              supplier: args.supplier,
              items: next
                .filter((l) => l.item_code && !l.is_free_item)
                .map((l, i) => ({
                  doctype: `${doctype} Item`,
                  name: `row-${i}`,
                  item_code: l.item_code,
                  qty: l.qty,
                  uom: l.uom,
                  price_list_rate: l.rate,
                })),
            },
          });
          const rules = pr?.message ?? [];
          const paid = next.filter((l) => l.item_code && !l.is_free_item);
          const blanks = next.filter((l) => !l.item_code);
          let ri = 0;
          const priced = paid.map((l) => {
            const rule = rules[ri++];
            return rule ? applyPricingRule(l, rule) : l;
          });
          const free = rules.flatMap((rule) => (rule ? freeLinesFrom(rule) : []));
          const seen = new Set<string>();
          const freeOnce = free.filter((l) => {
            const key = `${l.item_code}:${l.pricing_rules ?? ""}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          next = [...priced, ...freeOnce, ...blanks];
          setPricingError(null);
        } catch (err) {
          setPricingError(err);
        }
        return next;
      } catch (err) {
        setPricingError(err);
        return args.lines;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doctype, side, company],
  );

  const loadTaxRows = useCallback(
    async (template: string) => {
      if (!template) return [];
      const r = await taxesCall.call({
        master_doctype: taxMasterDoctype(side),
        master_name: template,
      });
      return r?.message ?? [];
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [side],
  );

  const fetchExchangeRate = useCallback(
    async (fromCurrency: string, toCurrency: string, transactionDate?: string) => {
      if (!fromCurrency || !toCurrency || fromCurrency === toCurrency) return 1;
      const r = await exchangeCall.call({
        from_currency: fromCurrency,
        to_currency: toCurrency,
        transaction_date: transactionDate,
        args: side === "buying" ? "for_buying" : "for_selling",
      });
      const rate = Number(r?.message);
      return Number.isFinite(rate) ? rate : 0;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [side],
  );

  const convertUom = useCallback(async (item_code: string, uom: string) => {
    const r = await conversionCall.call({ item_code, uom });
    return Number(r?.message?.conversion_factor ?? 1) || 1;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const previewTotals = useCallback(
    async (doc: Record<string, unknown>) => {
      const r = await previewCall.call({ doc: { doctype, company: company || undefined, ...doc } });
      return r?.message ?? null;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [doctype, company],
  );

  return {
    fetchParty,
    fetchItem,
    repriceLines,
    loadTaxRows,
    convertUom,
    fetchExchangeRate,
    previewTotals,
    partyCall,
    itemCall,
    previewCall,
    pricingError,
  };
}

/** Debounced tax/totals preview when doc shape changes. */
export function useTotalsPreview(
  buildDoc: () => Record<string, unknown> | null,
  deps: unknown[],
  previewTotals: (doc: Record<string, unknown>) => Promise<TotalsPreview | null>,
  delayMs = 400,
) {
  const [preview, setPreview] = useState<TotalsPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const doc = buildDoc();
      if (!doc) {
        setPreview(null);
        return;
      }
      setPreviewing(true);
      previewTotals(doc)
        .then((p) => setPreview(p))
        .catch(() => setPreview(null))
        .finally(() => setPreviewing(false));
    }, delayMs);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { preview, previewing };
}

export type PaymentScheduleRow = {
  payment_term?: string;
  description?: string;
  due_date?: string;
  invoice_portion?: number;
  payment_amount?: number;
  mode_of_payment?: string;
};

export type CreditBalance = {
  credit_limit: number;
  outstanding: number;
  extra_amount: number;
  projected: number;
  remaining: number | null;
  crossed: boolean;
};

/** Rebuild payment schedule when the template or totals change. */
export function usePaymentSchedule(
  termsTemplate: string | undefined,
  postingDate: string | undefined,
  grandTotal: number | undefined,
  baseGrandTotal?: number,
) {
  const call = useFrappePostCall<{ message: PaymentScheduleRow[] }>(METHOD.getPaymentTerms);
  const [rows, setRows] = useState<PaymentScheduleRow[]>([]);

  useEffect(() => {
    if (!termsTemplate || !postingDate) {
      setRows([]);
      return;
    }
    const total = Number(grandTotal) || 0;
    const base = Number(baseGrandTotal ?? grandTotal) || 0;
    let cancelled = false;
    void call
      .call({
        terms_template: termsTemplate,
        posting_date: postingDate,
        grand_total: total,
        base_grand_total: base,
      })
      .then((r) => {
        if (!cancelled) setRows(r?.message ?? []);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [termsTemplate, postingDate, grandTotal, baseGrandTotal]);

  return rows;
}

/** Advisory credit check for sales documents. Server still enforces on submit. */
export function useCreditBalance(
  customer: string | undefined,
  company: string | null | undefined,
  extraAmount: number,
) {
  const call = useFrappePostCall<{ message: CreditBalance }>(METHOD.getCreditBalance);
  const [balance, setBalance] = useState<CreditBalance | null>(null);

  useEffect(() => {
    if (!customer || !company) {
      setBalance(null);
      return;
    }
    let cancelled = false;
    const handle = window.setTimeout(() => {
      void call
        .call({ customer, company, extra_amount: extraAmount || 0 })
        .then((r) => {
          if (!cancelled) setBalance(r?.message ?? null);
        })
        .catch(() => {
          if (!cancelled) setBalance(null);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer, company, extraAmount]);

  return balance;
}
