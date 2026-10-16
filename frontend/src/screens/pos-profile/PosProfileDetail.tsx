/**
 * POS Profile detail — read with minimal edit of warehouse + payments.
 * Importers: App.tsx route /pos-profiles/:name.
 * API: taxmate.api.resource.get/save on POS Profile.
 * Schema: name, company, warehouse, disabled, selling_price_list, taxes_and_charges,
 *   payments[mode_of_payment, default].
 * User: "Implement the plan… complete all the to-dos."
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useSave } from "../../lib/resource";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Field, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import LinkField from "../../components/LinkField";

type PaymentRow = { mode_of_payment?: string; default?: 0 | 1 };

type Doc = {
  name: string;
  company?: string;
  warehouse?: string;
  selling_price_list?: string;
  taxes_and_charges?: string;
  disabled?: 0 | 1;
  payments?: PaymentRow[];
};

export default function PosProfileDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.posProfile, name);
  const save = useSave();
  const [warehouse, setWarehouse] = useState("");
  const [priceList, setPriceList] = useState("");
  const [taxes, setTaxes] = useState("");
  const [disabled, setDisabled] = useState<0 | 1>(0);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    if (data) {
      setWarehouse(data.warehouse ?? "");
      setPriceList(data.selling_price_list ?? "");
      setTaxes(data.taxes_and_charges ?? "");
      setDisabled(data.disabled ? 1 : 0);
    }
  }, [data]);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  async function handleSave() {
    setSaving(true); setSaveError(null);
    try {
      await save.updateDoc(DT.posProfile, name, { warehouse, disabled, selling_price_list: priceList, taxes_and_charges: taxes });
      setEditing(false);
      mutate();
    } catch (e) { setSaveError(e); } finally { setSaving(false); }
  }

  return (
    <>
      <PageHead
        title={data.name}
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/pos-profiles")}>{t("posp.title")}</button>}
        actions={
          <>
            <DocHistory doctype={DT.posProfile} name={name} />
            {editing ? (
              <>
                <button className="btn" onClick={handleSave} disabled={saving}>{saving ? t("common.saving") : t("common.save")}</button>
                <button className="btn btn-ghost ml-2" onClick={() => setEditing(false)}>{t("common.cancel")}</button>
              </>
            ) : (
              <button className="btn btn-secondary" onClick={() => setEditing(true)}>{t("common.edit")}</button>
            )}
          </>
        }
      />
      {saveError && <ErrorBox error={saveError} />}
      <Card title={t("posp.title")}>
        <ReadRow k={t("posp.col.company")} v={data.company || "—"} />
        <ReadRow k={t("posp.col.status")} v={<Pill cls={data.disabled ? "p-cxl" : "p-done"}>{data.disabled ? t("common.disabled") : t("common.active")}</Pill>} />
        {editing ? (
          <>
            <Field label={t("posp.col.priceList")}>
              <LinkField doctype={DT.priceList} value={priceList} onChange={setPriceList} />
            </Field>
            <Field label={t("posp.col.taxes")}>
              <LinkField doctype={DT.taxTemplate} value={taxes} onChange={setTaxes} />
            </Field>
          </>
        ) : (
          <>
            <ReadRow k={t("posp.col.priceList")} v={data.selling_price_list || "—"} />
            <ReadRow k={t("posp.col.taxes")} v={data.taxes_and_charges || "—"} />
          </>
        )}
        {editing ? (
          <CheckField
            label={t("common.disabled")}
            hint={t("doc.offHint")}
            checked={!!disabled}
            onChange={(on) => setDisabled(on ? 1 : 0)}
          />
        ) : null}
        {editing ? (
          <Field label={t("posp.col.warehouse")}>
            <LinkField doctype={DT.warehouse} value={warehouse} onChange={setWarehouse} placeholder={t("posp.ph.warehouse")} />
          </Field>
        ) : (
          <ReadRow k={t("posp.col.warehouse")} v={data.warehouse || "—"} />
        )}
      </Card>
      {(data.payments ?? []).length > 0 && (
        <Card title={t("posp.col.payments")}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-start py-1 pr-3">{t("pos.col.mop")}</th>
                <th className="text-start py-1">{t("pos.col.default")}</th>
              </tr>
            </thead>
            <tbody>
              {(data.payments ?? []).map((p, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1 pr-3">{p.mode_of_payment || "—"}</td>
                  <td className="py-1">{p.default ? "✓" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
