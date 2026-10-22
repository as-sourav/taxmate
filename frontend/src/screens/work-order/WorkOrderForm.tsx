/**
 * WorkOrderForm — Phase 18. Create + submit Work Order, then create SE.
 * Callers: App.tsx /work-orders/new, /work-orders/:name/edit
 * API: taxmate.api.resource.insert / save; workflow.submit
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { parseNum, toIsoDate } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading } from "../../components/ui";
import { FormActions } from "../../components/form";
import { DocForm } from "../../components/screen";
import LinkField from "../../components/LinkField";

const today = toIsoDate(new Date());
type Doc = { name: string; item_name?: string; bom_no?: string; qty?: number; planned_start_date?: string; wip_warehouse?: string; fg_warehouse?: string; docstatus?: number };

export default function WorkOrderForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const canSubmit = canSubmitSales(session.roles);

  const existing = useDoc<Doc>(DT.workOrder, isNew ? undefined : name, isNew ? null : name, { isPaused: () => isNew });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall(METHOD.submit);

  const [bom, setBom] = useState("");
  const pickedBom = useRef("");
  const qtyEdited = useRef(false);
  const bomDoc = useDoc<{ name: string; item?: string; item_name?: string; quantity?: number }>(
    DT.bom, bom || undefined, bom ? `wo-bom-${bom}` : null,
  );
  const [qty, setQty] = useState(1);
  const [startDate, setStartDate] = useState(today);
  const [wipWarehouse, setWipWarehouse] = useState("");
  const [fgWarehouse, setFgWarehouse] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const d = existing.data;
    if (!d || loaded) return;
    if (d.docstatus !== 0) { nav(`/work-orders/${encodeURIComponent(name)}`, { replace: true }); return; }
    setBom(d.bom_no || "");
    setQty(d.qty || 1);
    setStartDate(d.planned_start_date || today);
    setWipWarehouse(d.wip_warehouse || "");
    setFgWarehouse(d.fg_warehouse || "");
    setLoaded(true);
  }, [existing.data, loaded, name, nav]);

  useEffect(() => {
    const d = bomDoc.data;
    if (!bom || !d || d.name !== bom) return;
    if (pickedBom.current === bom) return;
    if (pickedBom.current === "" && !isNew) {
      pickedBom.current = bom;
      return;
    }
    pickedBom.current = bom;
    if (qtyEdited.current) return;
    if (d.quantity) setQty(Number(d.quantity) || 1);
  }, [bom, bomDoc.data, isNew]);

  const whFilters = session.company
    ? [["company", "=", session.company], ["is_group", "=", 0]] as [string, string, string][]
    : undefined;

  const checks = useMemo(() => [
    { label: t("wo.col.bom"), ok: !!bom },
    { label: t("wo.col.qty"), ok: qty > 0 },
    { label: t("wo.col.start"), ok: !!startDate },
  ], [bom, qty, startDate]);
  const ready = checks.every((c) => c.ok);

  async function saveFn(andSubmit = false) {
    if (!ready) return;
    setBusy(true); setSaveError(null);
    try {
      const payload = {
        bom_no: bom, qty, planned_start_date: startDate,
        wip_warehouse: wipWarehouse || undefined,
        fg_warehouse: fgWarehouse || undefined,
        company: session.company,
      };
      let n: string;
      if (isNew) {
        const doc = (await create.createDoc(DT.workOrder, payload)) as { name: string };
        n = doc.name;
      } else {
        await update.updateDoc(DT.workOrder, name, payload);
        n = name;
      }
      if (andSubmit) await submitCall.call({ doc: { doctype: DT.workOrder, name: n } });
      nav(`/work-orders/${encodeURIComponent(n)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;

  const madeItem = bomDoc.data?.item_name || bomDoc.data?.item || "";

  return (
    <DocForm
      eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/work-orders")}>{t("wo.title")}</button>}
      title={isNew ? t("wo.new") : name}
      checks={checks}
      readyCaption={t("sr.readyCap")}
      alert={saveError ? <ErrorBox error={saveError} /> : null}
      actions={
        <FormActions
          onSave={() => void saveFn(false)}
          onSubmit={canSubmit ? () => void saveFn(true) : undefined}
          onDiscard={() => nav(isNew ? "/work-orders" : `/work-orders/${encodeURIComponent(name)}`)}
          busy={busy}
          ready={ready}
        />
      }
    >
      <Card num={1} title={t("wo.col.bom")}>
        <div className="grid2">
          <Field label={t("wo.col.bom")} required>
            <LinkField doctype={DT.bom} value={bom} onChange={(v) => { qtyEdited.current = false; setBom(v); }} placeholder={t("wo.bomPh")} />
            {madeItem ? <div className="iname">{madeItem}</div> : null}
          </Field>
          <Field label={t("wo.col.qty")} htmlFor="wo-qty">
            <input id="wo-qty" className="ctl" type="number" min={0.001} step={0.001} value={qty} onChange={(e) => { qtyEdited.current = true; setQty(parseNum(e.target.value)); }} />
          </Field>
          <Field label={t("wo.col.start")} htmlFor="wo-start">
            <input id="wo-start" className="ctl" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </Field>
          <Field label={t("wo.col.wip")}>
            <LinkField doctype={DT.warehouse} value={wipWarehouse} onChange={setWipWarehouse} placeholder={t("wo.warehousePh")} filters={whFilters as never} />
          </Field>
          <Field label={t("wo.col.fg")}>
            <LinkField doctype={DT.warehouse} value={fgWarehouse} onChange={setFgWarehouse} placeholder={t("wo.warehousePh")} filters={whFilters as never} />
          </Field>
        </div>
      </Card>
    </DocForm>
  );
}
