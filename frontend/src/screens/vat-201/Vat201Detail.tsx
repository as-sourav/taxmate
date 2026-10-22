/**
 * VAT 201 filing detail. Catalog get, generate_vat_201, workflow.submit.
 */
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales } from "../../lib/roles";
import { confirmCancel } from "../../lib/workflow";
import { date, money } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import { FormLayout } from "../../components/form";
import LineItems, { type LineField } from "../../components/LineItems";

type Box = {
  name?: string;
  box_no?: string;
  legend?: string;
  amount?: number;
  vat_amount?: number;
  is_subtotal?: number;
};

type Doc = {
  name: string;
  company?: string;
  period_start?: string;
  period_end?: string;
  filing_due_date?: string;
  status?: string;
  deadline_status?: string;
  company_trn?: string;
  vat_group?: string;
  tax_currency?: string;
  net_vat_due?: number;
  generated_on?: string;
  filed_on?: string;
  filed_by?: string;
  notes?: string;
  docstatus?: 0 | 1 | 2;
  boxes?: Box[];
};

function statusPill(status?: string): string {
  if (status === "Filed") return "p-done";
  if (status === "Reviewed") return "p-open";
  return "p-draft";
}

function deadlinePill(status?: string): string {
  if (status === "Overdue") return "p-overdue";
  if (status === "Due") return "p-warn";
  if (status === "Filed") return "p-done";
  return "p-open";
}

export default function Vat201Detail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.vat201, name, listPath: "/vat-201" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.vat201, name);
  const generate = useFrappePostCall(METHOD.generateVat201);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.tax_currency || session.currency || "";
  const draft = data.docstatus === 0;
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);
  const boxes = data.boxes ?? [];
  const busyError = generate.error || submitCall.error || cancelCall.error || amendCall.error;

  async function regenerate() {
    await generate.call({ name });
    await mutate();
  }

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/vat-201")}>
            {t("nav.vat201")}
          </button>
        }
        title={data.name}
        actions={
          <>
            <DocHistory doctype={DT.vat201} name={name} />
            {draft && (
              <button type="button" className="btn ghost" disabled={generate.loading}
                onClick={() => void regenerate()}>
                {generate.loading ? t("soc.saving") : t("v201.generate")}
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
                onClick={() => void submitCall.call({ doc: { doctype: DT.vat201, name } }).then(() => mutate()).catch(() => undefined)}>
                {t("inv.submit")}
              </button>
            )}
            {data.docstatus === 1 && canCancel && (
              <button type="button" className="btn quiet" disabled={cancelCall.loading}
                onClick={() => {
                  if (!confirmCancel(name)) return;
                  void cancelCall.call({ doctype: DT.vat201, name }).then(() => mutate()).catch(() => undefined);
                }}>
                {t("inv.cancel")}
              </button>
            )}
            {data.docstatus === 2 && canSubmit && (
              <button type="button" className="btn ghost" disabled={amendCall.loading}
                onClick={() => void amendCall.call({ doctype: DT.vat201, name }).then((res) => {
                  const next = res?.message?.name;
                  if (next) nav(`/vat-201/${encodeURIComponent(next)}`);
                  else mutate();
                }).catch(() => undefined)}>
                {amendCall.loading ? t("soc.saving") : t("inv.amend")}
              </button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <Pill cls={statusPill(data.status)}>{data.status ? t(`v201.status.${data.status}`) : "—"}</Pill>
          <Pill cls={deadlinePill(data.deadline_status)}>{data.deadline_status || "—"}</Pill>
        </p>
      </PageHead>
      {busyError && <ErrorBox error={busyError} />}
      <FormLayout
        aside={
          <Card title={t("v201.summary")}>
            <SumRow k={t("v201.col.net")} v={`${cur} ${money(data.net_vat_due)}`} />
            <ReadRow k={t("v201.col.due")} v={date(data.filing_due_date)} />
            <ReadRow k={t("v201.generated")} v={data.generated_on ? date(data.generated_on) : "—"} />
            <ReadRow k={t("v201.filedOn")} v={data.filed_on ? date(data.filed_on) : "—"} />
            <ReadRow k={t("v201.filedBy")} v={data.filed_by || "—"} />
          </Card>
        }
      >
        <Card>
          <div className="fg">
            <ReadRow k={t("coa.company")} v={data.company || "—"} />
            <ReadRow k={t("v201.col.period")} v={`${date(data.period_start)} – ${date(data.period_end)}`} />
            <ReadRow k={t("v201.trn")} v={data.company_trn || "—"} />
            <ReadRow k={t("v201.group")} v={data.vat_group || "—"} />
          </div>
          {data.notes ? (
            <div>
              <ReadRow k={t("v201.notes")} v={data.notes} />
            </div>
          ) : null}
        </Card>
        {boxes.length > 0 ? (
          <Card title={t("v201.boxes")}>
            {/* The return's boxes are rendered as a flat four-column table —
                no row spans, no section rows, no totals row — so it converts
                like any other read-only line table. The legend names the row;
                the box number rides along beneath it on a card. */}
            <LineItems<Box>
              rows={boxes}
              collapse={false}
              fields={[
                {
                  key: "box", label: t("v201.box"), tdClass: "ordno",
                  render: (b) => <>{b.box_no || "—"}</>,
                },
                {
                  key: "legend", label: t("v201.legend"), slot: "title",
                  render: (b) => <>{b.legend || "—"}</>,
                },
                {
                  key: "amount", label: t("v201.amount"), slot: "primary", numeric: true,
                  render: (b) => <>{money(b.amount)}</>,
                },
                {
                  key: "vat", label: t("v201.vat"), slot: "primary", numeric: true,
                  render: (b) => <>{money(b.vat_amount)}</>,
                },
              ] as LineField<Box>[]}
            />
          </Card>
        ) : null}
      </FormLayout>
    </>
  );
}
