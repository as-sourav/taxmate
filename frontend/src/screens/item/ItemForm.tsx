import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";
import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { parseNum } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import LinkField from "../../components/LinkField";

const COMMON_UOMS = ["Nos", "Unit", "Box", "Set", "Pair", "Kg", "g", "Litre", "Ltr", "Meter", "m", "Dozen", "Hour", "Day"];

type UomConvRow = {
  _key: string;
  uom: string;
  conversion_factor: number;
};

type ItemDoc = {
  name: string;
  item_code?: string;
  item_name?: string;
  item_group?: string;
  custom_company?: string;
  stock_uom?: string;
  brand?: string;
  is_stock_item?: number;
  is_sales_item?: number;
  is_purchase_item?: number;
  description?: string;
  valuation_method?: string;
  uae_item_type?: string;
  is_zero_rated?: number;
  is_exempt?: number;
  hs_code?: string;
  sac_code?: string;
  standard_rate?: number;
  safety_stock?: number;
  has_serial_no?: number;
  has_batch_no?: number;
  serial_no_series?: string;
  create_new_batch?: number;
  batch_number_series?: string;
  uoms?: { uom?: string; conversion_factor?: number }[];
  item_defaults?: { company?: string; default_warehouse?: string; income_account?: string; expense_account?: string }[];
  weight_per_unit?: number;
  weight_uom?: string;
  has_expiry_date?: number;
  shelf_life_in_days?: number;
  taxes?: { item_tax_template?: string }[];
  has_variants?: number;
  attributes?: { attribute?: string }[];
  barcodes?: { barcode?: string }[];
  disabled?: number;
  reorder_levels?: { warehouse?: string; warehouse_reorder_level?: number; warehouse_reorder_qty?: number; material_request_type?: string }[];
};

export default function ItemForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<ItemDoc>(DT.item, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });
  const groups = useDocList<{ name: string }>(DT.itemGroup, {
    fields: ["name"], filters: [["is_group", "=", 0]], limit: 80,
  });
  const uoms = useDocList<{ name: string }>(DT.uom, { fields: ["name"], limit: 80 });
  const settings = useDoc<{ selling_price_list?: string }>(DT.sellingSettings, DT.sellingSettings);
  const create = useInsert();
  const update = useSave();

  /* ERPNext's own fallback when Selling Settings has no default
     (erpnext/stock/doctype/item/item.py:274) — without it, editing an item
     whose price ERPNext put on Standard Selling would refuse to save.    */
  const priceList = settings.data?.selling_price_list || (settings.data ? "Standard Selling" : undefined);

  /* The selling rate lives on Item Price, not on Item.
     On INSERT, ERPNext's Item.after_insert creates the Item Price from
     standard_rate (erpnext/stock/doctype/item/item.py:178) — so a second
     create here would collide. On UPDATE it does nothing at all, which is why
     an edited rate has to be written to the Item Price explicitly.

     The filter matches Item Price's own uniqueness key as far as this form
     models it: a customer- or supplier-specific row is a different price and
     must never be overwritten by the general rate (check_duplicates,
     erpnext/stock/doctype/item_price/item_price.py:105).                 */
  const priceReady = !isNew && !!priceList;
  const existingPrice = useDocList<{
    name: string; price_list_rate: number; uom?: string; customer?: string; supplier?: string;
  }>(
    DT.itemPrice,
    {
      fields: ["name", "price_list_rate", "uom", "customer", "supplier"],
      filters: [
        ["item_code", "=", name],
        ["price_list", "=", priceList ?? ""],
        ["selling", "=", 1],
      ],
      orderBy: { field: "modified", order: "desc" },
      limit: 20,
    },
    priceReady ? `item-price-${name}-${priceList}` : null,
  );
  /* A null-key SWR hook reports isLoading:false with data:undefined, so
     "resolved" has to be tracked explicitly — otherwise a save that lands
     before the lookup returns would create a duplicate Item Price.       */
  const priceResolved = priceReady && existingPrice.data !== undefined;

  const [form, setForm] = useState({
    item_code: "",
    item_name: "",
    item_group: "",
    custom_company: "",
    stock_uom: "Nos",
    brand: "",
    is_stock_item: 0 as 0 | 1,
    is_sales_item: 1 as 0 | 1,
    is_purchase_item: 1 as 0 | 1,
    default_warehouse: "",
    income_account: "",
    expense_account: "",
    weight_per_unit: 0,
    weight_uom: "",
    has_expiry_date: 0 as 0 | 1,
    shelf_life_in_days: 0,
    item_tax_template: "",
    has_variants: 0 as 0 | 1,
    variant_attributes: [] as string[],
    description: "",
    valuation_method: "",
    uae_item_type: "Service",
    is_zero_rated: 0 as 0 | 1,
    is_exempt: 0 as 0 | 1,
    hs_code: "",
    sac_code: "",
    standard_rate: 0,
    barcode: "",
    safety_stock: 0,
    reorder_warehouse: "",
    reorder_level: 0,
    reorder_qty: 0,
    has_serial_no: 0 as 0 | 1,
    has_batch_no: 0 as 0 | 1,
    serial_no_series: "",
    create_new_batch: 0 as 0 | 1,
    batch_number_series: "",
    disabled: 0 as 0 | 1,
  });
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [uomRows, setUomRows] = useState<UomConvRow[]>([]);
  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));
  useEffect(() => {
    const company = session.company || "";
    if (!isNew || !company) return;
    setForm((f) => (f.custom_company ? f : { ...f, custom_company: company }));
  }, [isNew, session.company]);
  let _uomKey = 0;
  const newUomKey = () => `u${++_uomKey}`;
  const onHand = useFrappeGetCall<{ message: { total: number; warehouses: { warehouse: string; actual_qty: number }[] } }>(
    METHOD.itemQty,
    !isNew && form.is_stock_item ? { item_code: name } : undefined,
    !isNew && form.is_stock_item ? `item-qty-${name}` : null,
  );

  // Check whether SLE exists for this item (limit 1) — serial/batch flags cannot change once stock is posted.
  const sleList = useDocList<{ name: string }>(
    DT.stockLedgerEntry,
    { fields: ["name"], filters: [["item_code", "=", name]] as never, limit: 1 },
    !isNew ? `sle-exists-${name}` : null,
  );
  const hasSle = !isNew && (sleList.data ?? []).length > 0;

  /* One effect, not two.
     Item.standard_rate is only read at insert; once an Item Price exists that
     row is the real selling rate and Item.standard_rate can be stale. Two
     separate effects let a background SWR revalidation of the Item re-run the
     first one alone and quietly put the stale rate back in the field — so the
     rate is resolved here, in the same pass that loads the document.     */
  /* Only the general rate. A customer- or supplier-specific Item Price in the
     same price list is a different price and must never be overwritten with
     the item's headline rate.                                             */
  const priceRow = existingPrice.data?.find((r) => !r.customer && !r.supplier);
  useEffect(() => {
    const d = existing.data;
    if (!d) return;
    // Prefer company-matched Item Default (ERPNext child). Callers: App /catalogue/items/:name.
    // User: Complete everything and make frontend completely comprehensive and complete
    const companyRow = (d.item_defaults ?? []).find((r) => r.company === session.company)
      || (d.item_defaults ?? [])[0];
    const companyWh = companyRow?.default_warehouse || "";
    setForm({
      item_code: d.item_code || d.name,
      item_name: d.item_name || "",
      item_group: d.item_group || "",
      custom_company: d.custom_company || companyRow?.company || session.company || "",
      stock_uom: d.stock_uom || "Nos",
      brand: d.brand || "",
      is_stock_item: (d.is_stock_item || 0) as 0 | 1,
      is_sales_item: ((d.is_sales_item ?? 1) || 0) as 0 | 1,
      is_purchase_item: ((d.is_purchase_item ?? 1) || 0) as 0 | 1,
      default_warehouse: companyWh,
      income_account: companyRow?.income_account || "",
      expense_account: companyRow?.expense_account || "",
      weight_per_unit: d.weight_per_unit || 0,
      weight_uom: d.weight_uom || "",
      has_expiry_date: (d.has_expiry_date ? 1 : 0) as 0 | 1,
      shelf_life_in_days: d.shelf_life_in_days || 0,
      item_tax_template: d.taxes?.[0]?.item_tax_template || "",
      has_variants: (d.has_variants ? 1 : 0) as 0 | 1,
      variant_attributes: (d.attributes ?? []).map((a) => a.attribute || "").filter(Boolean),
      description: d.description || "",
      valuation_method: d.valuation_method || "",
      uae_item_type: d.uae_item_type || "Service",
      is_zero_rated: (d.is_zero_rated || 0) as 0 | 1,
      is_exempt: (d.is_exempt || 0) as 0 | 1,
      hs_code: d.hs_code || "",
      sac_code: d.sac_code || "",
      standard_rate: priceRow ? Number(priceRow.price_list_rate) || 0 : d.standard_rate || 0,
      barcode: (d.barcodes ?? [])[0]?.barcode || "",
      safety_stock: Number(d.safety_stock) || 0,
      reorder_warehouse: (d.reorder_levels ?? [])[0]?.warehouse || "",
      reorder_level: Number((d.reorder_levels ?? [])[0]?.warehouse_reorder_level) || 0,
      reorder_qty: Number((d.reorder_levels ?? [])[0]?.warehouse_reorder_qty) || 0,
      has_serial_no: (d.has_serial_no || 0) as 0 | 1,
      has_batch_no: (d.has_batch_no || 0) as 0 | 1,
      serial_no_series: d.serial_no_series || "",
      create_new_batch: (d.create_new_batch || 0) as 0 | 1,
      batch_number_series: d.batch_number_series || "",
      disabled: (d.disabled ? 1 : 0) as 0 | 1,
    });
    // Load UOM conversions (exclude the stock UOM row which ERPNext auto-adds with factor 1)
    setUomRows(
      (d.uoms ?? [])
        .filter((r) => r.uom && r.uom !== d.stock_uom)
        .map((r) => ({
          _key: `u${Math.random()}`,
          uom: r.uom || "",
          conversion_factor: Number(r.conversion_factor) || 1,
        }))
    );
  }, [existing.data, priceRow, session.company]);

  const ready =
    !!form.item_code && !!form.item_name && !!form.item_group && !!form.stock_uom &&
    !!form.uae_item_type &&
    (!form.is_sales_item || !!form.custom_company) &&
    // On edit, hold Save until the Item Price lookup has answered.
    (isNew || priceResolved);

  async function save() {
    setBusy(true);
    setSaveError(null);
    try {
      const payload = {
        disabled: form.disabled,
        item_code: form.item_code,
        item_name: form.item_name,
        item_group: form.item_group,
        custom_company: form.custom_company || undefined,
        stock_uom: form.stock_uom,
        brand: form.brand || undefined,
        is_stock_item: form.is_stock_item,
        is_sales_item: form.is_sales_item,
        is_purchase_item: form.is_purchase_item,
        description: form.description || undefined,
        valuation_method: form.is_stock_item && form.valuation_method ? form.valuation_method : undefined,
        uae_item_type: form.uae_item_type,
        is_zero_rated: form.is_zero_rated,
        is_exempt: form.is_exempt,
        hs_code: form.hs_code || undefined,
        sac_code: form.sac_code || undefined,
        standard_rate: form.standard_rate,
        safety_stock: form.safety_stock || undefined,
        has_serial_no: form.is_stock_item ? form.has_serial_no : 0,
        has_batch_no: form.is_stock_item ? form.has_batch_no : 0,
        serial_no_series: form.is_stock_item && form.has_serial_no ? form.serial_no_series || undefined : undefined,
        create_new_batch: form.is_stock_item && form.has_batch_no ? form.create_new_batch : 0,
        batch_number_series: form.is_stock_item && form.has_batch_no ? form.batch_number_series || undefined : undefined,
        weight_per_unit: form.weight_per_unit || 0,
        weight_uom: form.weight_uom || undefined,
        has_expiry_date: form.has_expiry_date,
        shelf_life_in_days: form.shelf_life_in_days || 0,
        taxes: form.item_tax_template ? [{ item_tax_template: form.item_tax_template }] : [],
        has_variants: form.has_variants,
        attributes: form.has_variants
          ? form.variant_attributes.filter(Boolean).map((attribute) => ({ attribute }))
          : undefined,
        barcodes: form.barcode ? [{ barcode: form.barcode }] : undefined,
        reorder_levels: form.reorder_warehouse
          ? [{
              warehouse: form.reorder_warehouse,
              warehouse_reorder_level: form.reorder_level || 0,
              warehouse_reorder_qty: form.reorder_qty || 0,
              material_request_type: "Purchase",
            }]
          : undefined,
        uoms: uomRows.length > 0
          ? [
              // ERPNext expects the stock UOM row first with factor 1
              { uom: form.stock_uom, conversion_factor: 1 },
              ...uomRows.filter((r) => r.uom && r.conversion_factor > 0).map(({ _key: _k, ...r }) => r),
            ]
          : undefined,
        item_defaults: (form.custom_company || session.company)
          ? [{
              company: form.custom_company || session.company,
              default_warehouse: form.default_warehouse || undefined,
              income_account: form.income_account || undefined,
              expense_account: form.expense_account || undefined,
            }]
          : undefined,
      };
      const doc = isNew
        ? await create.createDoc(DT.item, payload)
        : await update.updateDoc(DT.item, name, payload);
      const code = (doc as { name: string }).name;

      /* New item: ERPNext already created the Item Price from standard_rate.
         Existing item: push the rate onto the Item Price ourselves, because
         nothing on the server does. Failures are NOT swallowed — a price that
         silently does not save is worse than an error message.            */
      if (!isNew) {
        if (!priceResolved || !priceList) {
          /* Guarded by the disabled Save button; this is the belt-and-braces
             so a race can never create a second Item Price.              */
          throw new Error(t("item.err.priceListLoading"));
        }
        if (priceRow) {
          if (Number(priceRow.price_list_rate) !== Number(form.standard_rate)) {
            await update.updateDoc(DT.itemPrice, priceRow.name, {
              price_list_rate: form.standard_rate,
            });
          }
        } else if (form.standard_rate) {
          await create.createDoc(DT.itemPrice, {
            item_code: code,
            price_list: priceList,
            price_list_rate: form.standard_rate,
            uom: form.stock_uom,
            selling: 1,
          });
        }
        await existingPrice.mutate();
      }
      nav(`/catalogue/items/${encodeURIComponent(code)}`);
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
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/catalogue/items")}>{t("nav.items")}</button>}
        title={isNew ? t("item.new") : form.item_name || name}
        actions={
          <>
            {!isNew ? (<DocHistory doctype={DT.item} name={name} />) : null}

            <button className="btn ghost" onClick={() => nav("/catalogue/items")}>{t("soc.discard")}</button>
            <button className="btn" disabled={busy || !ready} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
          </>
        }
      />
      {saveError && <ErrorBox error={saveError} />}
      <Card title={t("item.identity")}>
        <div className="grid2">
          <Field label={t("item.col.code")} required>
            <input className="ctl" value={form.item_code} disabled={!isNew} onChange={(e) => set("item_code", e.target.value)} />
          </Field>
          <Field label={t("item.col.name")} required>
            <input className="ctl" value={form.item_name} onChange={(e) => set("item_name", e.target.value)} />
          </Field>
          <CheckField
            label={t("common.disabled")}
            hint={t("doc.offHint")}
            checked={!!form.disabled}
            onChange={(on) => set("disabled", on ? 1 : 0)}
          />
          <Field label={t("item.description")}>
            <input className="ctl" value={form.description} onChange={(e) => set("description", e.target.value)} aria-label={t("item.description")} />
          </Field>
          <Field label={t("item.company")} required={!!form.is_sales_item} hint={t("item.companyHint")}>
            <LinkField
              doctype={DT.company}
              value={form.custom_company}
              onChange={(v) => set("custom_company", v)}
              placeholder={t("item.company")}
            />
          </Field>
          <Field label={t("item.col.group")} required>
            <select className="ctl" value={form.item_group} onChange={(e) => set("item_group", e.target.value)}>
              <option value="" />
              {(groups.data ?? []).map((g) => <option key={g.name} value={g.name}>{g.name}</option>)}
            </select>
          </Field>
          <Field label={t("item.uom")} required>
            <select className="ctl" value={form.stock_uom} onChange={(e) => set("stock_uom", e.target.value)}>
              {(() => {
                const all = (uoms.data ?? []).map((u) => u.name);
                const preferred = COMMON_UOMS.filter((u) => all.includes(u) || all.length === 0);
                // Always include current value if missing from preferred
                const visible = preferred.includes(form.stock_uom) ? preferred : [form.stock_uom, ...preferred];
                return visible.map((u) => <option key={u} value={u}>{u}</option>);
              })()}
            </select>
          </Field>
          <Field label={t("item.brand")}>
            <LinkField
              doctype={DT.brand}
              value={form.brand}
              onChange={(v) => set("brand", v)}
            />
          </Field>
          <Field label={t("item.barcode")}>
            <input className="ctl" value={form.barcode} onChange={(e) => set("barcode", e.target.value)} placeholder={t("item.ph.barcode")} />
          </Field>
          <Field label={t("item.col.stock")}>
            <select className="ctl" value={String(form.is_stock_item)} onChange={(e) => set("is_stock_item", Number(e.target.value))}>
              <option value="0">{t("no")}</option>
              <option value="1">{t("yes")}</option>
            </select>
          </Field>
          <Field label={t("item.sell")}>
            <select className="ctl" value={String(form.is_sales_item)} onChange={(e) => set("is_sales_item", Number(e.target.value))} aria-label={t("item.sell")}>
              <option value="0">{t("no")}</option>
              <option value="1">{t("yes")}</option>
            </select>
          </Field>
          <Field label={t("item.buy")}>
            <select className="ctl" value={String(form.is_purchase_item)} onChange={(e) => set("is_purchase_item", Number(e.target.value))} aria-label={t("item.buy")}>
              <option value="0">{t("no")}</option>
              <option value="1">{t("yes")}</option>
            </select>
          </Field>
          {!!form.is_stock_item && (
            <Field label={t("item.valuation")}>
              <select
                className="ctl"
                value={form.valuation_method}
                onChange={(e) => set("valuation_method", e.target.value)}
                aria-label={t("item.valuation")}
              >
                <option value="">{t("item.valuation.default")}</option>
                <option value="FIFO">{t("item.valuation.fifo")}</option>
                <option value="Moving Average">{t("item.valuation.moving")}</option>
              </select>
            </Field>
          )}
          {!!form.is_stock_item && (
            <Field label={t("item.defaultWh")}>
              <LinkField
                doctype={DT.warehouse}
                value={form.default_warehouse}
                onChange={(v) => set("default_warehouse", v)}
                filters={(form.custom_company || session.company) ? [["company", "=", form.custom_company || session.company], ["is_group", "=", 0]] : undefined}
              />
            </Field>
          )}
          <Field label={t("item.taxTpl")}>
            <LinkField doctype={DT.itemTaxTemplate} value={form.item_tax_template} onChange={(v) => set("item_tax_template", v)} />
          </Field>
          <Field label={t("item.income")}>
            <LinkField doctype={DT.account} value={form.income_account} onChange={(v) => set("income_account", v)} />
          </Field>
          <Field label={t("item.expense")}>
            <LinkField doctype={DT.account} value={form.expense_account} onChange={(v) => set("expense_account", v)} />
          </Field>
          <div className="grid2">
            <Field label={t("item.weight")}>
              <input className="ctl" type="number" min={0} step="any" value={form.weight_per_unit || ""} onChange={(e) => set("weight_per_unit", Number(e.target.value))} />
            </Field>
            <Field label={t("uom.title")}>
              <LinkField doctype={DT.uom} value={form.weight_uom} onChange={(v) => set("weight_uom", v)} />
            </Field>
          </div>
          <CheckField label={t("item.variants")} hint={t("doc.onHint")} checked={!!form.has_variants} onChange={(v) => set("has_variants", v ? 1 : 0)} />
          {!!form.has_variants && (
            <>
              {form.variant_attributes.map((attr, i) => (
                <Field key={i} label={t("item.attribute")}>
                  <LinkField
                    doctype="Item Attribute"
                    value={attr}
                    onChange={(v) => setForm((f) => ({
                      ...f,
                      variant_attributes: f.variant_attributes.map((a, j) => (j === i ? v : a)),
                    }))}
                  />
                </Field>
              ))}
              <button
                type="button"
                className="btn quiet"
                onClick={() => setForm((f) => ({ ...f, variant_attributes: [...f.variant_attributes, ""] }))}
              >
                {t("tx.addRow")}
              </button>
            </>
          )}
          <CheckField label={t("item.expiry")} hint={t("doc.onHint")} checked={!!form.has_expiry_date} onChange={(v) => set("has_expiry_date", v ? 1 : 0)} />
          {!!form.has_expiry_date && (
            <Field label={t("item.shelf")}>
              <input className="ctl" type="number" min={0} value={form.shelf_life_in_days || ""} onChange={(e) => set("shelf_life_in_days", Number(e.target.value))} />
            </Field>
          )}
          {!isNew && !!form.is_stock_item && onHand.data?.message && (
            <Field label={t("item.onHand")}>
              <div className="ctl" style={{ background: "var(--bg-faint)", cursor: "default" }}>
                {t("item.onHandTotal")}: {onHand.data.message.total ?? 0}
                {(onHand.data.message.warehouses ?? []).length > 0 && (
                  <ul style={{ margin: "6px 0 0", padding: 0, listStyle: "none", fontSize: 12, color: "var(--faint)" }}>
                    {onHand.data.message.warehouses.map((r) => (
                      <li key={r.warehouse}>{r.warehouse}: {r.actual_qty}</li>
                    ))}
                  </ul>
                )}
              </div>
            </Field>
          )}
          <Field label={t("item.kind")} required>
            <select className="ctl" value={form.uae_item_type} onChange={(e) => set("uae_item_type", e.target.value)}>
              <option value="Goods">{t("item.goods")}</option>
              <option value="Service">{t("item.service")}</option>
              <option value="Both">{t("item.both")}</option>
            </select>
          </Field>
          <Field label={t("item.col.vat")}>
            <select className="ctl" value={form.is_zero_rated ? "zero" : form.is_exempt ? "exempt" : "standard"}
              onChange={(e) => {
                set("is_zero_rated", e.target.value === "zero" ? 1 : 0);
                set("is_exempt", e.target.value === "exempt" ? 1 : 0);
              }}>
              <option value="standard">{t("item.standard")}</option>
              <option value="zero">{t("item.zero")}</option>
              <option value="exempt">{t("item.exempt")}</option>
            </select>
          </Field>
          {(form.uae_item_type === "Goods" || form.uae_item_type === "Both") && (
            <Field label={t("item.hs")}>
              <input className="ctl" value={form.hs_code} onChange={(e) => set("hs_code", e.target.value)} />
            </Field>
          )}
          {(form.uae_item_type === "Service" || form.uae_item_type === "Both") && (
            <Field label={t("item.sac")}>
              <input className="ctl" value={form.sac_code} onChange={(e) => set("sac_code", e.target.value)} />
            </Field>
          )}
          <Field label={t("item.col.rate")}>
            <input className="ctl" value={form.standard_rate} onChange={(e) => set("standard_rate", parseNum(e.target.value))} />
          </Field>
          {!!form.is_stock_item && (
            <Field label={t("item.safetyStock")}>
              <input className="ctl" type="number" min={0} value={form.safety_stock}
                onChange={(e) => set("safety_stock", parseNum(e.target.value))} />
            </Field>
          )}
        </div>
      </Card>
      {!!form.is_stock_item && (
        <Card title={t("item.reorder")}>
          <div className="grid2">
            <Field label={t("item.reorderWh")}>
              <LinkField
                doctype={DT.warehouse}
                value={form.reorder_warehouse}
                onChange={(v) => set("reorder_warehouse", v)}
                filters={(form.custom_company || session.company) ? [["company", "=", form.custom_company || session.company], ["is_group", "=", 0]] : undefined}
              />
            </Field>
            <Field label={t("item.reorderLevel")}>
              <input className="ctl" type="number" min={0} value={form.reorder_level}
                onChange={(e) => set("reorder_level", parseNum(e.target.value))} />
            </Field>
            <Field label={t("item.reorderQty")}>
              <input className="ctl" type="number" min={0} value={form.reorder_qty}
                onChange={(e) => set("reorder_qty", parseNum(e.target.value))} />
            </Field>
          </div>
        </Card>
      )}
      {!!form.is_stock_item && (
        <Card title={t("item.serialBatch")}>
          {hasSle && (
            <p style={{ color: "var(--warning, #b45309)", marginBottom: 8, fontSize: 13 }}>
              {t("item.sleWarning")}
            </p>
          )}
          <div className="grid2">
            <Field label={t("item.hasSerialNo")}>
              <select className="ctl" value={String(form.has_serial_no)}
                disabled={hasSle}
                onChange={(e) => {
                  set("has_serial_no", Number(e.target.value));
                  if (!Number(e.target.value)) set("serial_no_series", "");
                }}>
                <option value="0">{t("no")}</option>
                <option value="1">{t("yes")}</option>
              </select>
            </Field>
            {!!form.has_serial_no && (
              <Field label={t("item.serialNoSeries")}>
                <input className="ctl" value={form.serial_no_series}
                  onChange={(e) => set("serial_no_series", e.target.value)}
                  placeholder={t("item.ph.serialSeries")} />
              </Field>
            )}
            <Field label={t("item.hasBatchNo")}>
              <select className="ctl" value={String(form.has_batch_no)}
                disabled={hasSle}
                onChange={(e) => {
                  set("has_batch_no", Number(e.target.value));
                  if (!Number(e.target.value)) { set("create_new_batch", 0); set("batch_number_series", ""); }
                }}>
                <option value="0">{t("no")}</option>
                <option value="1">{t("yes")}</option>
              </select>
            </Field>
            {!!form.has_batch_no && (
              <>
                <Field label={t("item.createNewBatch")}>
                  <select className="ctl" value={String(form.create_new_batch)}
                    onChange={(e) => set("create_new_batch", Number(e.target.value))}>
                    <option value="0">{t("no")}</option>
                    <option value="1">{t("yes")}</option>
                  </select>
                </Field>
                <Field label={t("item.batchNumberSeries")}>
                  <input className="ctl" value={form.batch_number_series}
                    onChange={(e) => set("batch_number_series", e.target.value)}
                    placeholder={t("item.ph.batchSeries")} />
                </Field>
              </>
            )}
          </div>
        </Card>
      )}
      <Card title={t("item.uomConversions")}>
        <p style={{ color: "var(--faint)", fontSize: 12, marginBottom: 8 }}>
          {t("item.uom.factorHint")
            .replace("{uom}", t("item.uom.exampleUom"))
            .replace("{stockUom}", form.stock_uom || t("item.uom.stockUomWord"))}
        </p>
        {uomRows.length === 0 ? (
          <p style={{ color: "var(--faint)", marginBottom: 8 }}>{t("item.uomConversions")}: —</p>
        ) : (
          <table className="data-table" style={{ marginBottom: 8 }}>
            <thead>
              <tr>
                <th>{t("item.uom.uom")}</th>
                <th>{t("item.uom.factor")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {uomRows.map((r) => (
                <tr key={r._key}>
                  <td>
                    <select
                      className="ctl"
                      value={r.uom}
                      onChange={(e) =>
                        setUomRows((rs) =>
                          rs.map((row) => row._key === r._key ? { ...row, uom: e.target.value } : row)
                        )
                      }
                    >
                      <option value="" />
                      {(uoms.data ?? []).map((u) => (
                        <option key={u.name} value={u.name}>{u.name}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="ctl"
                      type="number"
                      min={0.0001}
                      step={0.001}
                      value={r.conversion_factor}
                      onChange={(e) =>
                        setUomRows((rs) =>
                          rs.map((row) => row._key === r._key ? { ...row, conversion_factor: Number(e.target.value) } : row)
                        )
                      }
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => setUomRows((rs) => rs.filter((row) => row._key !== r._key))}
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
            setUomRows((rs) => [...rs, { _key: newUomKey(), uom: "", conversion_factor: 1 }])
          }
        >
          {t("item.addUom")}
        </button>
      </Card>
    </>
  );
}
