/**
 * Pick List form — new and edit.
 * Importers: App.tsx routes /pick-lists/new and /pick-lists/:name/edit.
 * API: taxmate.api.resource.insert / save.
 * Schema: purpose (Select: Delivery/Material Transfer/Manufacture), customer (Link),
 *   delivery_note (Link), work_order (Link), locations[item_code, qty, warehouse].
 * User: "Implement the plan… complete all the to-dos."
 */
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { parseNum } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormActions, FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";

const PURPOSES = ["Delivery", "Material Transfer", "Manufacture"] as const;
type Purpose = (typeof PURPOSES)[number];

type Line = { item_code: string; qty: number; warehouse: string };

type Doc = {
  name: string;
  purpose?: string;
  customer?: string;
  delivery_note?: string;
  work_order?: string;
  docstatus?: number;
  locations?: { item_code?: string; qty?: number; warehouse?: string }[];
};

export default function PickListForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<Doc>(DT.pickList, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });

  const [purpose, setPurpose] = useState<Purpose>("Delivery");
  const [customer, setCustomer] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [workOrder, setWorkOrder] = useState("");
  const [lines, setLines] = useState<Line[]>([{ item_code: "", qty: 1, warehouse: "" }]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const insert = useInsert();
  const save = useSave();

  useEffect(() => {
    if (!isNew && existing.data) {
      const d = existing.data;
      setPurpose((d.purpose as Purpose) ?? "Delivery");
      setCustomer(d.customer ?? "");
      setDeliveryNote(d.delivery_note ?? "");
      setWorkOrder(d.work_order ?? "");
      setLines(
        (d.locations ?? []).map((l) => ({
          item_code: l.item_code ?? "",
          qty: l.qty ?? 1,
          warehouse: l.warehouse ?? "",
        }))
      );
    }
  }, [isNew, existing.data]);

  if (!session.user) return <Navigate to="/" />;
  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data?.docstatus !== 0) return <Navigate to={`/pick-lists/${encodeURIComponent(name)}`} />;

  function addLine() { setLines((ls) => [...ls, { item_code: "", qty: 1, warehouse: "" }]); }
  function removeLine(i: number) { setLines((ls) => ls.filter((_, j) => j !== i)); }
  function setLine<K extends keyof Line>(i: number, k: K, v: Line[K]) {
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  }

  async function handleSave() {
    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, unknown> = {
        doctype: DT.pickList,
        purpose,
        ...(customer ? { customer } : {}),
        ...(deliveryNote ? { delivery_note: deliveryNote } : {}),
        ...(workOrder ? { work_order: workOrder } : {}),
        locations: lines
          .filter((l) => l.item_code)
          .map((l) => ({ doctype: "Pick List Item", item_code: l.item_code, qty: l.qty, warehouse: l.warehouse })),
      };
      if (isNew) {
        const created = await insert.createDoc(DT.pickList, body);
        nav(`/pick-lists/${encodeURIComponent((created as { name: string }).name)}`);
      } else {
        await save.updateDoc(DT.pickList, name, body);
        nav(`/pick-lists/${encodeURIComponent(name)}`);
      }
    } catch (e) { setSaveError(e); } finally { setSaving(false); }
  }

  return (
    <>
      <PageHead title={isNew ? t("picklist.new") : name} eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/pick-lists")}>{t("picklist.title")}</button>} />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout>
        <Card title={t("picklist.title")}>
          <Field label={t("picklist.col.purpose")}>
            <select className="inp" value={purpose} onChange={(e) => setPurpose(e.target.value as Purpose)}>
              {PURPOSES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
          {purpose === "Delivery" && (
            <Field label={t("picklist.col.dn")}>
              <LinkField doctype={DT.deliveryNote} value={deliveryNote} onChange={setDeliveryNote} placeholder="DN-…" />
            </Field>
          )}
          {purpose === "Manufacture" && (
            <Field label={t("picklist.col.wo")}>
              <LinkField doctype={DT.workOrder} value={workOrder} onChange={setWorkOrder} placeholder="MFG-WO-…" />
            </Field>
          )}
          <Field label={t("picklist.col.customer")}>
            <LinkField doctype={DT.customer} value={customer} onChange={setCustomer} placeholder={t("picklist.col.customer")} />
          </Field>
        </Card>
        <Card title={t("picklist.col.locations")}>
          {lines.map((ln, i) => (
            <div key={i} className="flex gap-2 mb-2 items-end">
              <Field label={i === 0 ? t("picklist.col.item") : ""}>
                <LinkField doctype={DT.item} value={ln.item_code} onChange={(v) => setLine(i, "item_code", v)} placeholder={t("pick.ph.item")} />
              </Field>
              <Field label={i === 0 ? t("picklist.col.qty") : ""}>
                <input className="inp" type="number" min={0.001} step={0.001} value={ln.qty}
                  onChange={(e) => setLine(i, "qty", parseNum(e.target.value))} />
              </Field>
              <Field label={i === 0 ? t("picklist.col.warehouse") : ""}>
                <LinkField doctype={DT.warehouse} value={ln.warehouse} onChange={(v) => setLine(i, "warehouse", v)} placeholder={t("pick.ph.warehouse")} />
              </Field>
              <button type="button" className="btn btn-ghost text-red-500" onClick={() => removeLine(i)} aria-label={t("common.remove")}>✕</button>
            </div>
          ))}
          <button type="button" className="btn btn-ghost text-sm mt-1" onClick={addLine}>+ {t("common.addLine")}</button>
        </Card>
        <FormActions
          onDiscard={() => nav(isNew ? "/pick-lists" : `/pick-lists/${encodeURIComponent(name)}`)}
          onSave={handleSave}
          busy={saving}
        />
      </FormLayout>
    </>
  );
}
