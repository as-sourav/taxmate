/**
 * PeriodClosingDetail — Phase 5.
 * Callers: App.tsx /period-closing/:name
 * API: taxmate.api.resource.get on "Period Closing Voucher"
 */
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { METHOD } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite } from "../../lib/roles";
import { date } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DetailActions from "../../components/DetailActions";

type Doc = {
  name: string;
  company?: string;
  transaction_date?: string;
  period_start_date?: string;
  period_end_date?: string;
  fiscal_year?: string;
  closing_account_head?: string;
  remarks?: string;
  docstatus?: number;
};

export default function PeriodClosingDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>("Period Closing Voucher", name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const st = data.docstatus === 1 ? "Submitted" : data.docstatus === 2 ? "Cancelled" : "Draft";

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/period-closing")}>
            {t("pcv.title")}
          </button>
        }
        title={data.name}
        actions={
          <DetailActions
            doctype="Period Closing Voucher"
            name={name}
            draft={data.docstatus === 0}
            submitted={data.docstatus === 1}
            cancelled={data.docstatus === 2}
            canWrite={canWrite(session)}
            canSubmit={canSubmitSales(session.roles)}
            canCancel={canCancelSales(session.roles)}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading}
            onSubmit={() => {
              void submitCall.call({ doc: { doctype: "Period Closing Voucher", name } }).then(() => mutate()).catch(() => undefined);
            }}
            onCancel={() => {
              void cancelCall.call({ doctype: "Period Closing Voucher", name }).then(() => mutate()).catch(() => undefined);
            }}
            onAmend={() => {
              void amendCall.call({ doctype: "Period Closing Voucher", name }).then((res) => {
                const next = res?.message?.name;
                if (next) nav(`/period-closing/${encodeURIComponent(next)}`);
                else mutate();
              }).catch(() => undefined);
            }}
          />
        }
      >
        <Pill cls={data.docstatus === 1 ? "p-sub" : data.docstatus === 2 ? "p-cancel" : "p-draft"}>
          {t(`status.${st}`)}
        </Pill>
      </PageHead>
      {(submitCall.error || cancelCall.error || amendCall.error) && (
        <ErrorBox error={submitCall.error || cancelCall.error || amendCall.error} />
      )}
      <Card>
        <div className="fg">
          <ReadRow k={t("pcv.col.date")} v={date(data.transaction_date)} />
          <ReadRow k={t("pcv.col.fiscalYear")} v={data.fiscal_year || "—"} />
          <ReadRow
            k={t("pcv.col.period")}
            v={
              data.period_start_date && data.period_end_date
                ? `${date(data.period_start_date)} – ${date(data.period_end_date)}`
                : "—"
            }
          />
          <ReadRow k={t("pcv.col.account")} v={data.closing_account_head || "—"} />
          {data.remarks && <ReadRow k={t("je.col.remark")} v={data.remarks} />}
        </div>
      </Card>
    </>
  );
}
