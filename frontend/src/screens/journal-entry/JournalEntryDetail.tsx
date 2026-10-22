import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";

type Line = {
  account?: string;
  party_type?: string;
  party?: string;
  debit_in_account_currency?: number;
  credit_in_account_currency?: number;
  user_remark?: string;
  cost_center?: string;
};

type Doc = {
  name: string;
  posting_date?: string;
  voucher_type?: string;
  company?: string;
  user_remark?: string;
  total_debit?: number;
  total_credit?: number;
  docstatus?: 0 | 1 | 2;
  currency?: string;
  accounts?: Line[];
};

function jePill(ds?: number): string {
  if (ds === 0) return "p-draft";
  if (ds === 2) return "p-cxl";
  return "p-done";
}

export default function JournalEntryDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.journalEntry, name, listPath: "/journals" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.journalEntry, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.currency || session.currency || "";
  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const cancelled = data.docstatus === 2;
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const writable = canWrite(session);
  const busy = submitCall.loading || cancelCall.loading || amendCall.loading;
  const busyError = deleteAction.error || submitCall.error || cancelCall.error || amendCall.error;

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/journals")}>
            {t("nav.journals")}
          </button>
        }
        title={data.voucher_type || data.name}
        actions={
          <DetailActions
            doctype={DT.journalEntry}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={cancelled}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={writable}
            busy={busy || deleteAction.loading}
            onEdit={() => nav(`/journals/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.journalEntry, name } }).then(() => mutate())}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.journalEntry, name }).then(() => mutate())}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.journalEntry, name });
              const newName = res?.message?.name;
              if (newName) nav(`/journals/${encodeURIComponent(newName)}/edit`);
              else void mutate();
            }}
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={jePill(data.docstatus)}>
            {data.docstatus === 0 ? t("pay.status.Draft") : data.docstatus === 2 ? t("pay.status.Cancelled") : t("pay.status.Submitted")}
          </Pill>
        </p>
      </PageHead>

      {busyError && <ErrorBox error={busyError} />}

      <FormLayout
        aside={
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("je.totals")}</h2>
            <SumRow k={t("je.col.debit")} v={money(data.total_debit)} currency={cur} />
            <SumRow k={t("je.col.credit")} v={money(data.total_credit)} cls="rule total" currency={cur} />
          </Card>
        }
      >
        <Card>
          <div className="fg">
            <ReadRow k={t("inv.col.date")} v={date(data.posting_date)} />
            <ReadRow k={t("je.col.type")} v={data.voucher_type || "—"} />
            <ReadRow k={t("je.col.remark")} v={data.user_remark || "—"} />
          </div>
        </Card>
        <Card title={t("je.accounts")}>
          {/* Read-only: a posted journal's legs cannot be added or removed here.
              The account names the row and the two figures are the point of it,
              so debit and credit take the card face; cost centre and party sit
              below, still visible with collapse off. */}
          <LineItems<Line>
            rows={data.accounts ?? []}
            collapse={false}
            fields={[
              {
                key: "account", label: t("je.account"), slot: "title",
                render: (row) => <>{row.account}</>,
              },
              {
                key: "costCenter", label: t("je.costCenter"),
                render: (row) => <>{row.cost_center || "—"}</>,
              },
              {
                key: "party", label: t("je.party"),
                render: (row) => <>{row.party || "—"}</>,
              },
              {
                key: "debit", label: t("je.col.debit"), slot: "primary", numeric: true,
                render: (row) => <>{money(row.debit_in_account_currency)}</>,
              },
              {
                key: "credit", label: t("je.col.credit"), slot: "primary", numeric: true, tdClass: "tot",
                render: (row) => <>{money(row.credit_in_account_currency)}</>,
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
