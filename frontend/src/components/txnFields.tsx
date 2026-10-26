import { useId, type ReactNode } from "react";

import LinkField from "./LinkField";
import { Field, SumRow } from "./ui";
import { DT } from "../lib/frappe";
import { money, parseNum } from "../lib/format";
import { t } from "../i18n/strings";
import {
  applyLineDiscountPct,
  type DiscountBasis,
  type PartyDetails,
  type TxnLine,
  type TxnSide,
} from "../lib/txn";

function partyFilters(side: TxnSide, partyName: string) {
  const linkDoctype = side === "buying" ? "Supplier" : "Customer";
  if (!partyName) return undefined;
  return [
    ["Dynamic Link", "link_doctype", "=", linkDoctype],
    ["Dynamic Link", "link_name", "=", partyName],
  ];
}

/** Billing, shipping, and contact. Filled by get_party_details; the user can change them. */
export function PartyFields({
  side,
  partyName,
  party,
  onChange,
  disabled,
}: {
  side: TxnSide;
  partyName: string;
  party: PartyDetails;
  onChange: (patch: Partial<PartyDetails>) => void;
  disabled?: boolean;
}) {
  const filters = partyFilters(side, partyName);
  const billing = side === "buying" ? party.supplier_address : party.customer_address;
  const billingKey = side === "buying" ? "supplier_address" : "customer_address";
  return (
    <div className="grid3" style={{ marginBlockStart: 14 }}>
      <Field label={t("f.address")}>
        <LinkField
          doctype={DT.address}
          value={billing ?? ""}
          disabled={disabled || !partyName}
          filters={filters}
          onChange={(v) => onChange({ [billingKey]: v })}
        />
      </Field>
      {side === "selling" && (
        <Field label={t("f.shipping")}>
          <LinkField
            doctype={DT.address}
            value={party.shipping_address_name ?? ""}
            disabled={disabled || !partyName}
            filters={filters}
            onChange={(v) => onChange({ shipping_address_name: v })}
          />
        </Field>
      )}
      <Field label={t("f.contact")}>
        <LinkField
          doctype={DT.contact}
          value={party.contact_person ?? ""}
          disabled={disabled || !partyName}
          filters={filters}
          onChange={(v) => onChange({ contact_person: v })}
        />
      </Field>
    </div>
  );
}

/** Shown only when the document currency is not the company currency. */
export function ExchangeRateField({
  currency,
  companyCurrency,
  value,
  onChange,
  disabled,
}: {
  currency?: string;
  companyCurrency?: string;
  value: number;
  onChange: (rate: number) => void;
  disabled?: boolean;
}) {
  if (!currency || !companyCurrency || currency === companyCurrency) return null;
  return (
    <Field label={t("f.conversionRate")}>
      <input
        className="ctl"
        type="number"
        min={0}
        step={0.000001}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseNum(e.target.value) || 0)}
      />
    </Field>
  );
}

/** Batch, serial, and margin-scheme price. Rendered only when the item needs them. */
export function LineTrack({
  line,
  onChange,
  disabled,
}: {
  line: TxnLine;
  onChange: (patch: Partial<TxnLine>) => void;
  disabled?: boolean;
}) {
  const batch = !!line.has_batch_no;
  const serial = !!line.has_serial_no;
  const margin = !!line.uae_is_margin_scheme;
  if (!batch && !serial && !margin && !line.is_free_item) return null;
  return (
    <div className="grid3" style={{ marginTop: 6 }}>
      {!!line.is_free_item && <span className="infochip">{t("txn.freeItem")}</span>}
      {batch && (
        <Field label={t("dn.batchNo")}>
          <LinkField
            doctype={DT.batch}
            value={line.batch_no ?? ""}
            disabled={disabled}
            filters={line.item_code ? { item: line.item_code } : undefined}
            onChange={(v) => onChange({ batch_no: v })}
          />
        </Field>
      )}
      {serial && (
        <Field label={t("dn.serialNo")}>
          <input
            className="ctl"
            value={line.serial_no ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ serial_no: e.target.value })}
          />
        </Field>
      )}
      {margin && (
        <Field label={t("txn.marginPrice")}>
          <input
            className="ctl"
            type="number"
            min={0}
            step="0.01"
            value={line.uae_purchase_price ?? ""}
            disabled={disabled}
            onChange={(e) => onChange({ uae_purchase_price: parseNum(e.target.value) })}
          />
        </Field>
      )}
    </div>
  );
}

export type ScheduleRow = {
  payment_term?: string;
  description?: string;
  due_date?: string;
  invoice_portion?: number;
  payment_amount?: number;
};

/** Compact payment schedule from the selected terms template. */
export function PaymentScheduleTable({ rows }: { rows: ScheduleRow[] }) {
  if (!rows.length) return null;
  return (
    <div className="twrap" style={{ marginBlockStart: 14 }}>
      <table>
        <thead>
          <tr>
            <th>{t("txn.dueDate")}</th>
            <th>{t("f.paymentTerms")}</th>
            <th className="n">{t("txn.portion")}</th>
            <th className="n">{t("sod.col.amount")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.due_date ?? ""}-${i}`}>
              <td>{r.due_date || "—"}</td>
              <td>{r.payment_term || r.description || "—"}</td>
              <td className="n">{r.invoice_portion != null ? `${r.invoice_portion}%` : "—"}</td>
              <td className="n">{money(Number(r.payment_amount) || 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The row is the order discount, not a product discount. "Before VAT" is
 * Desk's Net Total; "after VAT" is Grand Total. The form's select uses the
 * Desk names Net total and Grand total. This label does not, because those
 * words are already the net and grand rows underneath.
 * Callers: TxnTotals below. Purchase, sales, and receipt screens pass the basis.
 */
export function orderDiscountLabel(percent?: number, basis?: string): string {
  const where = basis === "Grand Total" ? t("txn.afterVat") : t("txn.beforeVat");
  const pct = Number(percent) || 0;
  const pctBit = pct > 0 ? `, ${pct}%` : "";
  return `${t("txn.orderDiscount")}${pctBit} · ${where}`;
}

export function formatLineDiscount(line: { discount_percentage?: number; discount_amount?: number }): string {
  const pct = Number(line.discount_percentage) || 0;
  if (pct > 0) {
    const shown = Number.isInteger(pct) ? String(pct) : String(Math.round(pct * 100) / 100);
    return `${shown}%`;
  }
  const amt = Number(line.discount_amount) || 0;
  if (amt > 0) return money(amt);
  return "—";
}

/**
 * Order-level discount. The percent is separate from a line discount, and the
 * select says whether VAT is calculated before or after it.
 */
export function OrderDiscountFields({
  percent,
  basis,
  onPercent,
  onBasis,
  disabled,
}: {
  percent: number;
  basis: DiscountBasis;
  onPercent: (n: number) => void;
  onBasis: (basis: DiscountBasis) => void;
  disabled?: boolean;
}) {
  const pctId = useId();
  const basisId = useId();
  return (
    <>
      <Field label={t("txn.orderDiscount")} hint={t("txn.discountHint")} htmlFor={pctId}>
        <input
          id={pctId}
          className="ctl"
          type="number"
          min={0}
          max={100}
          step={0.01}
          inputMode="decimal"
          value={percent}
          disabled={disabled}
          onChange={(e) => onPercent(Math.min(100, Math.max(0, parseNum(e.target.value))))}
        />
      </Field>
      <Field label={t("txn.discountBasis")} htmlFor={basisId}>
        <select
          id={basisId}
          className="ctl"
          value={basis}
          disabled={disabled}
          onChange={(e) => onBasis(e.target.value === "Grand Total" ? "Grand Total" : "Net Total")}
        >
          <option value="Net Total">{t("sod.net")}</option>
          <option value="Grand Total">{t("sod.grand")}</option>
        </select>
      </Field>
    </>
  );
}

/** Percent off this product's list rate. */
export function LineDiscountInput({
  line,
  onChange,
  disabled,
}: {
  line: TxnLine;
  onChange: (next: TxnLine) => void;
  disabled?: boolean;
}) {
  return (
    <input
      className="ctl mini nn"
      style={{ width: 72 }}
      type="number"
      min={0}
      max={100}
      step={0.01}
      inputMode="decimal"
      aria-label={t("txn.lineDiscount")}
      value={line.discount_percentage ?? 0}
      disabled={disabled}
      onChange={(e) => onChange(applyLineDiscountPct(line, parseNum(e.target.value)))}
    />
  );
}

/**
 * Net, VAT, and grand total, with product and order discounts named when they exist.
 * Rows stay in the order the figures add up: list, product discount, items, order discount, net, VAT, grand.
 */
export function TxnTotals({
  currency,
  itemsTotal,
  productDiscount,
  orderDiscount,
  orderDiscountPercent,
  discountOn,
  net,
  vat,
  grand,
  netLabel,
  vatLabel,
  grandLabel,
  children,
}: {
  currency?: string;
  itemsTotal?: number;
  productDiscount?: number;
  orderDiscount?: number;
  orderDiscountPercent?: number;
  discountOn?: string;
  net?: number;
  vat?: number;
  grand?: number;
  netLabel: string;
  vatLabel: string;
  grandLabel: string;
  children?: ReactNode;
}) {
  const product = Number(productDiscount) || 0;
  const order = Math.abs(Number(orderDiscount) || 0);
  const showProduct = product > 0.004;
  const showOrder = order > 0.004;
  const items = Number(itemsTotal ?? net) || 0;
  const netAmount = Number(net) || 0;
  // A Grand Total percent is taken off the bill after VAT. ERPNext then
  // lowers the item net by only the pre-VAT share and recomputes VAT, so
  // discount_amount is larger than items − net. The row uses the share that
  // sits between items and net; the note keeps the full bill reduction.
  // Only the stored discount_amount opens this row. A gap between total and
  // net is also how included tax shows up, so it is not treated as a discount.
  const itemShare = itemsTotal == null ? order : items - netAmount;
  const onGrand = discountOn === "Grand Total";
  const splitGrand =
    onGrand && itemsTotal != null && Math.abs(itemShare) > 0.004 && Math.abs(itemShare - order) > 0.004;
  const rowAmount = splitGrand ? Math.abs(itemShare) : Math.abs(order);
  const billSaving = splitGrand ? Math.abs(order) : 0;
  return (
    <>
      {showProduct && (
        <>
          <SumRow k={t("txn.listTotal")} v={money(items + product)} currency={currency} />
          <SumRow k={t("txn.productDiscounts")} v={`−${money(product)}`} currency={currency} cls="discount" />
        </>
      )}
      {showOrder && (
        <>
          <SumRow k={t("txn.itemsTotal")} v={money(items)} currency={currency} />
          <SumRow
            k={orderDiscountLabel(orderDiscountPercent, discountOn)}
            v={`−${money(rowAmount)}`}
            currency={currency}
            cls="discount"
          />
          {billSaving > 0.004 && (
            <div className="srow discount-note">
              <span className="k">
                {t("txn.lessOnBill").replace(
                  "{amount}",
                  `${currency ? `${currency} ` : ""}${money(billSaving)}`,
                )}
              </span>
            </div>
          )}
        </>
      )}
      <SumRow k={netLabel} v={money(net)} currency={currency} />
      <SumRow k={vatLabel} v={money(vat)} currency={currency} />
      <SumRow k={grandLabel} v={money(grand)} currency={currency} cls="rule total" />
      {children}
    </>
  );
}

/** Warning when projected receivables cross the customer credit limit. */
export function CreditLimitNotice({
  balance,
}: {
  balance: { credit_limit: number; projected: number; remaining: number | null; crossed: boolean } | null;
}) {
  if (!balance?.credit_limit || !balance.crossed) return null;
  return (
    <div className="note" role="status" style={{ marginBlockStart: 12 }}>
      <svg className="ic" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="8" cy="8" r="6.5" /><path d="M8 7.5v4M8 4.8v.6" />
      </svg>
      <span>
        <b>{t("txn.creditCrossed")}</b>
        <span>
          {" "}
          {t("txn.creditDetail")
            .replace("{projected}", money(balance.projected))
            .replace("{limit}", money(balance.credit_limit))}
        </span>
      </span>
    </div>
  );
}
