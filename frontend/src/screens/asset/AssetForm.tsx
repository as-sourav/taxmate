/**
 * Asset form — new and edit.
 * Importers: App.tsx routes /assets/new and /assets/:name/edit.
 * API: taxmate.api.resource.insert / save.
 * Schema: asset_name (Data), item_code (Link), company (Link),
 *   asset_category (Link), purchase_date (Date), purchase_amount (Currency),
 *   available_for_use_date (Date), calculate_depreciation (Check).
 * User: "Implement the plan… complete all the to-dos."
 */
import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { parseNum, toIsoDate } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormActions, FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";

type Doc = {
  name: string;
  asset_name?: string;
  item_code?: string;
  company?: string;
  asset_category?: string;
  purchase_date?: string;
  available_for_use_date?: string;
  purchase_amount?: number;
  calculate_depreciation?: 0 | 1;
  location?: string;
  finance_books?: { depreciation_method?: string; total_number_of_depreciations?: number; frequency_of_depreciation?: number }[];
  docstatus?: number;
};

export default function AssetForm() {
  const { name = "new" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";
  const existing = useDoc<Doc>(DT.asset, isNew ? undefined : name, isNew ? null : name, {
    isPaused: () => isNew,
  });

  const [assetName, setAssetName] = useState("");
  const [itemCode, setItemCode] = useState("");
  const [company, setCompany] = useState(session.company ?? "");
  const [assetCategory, setAssetCategory] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(toIsoDate(new Date()));
  const [availDate, setAvailDate] = useState(toIsoDate(new Date()));
  const [purchaseAmount, setPurchaseAmount] = useState(0);
  const [calcDepr, setCalcDepr] = useState(false);
  const [location, setLocation] = useState("");
  const [method, setMethod] = useState("Straight Line");
  const [life, setLife] = useState(0);
  const [frequency, setFrequency] = useState(12);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const insert = useInsert();
  const save = useSave();

  useEffect(() => {
    if (!isNew && existing.data) {
      const d = existing.data;
      setAssetName(d.asset_name ?? "");
      setItemCode(d.item_code ?? "");
      setCompany(d.company ?? "");
      setAssetCategory(d.asset_category ?? "");
      setPurchaseDate(d.purchase_date ?? toIsoDate(new Date()));
      setAvailDate(d.available_for_use_date ?? toIsoDate(new Date()));
      setPurchaseAmount(d.purchase_amount ?? 0);
      setCalcDepr(!!d.calculate_depreciation);
      setLocation(d.location ?? "");
      const book = d.finance_books?.[0];
      setMethod(book?.depreciation_method || "Straight Line");
      setLife(book?.total_number_of_depreciations || 0);
      setFrequency(book?.frequency_of_depreciation || 12);
    }
  }, [isNew, existing.data]);

  if (!session.user) return <Navigate to="/" />;
  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!isNew && existing.data?.docstatus === 1) return <Navigate to={`/assets/${encodeURIComponent(name)}`} />;

  async function handleSave() {
    setSaving(true); setSaveError(null);
    try {
      const body: Record<string, unknown> = {
        doctype: DT.asset,
        asset_name: assetName,
        ...(itemCode ? { item_code: itemCode } : {}),
        company,
        asset_category: assetCategory,
        purchase_date: purchaseDate,
        available_for_use_date: availDate,
        purchase_amount: purchaseAmount,
        calculate_depreciation: calcDepr ? 1 : 0,
        location: location || undefined,
        finance_books: calcDepr ? [{
          depreciation_method: method,
          total_number_of_depreciations: life,
          frequency_of_depreciation: frequency,
        }] : undefined,
      };
      if (isNew) {
        const created = await insert.createDoc(DT.asset, body);
        nav(`/assets/${encodeURIComponent((created as { name: string }).name)}`);
      } else {
        await save.updateDoc(DT.asset, name, body);
        nav(`/assets/${encodeURIComponent(name)}`);
      }
    } catch (e) { setSaveError(e); } finally { setSaving(false); }
  }

  return (
    <>
      <PageHead title={isNew ? t("ast.new") : name} eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/assets")}>{t("ast.title")}</button>} />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout>
        <Card title={t("ast.title")}>
          <Field label={t("ast.col.name")}>
            <input className="inp" value={assetName} onChange={(e) => setAssetName(e.target.value)} placeholder={t("ast.namePh")} />
          </Field>
          <Field label={t("ast.col.item")}>
            <LinkField doctype={DT.item} value={itemCode} onChange={setItemCode} placeholder={t("asset.ph.item")} />
          </Field>
          <Field label={t("ast.col.category")}>
            <LinkField doctype={DT.assetCategory} value={assetCategory} onChange={setAssetCategory} placeholder={t("asset.ph.category")} />
          </Field>
          <Field label={t("ast.location")} required>
            <LinkField doctype="Location" value={location} onChange={setLocation} />
          </Field>
          <Field label={t("ast.col.company")}>
            <LinkField doctype="Company" value={company} onChange={setCompany} placeholder={t("asset.ph.company")} />
          </Field>
          <Field label={t("ast.col.purchaseDate")}>
            <input className="inp" type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
          </Field>
          <Field label={t("ast.col.availDate")}>
            <input className="inp" type="date" value={availDate} onChange={(e) => setAvailDate(e.target.value)} />
          </Field>
          <Field label={t("ast.col.purchaseAmount")}>
            <input className="inp" type="number" min={0} step={0.01} value={purchaseAmount}
              onChange={(e) => setPurchaseAmount(parseNum(e.target.value))} />
          </Field>
          <Field label="">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={calcDepr} onChange={(e) => setCalcDepr(e.target.checked)} />
              {t("ast.calcDepr")}
            </label>
          </Field>
          {calcDepr && (
            <>
              <Field label={t("ast.method")}>
                <select className="inp" value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="Straight Line">{t("asset.dep.straightLine")}</option>
                  <option value="Double Declining Balance">{t("asset.dep.doubleDeclining")}</option>
                  <option value="Written Down Value">{t("asset.dep.wdv")}</option>
                  <option value="Manual">{t("asset.dep.manual")}</option>
                </select>
              </Field>
              <Field label={t("ast.life")}>
                <input className="inp" type="number" min={0} value={life} onChange={(e) => setLife(parseNum(e.target.value))} />
              </Field>
              <Field label={t("ast.frequency")}>
                <input className="inp" type="number" min={1} value={frequency} onChange={(e) => setFrequency(parseNum(e.target.value))} />
              </Field>
            </>
          )}
        </Card>
        <FormActions
          onDiscard={() => nav(isNew ? "/assets" : `/assets/${encodeURIComponent(name)}`)}
          onSave={handleSave}
          busy={saving}
        />
      </FormLayout>
    </>
  );
}
