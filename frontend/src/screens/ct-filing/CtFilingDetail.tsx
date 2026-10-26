/**
 * Corporate tax filing detail.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DT } from "../../lib/frappe";
import { useDoc, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, CheckField, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { PrintLangButtons } from "../../components/PrintLangButtons";
import DocHistory from "../../components/DocHistory";
import { FormLayout } from "../../components/form";
import LineItems, { type LineField } from "../../components/LineItems";

type Adj = { name?: string; adjustment_type?: string; category?: string; amount?: number; notes?: string };
type Doc = {
  name: string; company?: string; period_start?: string; period_end?: string;
  filing_due_date?: string; deadline_status?: string; company_trn?: string;
  revenue?: number; expenses?: number; accounting_profit?: number; taxable_profit?: number;
  tax_payable?: number; generated_on?: string; docstatus?: number; adjustments?: Adj[];
  elect_small_business_relief?: number; elect_qfzp?: number;
};

function deadlinePill(status?: string): string {
  if (status === "Overdue") return "p-overdue";
  if (status === "Due") return "p-warn";
  if (status === "Filed") return "p-done";
  return "p-open";
}

export default function CtFilingDetail() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.ctFiling, name);
  const update = useSave();
  const [sbr, setSbr] = useState<0 | 1 | null>(null);
  const [qfzp, setQfzp] = useState<0 | 1 | null>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;
  const cur = session.currency || "";
  const rows = data.adjustments ?? [];
  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/ct-filings")}>{t("nav.ct")}</button>}
        title={data.name}
        actions={
          <>
            <DocHistory doctype={DT.ctFiling} name={name} />
            <PrintLangButtons doctype={DT.ctFiling} name={name} format="UAE CT Worksheet" />
            <button type="button" className="btn" disabled={update.loading} onClick={() => {
            setSaveError(null);
            void update.updateDoc(DT.ctFiling, name, {
              elect_small_business_relief: sbr ?? (data.elect_small_business_relief ? 1 : 0),
              elect_qfzp: qfzp ?? (data.elect_qfzp ? 1 : 0),
            }).then(() => mutate()).catch(setSaveError);
          }}>{t("common.save")}</button>
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <Pill cls={deadlinePill(data.deadline_status)}>{data.deadline_status || "—"}</Pill>
        </p>
      </PageHead>
      {saveError ? <ErrorBox error={saveError} /> : null}
      <FormLayout aside={
        <Card title={t("ct.summary")}>
          <SumRow k={t("ct.col.tax")} v={`${cur} ${money(data.tax_payable)}`} />
          <ReadRow k={t("ct.col.profit")} v={`${cur} ${money(data.taxable_profit)}`} />
          <ReadRow k={t("v201.col.due")} v={date(data.filing_due_date)} />
          <ReadRow k={t("v201.generated")} v={data.generated_on ? date(data.generated_on) : "—"} />
        </Card>
      }>
        <Card>
          <div className="fg">
            <ReadRow k={t("coa.company")} v={data.company || "—"} />
            <ReadRow k={t("v201.col.period")} v={`${date(data.period_start)} – ${date(data.period_end)}`} />
            <ReadRow k={t("v201.trn")} v={data.company_trn || "—"} />
            <ReadRow k={t("ct.revenue")} v={money(data.revenue)} />
            <ReadRow k={t("ct.expenses")} v={money(data.expenses)} />
            <ReadRow k={t("ct.accounting")} v={money(data.accounting_profit)} />
            <CheckField label={t("ct.sbr")} checked={!!(sbr ?? data.elect_small_business_relief)} onChange={(on) => setSbr(on ? 1 : 0)} />
            <CheckField label={t("ct.qfzp")} checked={!!(qfzp ?? data.elect_qfzp)} onChange={(on) => setQfzp(on ? 1 : 0)} />
          </div>
        </Card>
        {rows.length > 0 ? (
          <Card title={t("ct.adjustments")}>
            {/* Read-only adjustments: nothing to add or remove, and on a phone
                every column stays visible rather than hiding behind "More". */}
            <LineItems<Adj>
              rows={rows}
              collapse={false}
              fields={[
                {
                  key: "type", label: t("ct.adjType"), slot: "title",
                  render: (r) => <>{r.adjustment_type || "—"}</>,
                },
                {
                  key: "category", label: t("ct.adjCat"),
                  render: (r) => <>{r.category || r.notes || "—"}</>,
                },
                {
                  key: "amount", label: t("v201.amount"), slot: "primary", numeric: true,
                  render: (r) => <>{money(r.amount)}</>,
                },
              ] as LineField<Adj>[]}
            />
          </Card>
        ) : null}
      </FormLayout>
    </>
  );
}
