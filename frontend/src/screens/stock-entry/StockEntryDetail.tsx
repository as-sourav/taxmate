/**
 * Stock Entry detail view. Read-only after submit.
 * Importers: App.tsx route /stock-entries/:name.
 * API: taxmate.api.resource.get on Stock Entry; taxmate.api.workflow.submit/cancel.
 * Schema: Stock Entry fields name, stock_entry_type, posting_date, company, docstatus, items[].
 * User: "Implement the plan as specified… complete all the to-dos."
 */
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";

type Line = {
  item_code?: string; item_name?: string; qty?: number; uom?: string;
  basic_rate?: number; valuation_rate?: number; amount?: number;
  s_warehouse?: string; t_warehouse?: string;
};

type Cost = { expense_account?: string; description?: string; amount?: number };

type Doc = {
  name: string;
  stock_entry_type?: string;
  posting_date?: string;
  company?: string;
  docstatus?: number;
  total_amount?: number;
  items?: Line[];
  additional_costs?: Cost[];
};

function sePill(ds?: number): string {
  if (ds === 2) return "p-cxl";
  if (ds === 1) return "p-done";
  return "p-draft";
}
function seLabel(ds?: number): string {
  if (ds === 2) return t("pay.status.Cancelled");
  if (ds === 1) return t("pay.status.Submitted");
  return t("pay.status.Draft");
}

export default function StockEntryDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.stockEntry, name, listPath: "/stock-entries" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.stockEntry, name);
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
  const cancelled = data.docstatus === 2;
  const writable = canWrite(session);
  const busy = submitCall.loading || cancelCall.loading || amendCall.loading;
  const total = data.total_amount
    ?? (data.items ?? []).reduce((s, l) => s + (Number(l.amount) || 0), 0);

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/stock-entries")}>
            {t("nav.stockEntries")}
          </button>
        }
        title={data.stock_entry_type || data.name}
        actions={
          <DetailActions
            doctype={DT.stockEntry}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={cancelled}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={writable}
            busy={busy || deleteAction.loading}
            onEdit={() => nav(`/stock-entries/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => {
              void submitCall.call({ doc: { doctype: DT.stockEntry, name } }).then(() => mutate()).catch(() => undefined);
            }}
            onDelete={deleteAction.onDelete}
            onCancel={() => {
              void cancelCall.call({ doctype: DT.stockEntry, name }).then(() => mutate()).catch(() => undefined);
            }}
            onAmend={() => {
              void amendCall.call({ doctype: DT.stockEntry, name }).then((res) => {
                const next = res?.message?.name;
                if (next) nav(`/stock-entries/${encodeURIComponent(next)}`);
                else mutate();
              }).catch(() => undefined);
            }}
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={sePill(data.docstatus)}>{seLabel(data.docstatus)}</Pill>
        </p>
      </PageHead>

      {(submitCall.error || cancelCall.error || amendCall.error) && (
        <ErrorBox error={submitCall.error || cancelCall.error || amendCall.error} />
      )}

      <FormLayout aside={
        <Card bodyClass="cbody">
          <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("se.summary")}</h2>
          <SumRow k={t("se.total")} v={money(total)} />
            {(data.additional_costs ?? []).length > 0 && (
              <SumRow k={t("se.totalCosts")} v={money((data.additional_costs ?? []).reduce((s, c) => s + (Number(c.amount) || 0), 0))} />
            )}
        </Card>
      }>
        <Card>
          <div className="fg">
            <ReadRow k={t("se.purpose")} v={data.stock_entry_type || "—"} />
            <ReadRow k={t("se.check.date")} v={date(data.posting_date)} />
            <ReadRow k={t("coa.company")} v={data.company || "—"} />
          </div>
        </Card>
        <Card title={t("se.items")}>
          {/* Read-only lines: no add, no remove, and collapse off — there is
              nothing to type here, so both warehouses stay on the card. */}
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
                key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                render: (l) => (
                  <>{qty(l.qty)}<div style={{ fontSize: 11, color: "var(--faint)" }}>{l.uom}</div></>
                ),
              },
              {
                key: "from", label: t("se.warehouse.from"),
                render: (l) => <>{l.s_warehouse || "—"}</>,
              },
              {
                key: "to", label: t("se.warehouse.to"),
                render: (l) => <>{l.t_warehouse || "—"}</>,
              },
              {
                key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                render: (l) => <>{money(l.amount)}</>,
              },
            ] as LineField<Line>[]}
          />
        </Card>
        {(data.additional_costs ?? []).length > 0 && (
          <Card title={t("se.costs")}>
            {/* No leading # column here, so no showIndex. */}
            <LineItems<Cost>
              rows={data.additional_costs ?? []}
              collapse={false}
              fields={[
                {
                  key: "account", label: t("se.costAccount"), slot: "title",
                  render: (c) => <>{c.expense_account || "—"}</>,
                },
                {
                  key: "description", label: t("se.costDesc"),
                  render: (c) => <>{c.description || "—"}</>,
                },
                {
                  key: "amount", label: t("se.costAmt"), slot: "primary", numeric: true,
                  render: (c) => <>{money(c.amount)}</>,
                },
              ] as LineField<Cost>[]}
            />
          </Card>
        )}
      </FormLayout>
    </>
  );
}
