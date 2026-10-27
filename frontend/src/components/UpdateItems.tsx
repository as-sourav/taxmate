/**
 * Desk's Update Items dialog, for a submitted order or quotation.
 * Callers: sales order, purchase order, quotation, and supplier quotation detail.
 * API: taxmate.api.accounts.update_items → erpnext update_child_qty_rate.
 * Schema: each row keeps docname, item, qty, rate, uom, conversion factor,
 * description, dates, warehouse, and finished-good fields Desk sends.
 */
import { useEffect, useState } from "react";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { METHOD } from "../lib/frappe";
import { t } from "../i18n/strings";
import { Card, ErrorBox } from "./ui";
import LinkField from "./LinkField";

type Row = {
  name?: string;
  item_code?: string;
  qty?: number;
  rate?: number;
  uom?: string;
  conversion_factor?: number;
  description?: string;
  delivery_date?: string;
  schedule_date?: string;
  warehouse?: string;
  fg_item?: string;
  fg_item_qty?: number;
};

type Props = {
  doctype: string;
  name: string;
  items: Row[];
  onSaved: () => void;
};

function signature(items: Row[]): string {
  return items.map((row) => [row.name, row.qty, row.rate, row.fg_item, row.fg_item_qty, row.warehouse].join("|")).join(";");
}

export default function UpdateItems({ doctype, name, items, onSaved }: Props) {
  const gated = doctype === "Sales Order" || doctype === "Purchase Order";
  const allowed = useFrappeGetCall<{ message: { allowed?: number } }>(
    METHOD.canUpdateItems,
    { doctype, name },
    gated ? `can-update-${doctype}-${name}` : null,
  );
  const call = useFrappePostCall(METHOD.updateItems);
  const [rows, setRows] = useState<Row[]>(() => items.map((row) => ({ ...row })));
  const [error, setError] = useState<unknown>(null);
  const itemKey = signature(items);

  useEffect(() => {
    setRows(items.map((row) => ({ ...row })));
    // itemKey changes only when the saved rows change, so a keystroke does not reset the editor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemKey]);

  if (gated && allowed.isLoading) return null;
  if (gated && allowed.data?.message?.allowed === 0) return null;

  function patch(index: number, next: Partial<Row>) {
    setRows((current) => current.map((item, i) => (i === index ? { ...item, ...next } : item)));
  }

  async function save() {
    setError(null);
    try {
      await call.call({
        doctype,
        name,
        items: rows
          .filter((row) => row.item_code)
          .map((row) => ({
            docname: row.name,
            item_code: row.item_code,
            qty: Number(row.qty) || 0,
            rate: Number(row.rate) || 0,
            uom: row.uom,
            conversion_factor: row.conversion_factor,
            description: row.description,
            delivery_date: row.delivery_date,
            schedule_date: row.schedule_date,
            warehouse: row.warehouse,
            fg_item: row.fg_item,
            fg_item_qty: row.fg_item_qty,
          })),
      });
      onSaved();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Card title="Update items">
      {error ? <ErrorBox error={error} /> : null}
      {allowed.error ? <ErrorBox error={allowed.error} /> : null}
      {rows.map((row, index) => (
        <div key={row.name || index} className="grid3" style={{ marginBottom: 8 }}>
          {row.name ? (
            <span className="ctl readonly">{row.item_code}</span>
          ) : (
            <LinkField doctype="Item" value={row.item_code || ""} onChange={(item) => patch(index, { item_code: item })} />
          )}
          <input className="ctl" type="number" aria-label="Quantity" value={row.qty ?? ""}
            onChange={(event) => patch(index, { qty: Number(event.target.value) })} />
          <input className="ctl" type="number" aria-label="Rate" value={row.rate ?? ""}
            onChange={(event) => patch(index, { rate: Number(event.target.value) })} />
          <button type="button" className="btn quiet" aria-label="Remove" onClick={() => setRows((current) => current.filter((_, i) => i !== index))}>
            {t("soc.discard")}
          </button>
        </div>
      ))}
      <button type="button" className="btn ghost" onClick={() => setRows((current) => [...current, { item_code: "", qty: 1, rate: 0 }])}>
        {t("mr.addLine")}
      </button>
      <button type="button" className="btn" disabled={call.loading} onClick={() => void save()}>
        {call.loading ? t("soc.saving") : t("soc.save")}
      </button>
    </Card>
  );
}
