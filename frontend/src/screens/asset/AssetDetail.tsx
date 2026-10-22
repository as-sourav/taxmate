/**
 * Asset detail — view with submit action and read-only depreciation schedule.
 * Importers: App.tsx route /assets/:name.
 * API: taxmate.api.resource.get on Asset; taxmate.api.workflow.submit/cancel.
 * Schema: asset_name, asset_category, company, purchase_date, purchase_amount,
 *   available_for_use_date, calculate_depreciation, docstatus,
 *   finance_books (Table — depreciation schedule, read-only).
 * User: "Implement the plan… complete all the to-dos."
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales, canCancelSales } from "../../lib/roles";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, ReadRow } from "../../components/ui";
import DetailActions from "../../components/DetailActions";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";

type FinanceBook = {
  finance_book?: string;
  depreciation_method?: string;
  total_number_of_depreciations?: number;
  frequency_of_depreciation?: number;
  value_after_depreciation?: number;
};

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
  is_fully_depreciated?: 0 | 1;
  docstatus?: number;
  finance_books?: FinanceBook[];
};

export default function AssetDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.asset, name, listPath: "/assets" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.asset, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;

  async function handleSubmit() {
    setBusy(true); setActionError(null);
    try {
      await submitCall.call({ doc: { doctype: DT.asset, name } });
      mutate();
    } catch (e) { setActionError(e); } finally { setBusy(false); }
  }

  async function handleCancel() {
    setBusy(true); setActionError(null);
    try {
      await cancelCall.call({ doctype: DT.asset, name });
      mutate();
    } catch (e) { setActionError(e); } finally { setBusy(false); }
  }

  async function handleAmend() {
    setBusy(true); setActionError(null);
    try {
      const res = await amendCall.call({ doctype: DT.asset, name });
      const next = res?.message?.name;
      if (next) nav(`/assets/${encodeURIComponent(next)}`);
      else mutate();
    } catch (e) { setActionError(e); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHead
        title={data.asset_name || data.name}
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/assets")}>{t("ast.title")}</button>}
        actions={
          <DetailActions
            doctype={DT.asset}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={canSubmit}
            onEdit={draft ? () => nav(`/assets/${encodeURIComponent(name)}/edit`) : undefined}
            onSubmit={handleSubmit}
            onDelete={deleteAction.onDelete}
            onCancel={handleCancel}
            onAmend={handleAmend}
            busy={busy || deleteAction.loading}
          />
        }
      />
      {actionError && <ErrorBox error={actionError} />}
      <Card title={t("ast.title")}>
        <ReadRow k={t("ast.col.category")} v={data.asset_category || "—"} />
        <ReadRow k={t("ast.col.company")} v={data.company || "—"} />
        <ReadRow k={t("ast.col.purchaseDate")} v={date(data.purchase_date)} />
        <ReadRow k={t("ast.col.availDate")} v={date(data.available_for_use_date)} />
        <ReadRow k={t("ast.col.purchaseAmount")} v={money(data.purchase_amount)} />
        {data.item_code && <ReadRow k={t("ast.col.item")} v={data.item_code} />}
      </Card>
      {data.calculate_depreciation && (data.finance_books ?? []).length > 0 && (
        <Card title={t("ast.deprSchedule")} >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-start py-1 pr-3">{t("ast.col.deprMethod")}</th>
                <th className="text-end py-1 pr-3">{t("ast.col.deprCount")}</th>
                <th className="text-end py-1">{t("ast.col.valueAfter")}</th>
              </tr>
            </thead>
            <tbody>
              {(data.finance_books ?? []).map((fb, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1 pr-3">{fb.depreciation_method || "—"}</td>
                  <td className="text-end py-1 pr-3">{fb.total_number_of_depreciations ?? "—"}</td>
                  <td className="text-end py-1">{money(fb.value_after_depreciation)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
