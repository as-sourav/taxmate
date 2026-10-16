/**
 * Loyalty Program detail.
 * Importers: App.tsx route /loyalty-programs/:name.
 * API: taxmate.api.resource.get on Loyalty Program.
 * Schema: name, loyalty_program_type, company, from_date, to_date, conversion_factor.
 * User: "Implement the plan… complete all the to-dos."
 */
import { useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc } from "../../lib/resource";
import { date } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, ReadRow } from "../../components/ui";
import DetailActions from "../../components/DetailActions";

type Doc = {
  name: string;
  loyalty_program_type?: string;
  company?: string;
  from_date?: string;
  to_date?: string;
  conversion_factor?: number;
  expiry_duration?: number;
};

export default function LoyaltyProgramDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.loyaltyProgram, name);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  return (
    <>
      <PageHead
        title={data.name}
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/loyalty-programs")}>{t("lp.title")}</button>}
        actions={
          <DetailActions
            doctype={DT.loyaltyProgram}
            name={name}
            draft={true}
            submitted={false}
            canSubmit={false}
            canCancel={false}
            canWrite={true}
            onEdit={() => nav(`/loyalty-programs/${encodeURIComponent(name)}/edit`)}
            busy={false}
          />
        }
      />
      <Card title={t("lp.title")}>
        <ReadRow k={t("lp.col.type")} v={data.loyalty_program_type || "—"} />
        <ReadRow k={t("lp.col.company")} v={data.company || "—"} />
        <ReadRow k={t("lp.col.from")} v={date(data.from_date)} />
        <ReadRow k={t("lp.col.to")} v={date(data.to_date)} />
        <ReadRow k={t("lp.col.convFactor")} v={String(data.conversion_factor ?? 1)} />
        {(data.expiry_duration ?? 0) > 0 && (
          <ReadRow k={t("lp.col.expiry")} v={t("lp.expiryDays").replace("{n}", String(data.expiry_duration))} />
        )}
      </Card>
    </>
  );
}
