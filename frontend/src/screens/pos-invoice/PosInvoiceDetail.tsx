/**
 * POS Invoice detail.
 * Callers: App.tsx route /pos-invoices/:name. The list opens this path.
 * API: taxmate.api.resource.get on POS Invoice; taxmate.api.workflow.submit,
 *   cancel, and amend. Return opens the existing /return route.
 * Schema: name, customer, pos_profile, posting_date, vat_emirate, grand_total,
 *   currency, docstatus, is_return, items, payments.
 * User: "Using frappe skills and anthropic skills, ensure that all our gaps are fixed and issues are fixed. Check buttons such as cancel, amend, and others - whether they work in all places or not. Review the complete frontend and make it robust- use gstack and production grade skills and development"
 */
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { date, money, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";

type Line = { item_code?: string; qty?: number; rate?: number; amount?: number };
type Payment = { mode_of_payment?: string; amount?: number };
type Doc = {
  name: string;
  customer?: string;
  pos_profile?: string;
  posting_date?: string;
  vat_emirate?: string;
  grand_total?: number;
  currency?: string;
  docstatus?: number;
  is_return?: 0 | 1;
  items?: Line[];
  payments?: Payment[];
};

export default function PosInvoiceDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const deleteAction = useDeleteDraftAction({ doctype: DT.posInvoice, name, listPath: "/pos-invoices" });
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.posInvoice, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const cancelled = data.docstatus === 2;
  const pill = data.is_return || cancelled ? "p-cxl" : submitted ? "p-done" : "p-draft";
  const label = data.is_return
    ? t("inv.status.Return")
    : cancelled
      ? t("inv.status.Cancelled")
      : submitted
        ? t("pos.statusPaid")
        : t("inv.status.Draft");

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/pos-invoices")}>{t("pos.title")}</button>}
        title={data.name}
        actions={
          <DetailActions
            doctype={DT.posInvoice}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={cancelled}
            canWrite={canWrite(session)}
            canSubmit={canSubmitSales(session.roles)}
            canCancel={canCancelSales(session.roles)}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || deleteAction.loading}
            onEdit={() => nav(`/pos-invoices/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => {
              void submitCall.call({ doc: { doctype: DT.posInvoice, name } }).then(() => mutate()).catch(() => undefined);
            }}
            onDelete={deleteAction.onDelete}
            onCancel={() => {
              void cancelCall.call({ doctype: DT.posInvoice, name }).then(() => mutate()).catch(() => undefined);
            }}
            onAmend={() => {
              void amendCall.call({ doctype: DT.posInvoice, name }).then((res) => {
                const next = res?.message?.name;
                if (next) nav(`/pos-invoices/${encodeURIComponent(next)}`);
                else mutate();
              }).catch(() => undefined);
            }}
            extra={submitted && !data.is_return ? (
              <button type="button" className="btn ghost" onClick={() => nav(`/pos-invoices/${encodeURIComponent(name)}/return`)}>
                {t("pos.return")}
              </button>
            ) : null}
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <Pill cls={pill}>{label}</Pill>
        </p>
      </PageHead>
      {(submitCall.error || cancelCall.error || amendCall.error || deleteAction.error) && (
        <ErrorBox error={submitCall.error || cancelCall.error || amendCall.error || deleteAction.error} />
      )}
      <Card>
        <div className="fg">
          <ReadRow k={t("pos.col.customer")} v={data.customer || t("pos.walkIn")} />
          <ReadRow k={t("pos.col.date")} v={date(data.posting_date)} />
          <ReadRow k={t("pos.col.profile")} v={data.pos_profile || "—"} />
          <ReadRow k={t("pos.col.emirate")} v={data.vat_emirate || "—"} />
          <ReadRow k={t("pos.col.total")} v={money(data.grand_total)} />
        </div>
      </Card>
      <Card title={t("pos.col.items")}>
        <LineItems<Line>
          rows={data.items ?? []}
          collapse={false}
          fields={[
            { key: "item", label: t("pos.col.items"), slot: "title", render: (r) => <>{r.item_code || "—"}</> },
            { key: "qty", label: t("bom.col.qty"), slot: "primary", numeric: true, render: (r) => <>{qty(r.qty)}</> },
            { key: "rate", label: t("pos.col.amount"), numeric: true, render: (r) => <>{money(r.rate)}</> },
          ] as LineField<Line>[]}
        />
      </Card>
      <Card title={t("pos.col.payments")}>
        <LineItems<Payment>
          rows={data.payments ?? []}
          collapse={false}
          fields={[
            { key: "mop", label: t("pos.col.mop"), slot: "title", render: (r) => <>{r.mode_of_payment || "—"}</> },
            { key: "amount", label: t("pos.col.amount"), slot: "primary", numeric: true, render: (r) => <>{money(r.amount)}</> },
          ] as LineField<Payment>[]}
        />
      </Card>
    </>
  );
}
