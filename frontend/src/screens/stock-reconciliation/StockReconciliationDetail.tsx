/**
 * Stock Reconciliation detail. Importers: App.tsx. API: taxmate.api.resource.get on Stock Reconciliation.
 * Schema: name, purpose, posting_date, docstatus, items[{item_code,warehouse,qty,valuation_rate}].
 * User: "Implement the plan as specified… complete all the to-dos."
 */
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { confirmCancel } from "../../lib/workflow";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import { FormLayout } from "../../components/form";
import LineItems, { type LineField } from "../../components/LineItems";

type Line = { item_code?: string; item_name?: string; warehouse?: string; qty?: number; valuation_rate?: number; };
type Doc = { name: string; purpose?: string; posting_date?: string; docstatus?: number; difference_account?: string; items?: Line[]; };

export default function StockReconciliationDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.stockReconciliation, name, listPath: "/stock-reconciliations" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.stockReconciliation, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const pill = data.docstatus === 2 ? "p-cxl" : data.docstatus === 1 ? "p-done" : "p-draft";
  const label = data.docstatus === 2 ? t("pay.status.Cancelled") : data.docstatus === 1 ? t("pay.status.Submitted") : t("pay.status.Draft");

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/stock-reconciliations")}>
            {t("nav.stockReconciliations")}
          </button>
        }
        title={data.purpose || data.name}
        actions={
          <>
            <DocHistory doctype={DT.stockReconciliation} name={name} />
            {draft && (
              <button type="button" className="btn ghost"
                onClick={() => nav(`/stock-reconciliations/${encodeURIComponent(name)}/edit`)}>
                {t("inv.edit")}
              </button>
            )}

            {draft && (
              <button type="button" className="btn quiet" disabled={deleteAction.loading}
                onClick={deleteAction.onDelete}>
                {deleteAction.loading ? t("soc.saving") : t("inv.delete")}
              </button>
            )}
            {draft && canSubmit && (
              <button type="button" className="btn" disabled={submitCall.loading}
                onClick={() => void submitCall.call({ doc: { doctype: DT.stockReconciliation, name } }).then(() => mutate()).catch(() => undefined)}>
                {t("inv.submit")}
              </button>
            )}
            {submitted && canCancel && (
              <button type="button" className="btn quiet" disabled={cancelCall.loading}
                onClick={() => {
                  if (!confirmCancel(name)) return;
                  void cancelCall.call({ doctype: DT.stockReconciliation, name }).then(() => mutate()).catch(() => undefined);
                }}>
                {t("inv.cancel")}
              </button>
            )}
            {data.docstatus === 2 && canSubmit && (
              <button type="button" className="btn ghost" disabled={amendCall.loading}
                onClick={() => void amendCall.call({ doctype: DT.stockReconciliation, name }).then((res) => {
                  const next = res?.message?.name;
                  if (next) nav(`/stock-reconciliations/${encodeURIComponent(next)}`);
                  else mutate();
                }).catch(() => undefined)}>
                {amendCall.loading ? t("soc.saving") : t("inv.amend")}
              </button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={pill}>{label}</Pill>
        </p>
      </PageHead>

      {(submitCall.error || cancelCall.error || amendCall.error) && (
        <ErrorBox error={submitCall.error || cancelCall.error || amendCall.error} />
      )}

      <FormLayout>
        <Card>
          <div className="fg">
            <ReadRow k={t("sr.purpose")} v={data.purpose || "—"} />
            <ReadRow k={t("sr.check.date")} v={date(data.posting_date)} />
            {data.difference_account && (
              <ReadRow k={t("sr.differenceAccount")} v={data.difference_account} />
            )}
          </div>
        </Card>
        <Card title={t("sr.items")}>
          {/* Read-only: no add or remove, and collapse off so the warehouse
              and the valuation rate are both on the card. */}
          <LineItems<Line>
            rows={data.items ?? []}
            showIndex
            collapse={false}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title",
                render: (l) => (
                  <>
                    <div className="icode">{l.item_code}</div>
                    <div className="iname">{l.item_name}</div>
                  </>
                ),
              },
              {
                key: "warehouse", label: t("sr.warehouse"),
                render: (l) => <>{l.warehouse || "—"}</>,
              },
              {
                key: "qty", label: t("sr.qty"), slot: "primary", numeric: true,
                render: (l) => <>{qty(l.qty)}</>,
              },
              {
                key: "rate", label: t("sr.rate"), slot: "primary", numeric: true,
                render: (l) => <>{money(l.valuation_rate)}</>,
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
