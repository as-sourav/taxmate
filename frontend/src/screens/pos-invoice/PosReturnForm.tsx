/**
 * POS Invoice return form.
 * Importers: App.tsx route /pos-invoices/:name/return.
 * API: taxmate.api.accounts.make_sales_return (reuse); taxmate.api.resource.insert; taxmate.api.workflow.submit.
 * Schema: return_against (Link: POS Invoice), is_return=1.
 * User: "Implement the plan… complete all the to-dos."
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, ReadRow } from "../../components/ui";
import { FormActions } from "../../components/form";

type Doc = {
  name: string;
  customer?: string;
  posting_date?: string;
  grand_total?: number;
  currency?: string;
  docstatus?: number;
};

export default function PosReturnForm() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading } = useDoc<Doc>(DT.posInvoice, name);
  const returnCall = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeSalesReturn);
  const submitCall = useFrappePostCall(METHOD.submit);
  const insert = useInsert();
  const [busy, setBusy] = useState(false);
  const [returnError, setReturnError] = useState<unknown>(null);
  const canSubmit = canSubmitSales(session.roles);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  if (data.docstatus !== 1) return <ErrorBox error={t("pos.errNotSubmitted")} />;

  async function handleReturn() {
    setBusy(true); setReturnError(null);
    try {
      const res = await returnCall.call({ source_name: name, doctype: DT.salesInvoice });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("pos.err.returnFailed"));
      const body: Record<string, unknown> = { ...(mapped as Record<string, unknown>), doctype: DT.posInvoice };
      delete body.name; delete body.__islocal; delete body.__unsaved;
      const created = await insert.createDoc(DT.posInvoice, body);
      const newName = (created as { name: string }).name;
      if (canSubmit) {
        await submitCall.call({ doc: { doctype: DT.posInvoice, name: newName } });
      }
      nav(`/pos-invoices/${encodeURIComponent(newName)}`);
    } catch (e) { setReturnError(e); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHead title={t("pos.return")} eyebrow={<button type="button" className="btn quiet" onClick={() => nav(`/pos-invoices/${encodeURIComponent(name)}`)}>{t("pos.title")}</button>} />
      {returnError && <ErrorBox error={returnError} />}
      <Card title={t("pos.return")}>
        <ReadRow k={t("pos.col.no")} v={data.name} />
        <ReadRow k={t("pos.col.customer")} v={data.customer || t("pos.walkIn")} />
        <ReadRow k={t("pos.col.date")} v={date(data.posting_date)} />
        <ReadRow k={t("pos.col.total")} v={money(data.grand_total)} />
      </Card>
      <FormActions
        onDiscard={() => nav(`/pos-invoices/${encodeURIComponent(name)}`)}
        onSave={handleReturn}
        saveLabel={t("pos.confirmReturn")}
        busy={busy}
      />
    </>
  );
}
