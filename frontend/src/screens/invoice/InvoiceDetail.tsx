import { useNavigate, useParams } from "react-router-dom";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { printDocUrl } from "../../lib/printDoc";
import { useDoc, useDocList } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales, canWrite, eInvoiceLocked } from "../../lib/roles";
import { date, datetime, money, qty } from "../../lib/format";
import { EINVOICE_CHIP, INV_PILL_CLASS, invoiceUiStatus, isInvoiceOverdue } from "../../lib/status";
import { t } from "../../i18n/strings";
import { CREDIT_NOTE_REASON_LABELS, creditNoteReasonCode } from "../../lib/creditNoteReason";
import { TxnTotals } from "../../components/txnFields";
import { productDiscountTotal, readDiscountBasis } from "../../lib/txn";
import { Card, Empty, ErrorBox, Loading, PageHead, Pill, ReadRow, SumRow } from "../../components/ui";
import { FormLayout } from "../../components/form";
import DetailActions from "../../components/DetailActions";
import LineItems, { type LineField } from "../../components/LineItems";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { isNative } from "../../mobile/platform";

/** The pipeline the e-invoice walks, in order. */
const PIPE = ["Generated", "Queued", "Submitted", "Accepted"] as const;
const PIPE_FAILED = ["Rejected", "Failed"];

type Line = {
  name?: string; item_code?: string; item_name?: string; qty?: number; uom?: string;
  rate?: number; amount?: number; uae_item_type?: string; hs_code?: string; sac_code?: string;
  price_list_rate?: number; discount_percentage?: number; discount_amount?: number;
};

type Doc = {
  name: string; customer?: string; customer_name?: string; customer_address?: string;
  posting_date?: string; due_date?: string; po_no?: string; company?: string;
  vat_emirate?: string; taxes_and_charges?: string; tax_id?: string; company_trn?: string;
  payment_terms_template?: string; selling_price_list?: string;
  total?: number; net_total?: number; total_taxes_and_charges?: number; grand_total?: number;
  discount_amount?: number; additional_discount_percentage?: number; apply_discount_on?: string;
  outstanding_amount?: number; currency?: string; total_advance?: number;
  allocate_advances_automatically?: number; advances?: unknown[];
  docstatus?: 0 | 1 | 2; status?: string;
  is_return?: number; return_against?: string; uae_credit_note_reason?: string;
  uae_e_invoice_status?: string; items?: Line[];
};

type EInvoiceLog = {
  name: string; status?: string; modified?: string; creation?: string;
  asp_document_id?: string; error_message?: string;
};

export default function InvoiceDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.salesInvoice, name, listPath: "/invoices" });
  const nav = useNavigate();
  const session = useSession();

  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.salesInvoice, name);

  /* Payments allocated to this invoice.
     The amount lives on the Payment Entry Reference child row. Listing that
     child doctype directly is refused by has_child_permission, so read it as
     a child-table field off the PARENT — `tabChild`.field is the supported
     notation (frappe/database/query.py, CHILD_TABLE_FIELD_PATTERN) and the
     parent's own permissions apply. The child filter lands in the WHERE, not
     the ON, so only THIS invoice's rows come back; the sum below exists for
     an invoice split across payment terms, which does return several.     */
  const payments = useFrappeGetCall<{
    message: { name: string; allocated?: number; ref?: string }[];
  }>(
    METHOD.getList,
    {
      doctype: DT.paymentEntry,
      fields: JSON.stringify([
        "name",
        "`tabPayment Entry Reference`.allocated_amount as allocated",
        "`tabPayment Entry Reference`.reference_name as ref",
      ]),
      filters: JSON.stringify([
        // reference_name alone would match a document of another type that
        // happens to share the name.
        ["Payment Entry Reference", "reference_doctype", "=", DT.salesInvoice],
        ["Payment Entry Reference", "reference_name", "=", name],
        ["Payment Entry", "docstatus", "=", 1],
      ]),
      order_by: "posting_date desc",
      limit_page_length: 200,
    },
    name ? `inv-payments-${name}` : null,
  );

  const creditNotes = useDocList<{ name: string; grand_total?: number; posting_date?: string }>(
    DT.salesInvoice,
    {
      fields: ["name", "grand_total", "posting_date"],
      filters: [["return_against", "=", name], ["docstatus", "<", 2]],
      limit: 20,
    },
    name ? `inv-credit-notes-${name}` : null,
  );

  const logs = useDocList<EInvoiceLog>(DT.eInvoiceLog, {
    fields: ["name", "status", "modified", "creation", "asp_document_id", "error_message"],
    filters: [["reference_doctype", "=", DT.salesInvoice], ["reference_name", "=", name]],
    orderBy: { field: "creation", order: "desc" },
    limit: 1,
  }, name ? `inv-elog-${name}` : null);

  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message: { name: string } }>(METHOD.amend);
  const einvoiceCall = useFrappePostCall(METHOD.generateEInvoice);
  const syncCall = useFrappePostCall(METHOD.syncEInvoiceStatus);
  const fetchCall = useFrappePostCall(METHOD.fetchEInvoiceDocuments);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = data.currency || session.currency || "";
  const ui = invoiceUiStatus(data);
  const late = isInvoiceOverdue(data);
  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const grand = data.grand_total ?? 0;
  const outstanding = data.outstanding_amount ?? 0;
  const received = Math.max(grand - outstanding, 0);

  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles) && !eInvoiceLocked(data.uae_e_invoice_status);
  const eStatus = data.uae_e_invoice_status;
  const log = logs.data?.[0];
  /* Query errors are shown too. A failed Payment Entry or log read would
     otherwise render as an empty panel — "no payments" when the truth is
     "could not check", which on an invoice is the worse of the two.
     The log in particular is readable by System Manager, Accounts Manager
     and Accounts User only, so a UAE-Tax-Manager-only user sees why the
     e-invoice actions are missing rather than nothing at all.            */
  const busyError = submitCall.error || cancelCall.error || amendCall.error || deleteAction.error || einvoiceCall.error
    || syncCall.error || fetchCall.error
    || payments.error || creditNotes.error || logs.error;

  const refresh = () => Promise.all([mutate(), logs.mutate()]);

  /* Keep only the rows that point at THIS invoice, then total per payment —
     the child-table join also returns the payment's other allocations.   */
  const allocations = Object.values(
    (payments.data?.message ?? [])
      .filter((r) => r.ref === name)
      .reduce<Record<string, { name: string; allocated: number }>>((acc, r) => {
        acc[r.name] ??= { name: r.name, allocated: 0 };
        acc[r.name].allocated += Number(r.allocated) || 0;
        return acc;
      }, {}),
  );

  return (
    <>
      <PageHead
        eyebrow={
          <>
            <button type="button" className="btn quiet" onClick={() => nav("/invoices")}>
              {t("nav.invoices")}
            </button>{" / "}{data.name}
          </>
        }
        title={data.customer_name || data.customer}
        actions={
          <DetailActions
            doctype={DT.salesInvoice}
            name={name}
            draft={draft}
            submitted={submitted}
            cancelled={data.docstatus === 2}
            canSubmit={canSubmit}
            canCancel={canCancel}
            canWrite={canWrite(session)}
            busy={submitCall.loading || cancelCall.loading || amendCall.loading || deleteAction.loading}
            onEdit={() => nav(`/invoices/${encodeURIComponent(name)}/edit`)}
            onSubmit={() => void submitCall.call({ doc: { doctype: DT.salesInvoice, name } }).then(refresh)}
            onDelete={deleteAction.onDelete}
            onCancel={() => void cancelCall.call({ doctype: DT.salesInvoice, name }).then(refresh)}
            onAmend={async () => {
              const res = await amendCall.call({ doctype: DT.salesInvoice, name });
              const newName = res?.message?.name;
              if (newName) nav(`/invoices/${encodeURIComponent(newName)}`);
              else refresh();
            }}
            extra={
              <>
                {submitted && outstanding > 0 && (
                  <button className="btn" onClick={() => nav(`/payments/new?invoice=${encodeURIComponent(name)}`)}>
                    {t("inv.receive")}
                  </button>
                )}
                {submitted && !data.is_return && (
                  <button className="btn ghost" onClick={() => nav(`/invoices/${encodeURIComponent(name)}/return`)}>
                    {t("inv.credit")}
                  </button>
                )}
                {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
                {!isNative() && (
                <button type="button" className="btn ghost" onClick={() => window.open(printUrl(name), "_blank", "noopener")}>
                  {t("inv.print")}
                </button>
                )}
              </>
            }
          />
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 7 }}>
          <Pill cls={INV_PILL_CLASS[ui]}>{t(`inv.status.${ui}`)}</Pill>
          {late && <Pill cls="p-overdue">{t("inv.overdueBy")} {data.due_date ? date(data.due_date) : ""}</Pill>}
          <span className={`echip ${eStatus ? EINVOICE_CHIP[eStatus] ?? "e-none" : "e-none"}`}>
            {eStatus || t("inv.eNone")}
          </span>
          {data.po_no && <span className="pill p-flat">{t("txn.poLabel")} · {data.po_no}</span>}
          {data.return_against && (
            <button type="button" className="pill p-flat"
               onClick={() => nav(`/invoices/${encodeURIComponent(data.return_against!)}`)}>
              {data.return_against}
            </button>
          )}
        </p>
      </PageHead>

      {busyError && <ErrorBox error={busyError} />}

      {/* Payment split — the spec's worked case: total / received / outstanding */}
      {submitted && (
        <Card title={t("inv.pay.title")}>
          <div className="paybar">
            <i style={{ width: `${grand ? (received / grand) * 100 : 0}%`, background: "var(--c-billed)" }} />
            <i style={{ width: `${grand ? (outstanding / grand) * 100 : 0}%`,
                        background: late ? "var(--bad)" : "var(--c-confirmed)" }} />
          </div>
          <div className="paylegend">
            <span><i style={{ background: "var(--track)" }} />{t("inv.pay.total")} <b>{cur} {money(grand)}</b></span>
            <span><i style={{ background: "var(--c-billed)" }} />{t("inv.pay.received")} <b>{cur} {money(received)}</b></span>
            <span>
              <i style={{ background: late ? "var(--bad)" : "var(--c-confirmed)" }} />
              {t("inv.pay.outstanding")} <b>{cur} {money(outstanding)}</b>
            </span>
          </div>
        </Card>
      )}

      {/* E-invoice pipeline */}
      {submitted && (
        <Card
          title={t("inv.einv.title")}
         
          bodyClass={null as unknown as string}
        >
          <EInvoicePipeline status={eStatus} log={log} />
          <div className="addrow">
            {eStatus && !PIPE_FAILED.includes(eStatus) && log && (
              <button className="btn ghost sm" disabled={syncCall.loading}
                onClick={() => void syncCall.call({ log_name: log.name }).then(refresh)}>
                {syncCall.loading ? t("soc.saving") : t("inv.einv.refresh")}
              </button>
            )}
            {eStatus === "Accepted" && log && (
              <button className="btn ghost sm" disabled={fetchCall.loading}
                onClick={() => void fetchCall.call({ log_name: log.name }).then(refresh)}>
                {t("inv.einv.fetch")}
              </button>
            )}
            {(!eStatus || PIPE_FAILED.includes(eStatus)) && canSubmit && (
              <button className="btn sm" disabled={einvoiceCall.loading}
                onClick={() => void einvoiceCall.call({ docname: name, doctype: DT.salesInvoice }).then(refresh)}>
                {einvoiceCall.loading ? t("soc.saving") : t("inv.einv.retry")}
              </button>
            )}
            {log && (
              <button className="btn quiet sm" onClick={() => nav(`/e-invoice-log?invoice=${encodeURIComponent(name)}`)}>
                {t("inv.einv.openLog")}
              </button>
            )}
          </div>
          {log?.error_message && (
            <div className="alert" style={{ background: "var(--bad-bg)", margin: "0 16px 16px" }}>
              <span>{log.error_message}</span>
            </div>
          )}
        </Card>
      )}

      <FormLayout aside={
        <>
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("inv.totals")}</h2>
            <TxnTotals
            currency={cur}
              itemsTotal={data.total}
              productDiscount={productDiscountTotal(data.items ?? [])}
              orderDiscount={data.discount_amount}
              orderDiscountPercent={data.additional_discount_percentage}
              discountOn={readDiscountBasis(data.apply_discount_on, Number(data.discount_amount) > 0)}
              net={data.net_total}
              vat={data.total_taxes_and_charges}
              grand={grand}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("sod.grand")}
            />
            {submitted && <SumRow k={t("inv.pay.received")} v={money(received)} cls="rule" currency={cur} />}
            {submitted && (
              <SumRow k={t("inv.col.outstanding")} v={money(outstanding)} cls="due" currency={cur} />
            )}
          </Card>

          <Card title={t("sod.linked")} bodyClass={null as unknown as string}>
            <LinkedDocs
              payments={allocations}
              creditNotes={creditNotes.data ?? []}
              currency={cur}
              loading={payments.isLoading || creditNotes.isLoading}
              onOpen={(path) => nav(path)}
            />
          </Card>

          {log && (
            <Card title={t("inv.einv.log")} bodyClass="cbody">
              <ReadRow k={t("inv.einv.logStatus")} v={log.status || "—"} />
              <ReadRow k={t("inv.einv.aspId")} v={<span className="mono">{log.asp_document_id || "—"}</span>} />
              <ReadRow k={t("inv.einv.updated")} v={datetime(log.modified)} />
            </Card>
          )}
        </>
      }>
          <Card title={t("inv.details")}>
            <div className="fg">
              <ReadRow k={t("f.customer")} v={data.customer_name || data.customer} link />
              <ReadRow k={t("f.customerTrn")} v={<span className="mono">{data.tax_id || "—"}</span>} />
              <ReadRow k={t("f.companyTrn")} v={<span className="mono">{data.company_trn || "—"}</span>} />
              <ReadRow k={t("f.address")} v={data.customer_address || "—"} />
              <ReadRow k={t("inv.date")} v={date(data.posting_date)} />
              <ReadRow k={t("inv.due")} v={date(data.due_date)} />
              <ReadRow k={t("f.paymentTerms")} v={data.payment_terms_template || "—"} />
              <ReadRow k={t("f.taxTemplate")} v={data.taxes_and_charges || "—"} />
              <ReadRow k={t("f.emirate")} v={data.vat_emirate || "—"} />
              {submitted && outstanding > 0
                && (Boolean(data.advances?.length) || data.allocate_advances_automatically != null)
                && data.total_advance != null ? (
                <ReadRow k={t("txn.totalAdvance")} v={money(data.total_advance)} />
              ) : null}
              {!!data.is_return && (
                <ReadRow k={t("inv.reason")} v={(() => {
                  const code = creditNoteReasonCode(data.uae_credit_note_reason);
                  return code ? CREDIT_NOTE_REASON_LABELS[code] : (data.uae_credit_note_reason || "—");
                })()} />
              )}
            </div>
          </Card>

          {/* bodyClass off: LineItems renders the `.twrap` wrapper itself, so
              the card body must not add a second one. */}
          <Card title={t("inv.lines")} bodyClass={null}>
            {/* A saved invoice's lines are read-only here — no add, no remove.
                Item, quantity and amount on the face of a phone card; the rate
                sits below, still visible with collapse off. */}
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
                      <div className="itags">
                        {l.uae_item_type && <span className="tag">{l.uae_item_type}</span>}
                        {l.hs_code && <span className="tag code">HS {l.hs_code}</span>}
                        {l.sac_code && <span className="tag code">SAC {l.sac_code}</span>}
                      </div>
                    </>
                  ),
                },
                {
                  key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                  render: (l) => (
                    <>
                      {qty(l.qty)}
                      <div style={{ fontSize: 11, color: "var(--faint)" }}>{l.uom}</div>
                    </>
                  ),
                },
                {
                  key: "rate", label: t("sod.col.rate"), numeric: true,
                  render: (l) => <>{money(l.rate)}</>,
                },
                {
                  key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                  td: { fontWeight: 600 },
                  render: (l) => <>{money(l.amount)}</>,
                },
              ] as LineField<Line>[]}
              /* The net total the table carried in its own <tfoot>. */
              footer={
                <tr>
                  <td colSpan={4} className="n">{t("sod.net")}</td>
                  <td className="n">{money(data.net_total)}</td>
                </tr>
              }
              footerCard={<><span>{t("sod.net")}</span><span>{money(data.net_total)}</span></>}
            />
          </Card>
      </FormLayout>
    </>
  );
}

function printUrl(name: string): string {
  return printDocUrl(DT.salesInvoice, name, "UAE Bilingual Tax Invoice");
}

function EInvoicePipeline({ status, log }: { status?: string; log?: EInvoiceLog }) {
  const failed = !!status && PIPE_FAILED.includes(status);
  const reached = status ? PIPE.indexOf(status as (typeof PIPE)[number]) : -1;
  return (
    <div className="pipe">
      {PIPE.map((step, i) => {
        const cls = failed && i > 0 ? (i === 1 ? "bad" : "todo")
          : reached < 0 ? "todo"
          : i < reached ? "done"
          : i === reached ? "now"
          : "todo";
        return (
          <div className={`pstep ${cls}`} key={step}>
            <div className="ph">
              <span className="pd">{cls === "done" ? "✓" : cls === "bad" ? "!" : cls === "now" ? "●" : i + 1}</span>
              <span className="pn">{t(`inv.einv.step.${step}`)}</span>
            </div>
            <span className="pt">
              {i === reached && log?.modified ? datetime(log.modified) : "—"}
            </span>
            <span className="pl" />
          </div>
        );
      })}
      {failed && (
        <div className="pstep bad" style={{ flexBasis: "100%", paddingInlineEnd: 0 }}>
          <div className="ph">
            <span className="pd">!</span>
            <span className="pn">{status}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function LinkedDocs({
  payments, creditNotes, currency, loading, onOpen,
}: {
  payments: { name: string; allocated?: number }[];
  creditNotes: { name: string; grand_total?: number; posting_date?: string }[];
  currency: string;
  loading: boolean;
  onOpen: (path: string) => void;
}) {
  if (loading) return <Loading />;
  if (payments.length + creditNotes.length === 0) return <Empty label={t("inv.noLinked")} />;
  return (
    <>
      {payments.map((p) => (
        <div className="doc" key={p.name} onClick={() => onOpen(`/payments/${encodeURIComponent(p.name)}`)}>
          <span className="ic" style={{ background: "var(--ok-bg)", color: "var(--ok)" }}>₵</span>
          <span className="t"><b>{p.name}</b><span>{t("nav.payments")}</span></span>
          <span className="r">{money(p.allocated)}<small>{currency}</small></span>
        </div>
      ))}
      {creditNotes.map((c) => (
        <div className="doc" key={c.name} onClick={() => onOpen(`/invoices/${encodeURIComponent(c.name)}`)}>
          <span className="ic" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>↩</span>
          <span className="t"><b>{c.name}</b><span>{t("inv.credit")}</span></span>
          <span className="r">{money(c.grand_total)}<small>{date(c.posting_date)}</small></span>
        </div>
      ))}
    </>
  );
}
