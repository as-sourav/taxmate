/**
 * BomForm — Phase 18. Create/edit BOM.
 * Callers: App.tsx /boms/new, /boms/:name/edit
 * API: taxmate.api.resource.insert / save on "BOM"
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { parseNum } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading } from "../../components/ui";
import { FormActions } from "../../components/form";
import { DocForm } from "../../components/screen";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";

type BomItem = { item_code: string; item_name?: string; qty: number; uom?: string; rate?: number };
type Doc = {
  name: string; item?: string; item_name?: string; quantity?: number; is_active?: number;
  is_default?: number; items?: (BomItem & { name?: string })[];
};

export default function BomForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const canSubmit = canSubmitSales(session.roles);

  const existing = useDoc<Doc>(DT.bom, isNew ? undefined : name, isNew ? null : name, { isPaused: () => isNew });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall(METHOD.submit);
  const itemCall = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.getItemDetails);

  const [item, setItem] = useState("");
  const [itemName, setItemName] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [isActive, setIsActive] = useState<0 | 1>(1);
  const [isDefault, setIsDefault] = useState<0 | 1>(0);
  const [rows, setRows] = useState<(BomItem & { _key: string })[]>([]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const d = existing.data;
    if (!d || loaded) return;
    setItem(d.item || "");
    setItemName(d.item_name || "");
    setQuantity(d.quantity || 1);
    setIsActive(d.is_active ? 1 : 0);
    setIsDefault(d.is_default ? 1 : 0);
    setRows((d.items ?? []).map((r, i) => ({ ...r, _key: String(i) })));
    setLoaded(true);
  }, [existing.data, loaded]);

  const rowKey = useRef(0);
  const finishedReq = useRef("");
  const addRow = () => {
    rowKey.current += 1;
    const key = `m${rowKey.current}`;
    setRows((rs) => [...rs, { _key: key, item_code: "", qty: 1, uom: "Nos" }]);
  };
  const removeRow = (key: string) => setRows((rs) => rs.filter((r) => r._key !== key));
  const setRow = (key: string, field: string, val: string | number) =>
    setRows((rs) => rs.map((r) => r._key === key ? { ...r, [field]: val } : r));

  async function fetchItem(key: string, code: string) {
    if (!code || !session.company) return;
    try {
      const res = await itemCall.call({
        ctx: { doctype: DT.materialRequest, item_code: code, company: session.company, qty: 1, conversion_rate: 1 },
      });
      const m = res?.message as Record<string, unknown> | undefined;
      if (!m) return;
      setRows((rs) => rs.map((r) => r._key === key && r.item_code === code ? {
        ...r,
        uom: m.stock_uom ? String(m.stock_uom) : r.uom,
        item_name: m.item_name ? String(m.item_name) : r.item_name,
      } : r));
    } catch (err) {
      setSaveError(err);
    }
  }

  async function onFinishedItem(code: string) {
    setItem(code);
    setItemName("");
    finishedReq.current = code;
    if (!code || !session.company) return;
    try {
      const res = await itemCall.call({
        ctx: { doctype: DT.materialRequest, item_code: code, company: session.company, qty: quantity || 1, conversion_rate: 1 },
      });
      if (finishedReq.current !== code) return;
      const m = res?.message as Record<string, unknown> | undefined;
      if (m?.item_name) setItemName(String(m.item_name));
    } catch (err) {
      if (finishedReq.current !== code) return;
      setSaveError(err);
    }
  }

  const checks = useMemo(() => [
    { label: t("bom.col.item"), ok: !!item },
    { label: t("bom.col.qty"), ok: quantity > 0 },
    { label: t("sr.check.lines"), ok: rows.length > 0 && rows.every((r) => !!r.item_code) },
  ], [item, quantity, rows]);
  const ready = checks.every((c) => c.ok);

  async function saveFn(andSubmit = false) {
    if (!ready) return;
    setBusy(true); setSaveError(null);
    try {
      const payload = {
        item, quantity, is_active: isActive, is_default: isDefault,
        company: session.company,
        currency: session.currency,
        items: rows.map(({ _key: _k2, ...r }) => r),
      };
      let n: string;
      if (isNew) {
        const doc = (await create.createDoc(DT.bom, payload)) as { name: string };
        n = doc.name;
      } else {
        await update.updateDoc(DT.bom, name, payload);
        n = name;
      }
      if (andSubmit) await submitCall.call({ doc: { doctype: DT.bom, name: n } });
      nav(`/boms/${encodeURIComponent(n)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;

  return (
    <DocForm
      eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/boms")}>{t("bom.title")}</button>}
      title={isNew ? t("bom.new") : itemName || item || name}
      checks={checks}
      readyCaption={t("sr.readyCap")}
      alert={saveError ? <ErrorBox error={saveError} /> : null}
      actions={
        <FormActions
          onSave={() => void saveFn(false)}
          onSubmit={canSubmit ? () => void saveFn(true) : undefined}
          onDiscard={() => nav(isNew ? "/boms" : `/boms/${encodeURIComponent(name)}`)}
          busy={busy}
          ready={ready}
        />
      }
    >
      <Card num={1} title={t("bom.col.item")}>
        <div className="grid2">
          <Field label={t("bom.col.item")} required>
            <LinkField doctype={DT.item} value={item} onChange={(v) => void onFinishedItem(v)} placeholder={t("bom.itemPh")} />
            {itemName ? <div className="iname">{itemName}</div> : null}
          </Field>
          <Field label={t("bom.col.qty")}>
            <input className="ctl" type="number" min={0.001} value={quantity} onChange={(e) => setQuantity(parseNum(e.target.value))} />
          </Field>
          <Field label={t("bom.col.active")}>
            <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 38 }}>
              <input type="checkbox" checked={!!isActive} onChange={(e) => setIsActive(e.target.checked ? 1 : 0)} />
              {t("bom.activeLabel")}
            </label>
          </Field>
          <Field label={t("bom.col.default")}>
            <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 38 }}>
              <input type="checkbox" checked={!!isDefault} onChange={(e) => setIsDefault(e.target.checked ? 1 : 0)} />
              {t("bom.defaultLabel")}
            </label>
          </Field>
        </div>
      </Card>
      <Card num={2} title={t("bom.materials")} bodyClass={null as unknown as string}>
        {/* Material names the line; its quantity is the one figure typed every
            time. The UOM arrives filled in from the item, so it sits behind
            "More". */}
        <LineItems<BomItem & { _key: string }>
          rows={rows}
          showIndex
          onRemove={(i) => removeRow(rows[i]._key)}
          addLabel={t("bom.addMaterial")}
          onAdd={addRow}
          fields={[
            {
              key: "material", label: t("bom.col.material"), slot: "title", td: { minWidth: 200 },
              render: (r) => (
                <>
                  <LinkField doctype={DT.item} value={r.item_code} onChange={(v) => { setRow(r._key, "item_code", v); void fetchItem(r._key, v); }} placeholder={t("bom.matPh")} />
                  {r.item_name && r.item_name !== r.item_code ? <div className="iname">{r.item_name}</div> : null}
                </>
              ),
            },
            {
              key: "qty", label: t("bom.col.matQty"), slot: "primary", numeric: true,
              render: (r) => (
                <input className="ctl mini nn" style={{ width: 90 }} type="number" min={0.001} step={0.001} value={r.qty} onChange={(e) => setRow(r._key, "qty", parseNum(e.target.value))} />
              ),
            },
            {
              key: "uom", label: t("bom.col.uom"),
              render: (r) => (
                <input className="ctl mini" style={{ width: 80 }} type="text" value={r.uom || ""} onChange={(e) => setRow(r._key, "uom", e.target.value)} />
              ),
            },
          ] as LineField<BomItem & { _key: string }>[]}
        />
      </Card>
    </DocForm>
  );
}
