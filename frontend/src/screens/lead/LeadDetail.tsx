/**
 * LeadDetail — Phase 21. Lead detail + convert to Customer.
 * Callers: App.tsx /leads/:name
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canWrite } from "../../lib/roles";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";

type Doc = { name: string; lead_name?: string; company_name?: string; email_id?: string; mobile_no?: string; status?: string; city?: string; country?: string };

function leadPill(status?: string): string {
  if (status === "Converted") return "p-done";
  if (status === "Do Not Contact" || status === "Lost Quotation") return "p-cxl";
  if (status === "Open" || status === "Replied") return "p-open";
  return "p-flat";
}

export default function LeadDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const writable = canWrite(session);
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.lead, name);
  const convertCall = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.convertLeadToCustomer);
  const create = useInsert();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  async function convertToCustomer() {
    setBusy(true); setActionError(null);
    try {
      const res = await convertCall.call({ lead_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("lead.err.convertFailed"));
      const body: Record<string, unknown> = { ...(mapped as Record<string, unknown>) };
      delete body.name; delete body.doctype; delete body.__islocal; delete body.__unsaved;
      const created = await create.createDoc(DT.customer, body);
      nav(`/customers/${encodeURIComponent((created as { name: string }).name)}`);
    } catch (err) { setActionError(err); }
    finally { setBusy(false); }
  }

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/leads")}>{t("lead.title")}</button>}
        title={data.lead_name || data.name}
        actions={<DocHistory doctype={DT.lead} name={name} />}
      >
        <Pill cls={leadPill(data.status)}>{data.status || "Open"}</Pill>
        {writable && data.status !== "Converted" && (
          <>
            <button className="btn ghost" onClick={() => nav(`/leads/${encodeURIComponent(name)}/edit`)}>{t("edit")}</button>
            <button className="btn" onClick={() => void convertToCustomer()} disabled={busy}>{t("lead.convert")}</button>
          </>
        )}
      </PageHead>
      {actionError ? <ErrorBox error={actionError} /> : null}
      <Card>
        <div className="fg">
          {data.company_name ? <ReadRow k={t("lead.col.company")} v={data.company_name} /> : null}
          {data.email_id ? <ReadRow k={t("lead.col.email")} v={data.email_id} /> : null}
          {data.mobile_no ? <ReadRow k={t("lead.col.mobile")} v={data.mobile_no} /> : null}
          {data.city ? <ReadRow k={t("lead.col.city")} v={`${data.city}${data.country ? `, ${data.country}` : ""}`} /> : null}
        </div>
      </Card>
    </>
  );
}
