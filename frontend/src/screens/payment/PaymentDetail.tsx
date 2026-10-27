import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { printDocUrl } from "../../lib/printDoc";
import { confirmCancel } from "../../lib/workflow";
import { useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { date, money } from "../../lib/format";
import {
  PARTY_TYPE, PAY_PILL, canCancelPayment, payStatus, round2, type PayType,
} from "../../lib/payments";
import { t } from "../../i18n/strings";
import { Card, Empty, ErrorBox, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import { FormLayout } from "../../components/form";
import LineItems, { type LineField } from "../../components/LineItems";
import { DirChip } from "./PaymentList";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { isNative } from "../../mobile/platform";

type Ref = {
  name?: string;
  reference_doctype?: string;
  reference_name?: string;
  payment_term?: string;
  allocated_amount?: number;
  outstanding_amount?: number;
  total_amount?: number;
};

type Doc = {
  name: string;
  payment_type?: PayType; party_type?: string; party?: string; party_name?: string;
  posting_date?: string; mode_of_payment?: string;
  paid_amount?: number; received_amount?: number;
  total_allocated_amount?: number; unallocated_amount?: number;
  reference_no?: string; reference_date?: string;
  company?: string; docstatus?: number; status?: string; owner?: string;
  references?: Ref[];
};

export default function PaymentDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.paymentEntry, name, listPath: "/payments" });
  const nav = useNavigate();
  const session = useSession();

  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.paymentEntry, name);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const cur = session.currency || "";
  const st = payStatus(data);
  const type: PayType = data.payment_type ?? "Receive";
  const amount = round2(data.paid_amount ?? 0);
  /* Stored columns — set_amounts() runs inside validate(), so these are the
     server's own figures, not a client-side re-derivation.               */
  const allocated = round2(data.total_allocated_amount ?? 0);
  const unallocated = round2(data.unallocated_amount ?? (amount - allocated));
  const refs = data.references ?? [];

  /* ERPNext grants cancel on Payment Entry to Accounts User and Accounts
     Manager. The period-closed and frozen-date gates are enforced server
     side on the GL reversal, so the button stays and the error surfaces. */
  const canCancel = canCancelPayment(session.roles) && data.docstatus === 1;

  return (
    <>
      <PageHead
        eyebrow={
          <>
            <button type="button" className="btn quiet" onClick={() => nav("/payments")}>
              {t("nav.payments")}
            </button>{" / "}{data.name}
          </>
        }
        title={data.party_name || data.party}
        actions={
          <>
            <DocHistory doctype={DT.paymentEntry} name={name} />
            {/* Print view needs a cookie session; the app gets PDF sharing in round 3. */}
            {!isNative() && (
            <button type="button" className="btn ghost"
              onClick={() => window.open(printUrl(data.name), "_blank", "noopener")}>
              {t("pay.print")}
            </button>
            )}
            {data.docstatus === 0 && (
              <button className="btn ghost" onClick={() => nav(`/payments/${encodeURIComponent(name)}/edit`)}>
                {t("inv.edit")}
              </button>
            )}
            {data.docstatus === 0 && (
              <button type="button" className="btn quiet" disabled={deleteAction.loading}
                onClick={deleteAction.onDelete}>
                {deleteAction.loading ? t("soc.saving") : t("inv.delete")}
              </button>
            )}
            {canCancel && (
              <button className="btn quiet" disabled={cancelCall.loading}
                onClick={() => {
                  if (!confirmCancel(name)) return;
                  void cancelCall.call({ doctype: DT.paymentEntry, name }).then(() => mutate()).catch(() => undefined);
                }}>
                {cancelCall.loading ? t("soc.saving") : t("pay.cancel")}
              </button>
            )}
            {data.docstatus === 2 && (
              <button className="btn ghost" disabled={amendCall.loading}
                onClick={() => void amendCall.call({ doctype: DT.paymentEntry, name }).then((r) => {
                  const n = r?.message?.name || "";
                  if (n) nav(`/payments/${encodeURIComponent(n)}/edit`);
                }).catch(() => undefined)}>
                {amendCall.loading ? t("soc.saving") : t("pay.amend")}
              </button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 7 }}>
          <Pill cls={PAY_PILL[st]}>{t(`pay.status.${st}`)}</Pill>
          <DirChip type={type} />
          {data.mode_of_payment && <span className="pill p-flat">{data.mode_of_payment}</span>}
          {data.reference_no && <span className="pill p-flat mono">{data.reference_no}</span>}
        </p>
      </PageHead>

      {(cancelCall.error || amendCall.error || deleteAction.error) && (
        <ErrorBox error={cancelCall.error ?? amendCall.error ?? deleteAction.error} />
      )}

      <Card bodyClass="cbody">
        <div className="srow" style={{ paddingBlock: 0 }}>
          <span className="k">{t("pay.sAmount")}</span>
          <span className="v" style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-.025em" }}>
            <span className="cur">{cur}</span>{money(amount)}
          </span>
        </div>
        <div className="allocbar" style={{ height: 12 }}>
          <i style={{ width: `${amount ? (allocated / amount) * 100 : 0}%`, background: "var(--c-billed)" }} />
          <i style={{ width: `${amount ? Math.max(0, (unallocated / amount) * 100) : 0}%`, background: "var(--warn)" }} />
        </div>
        <div className="paylegend">
          <span>
            <i style={{ background: "var(--c-billed)" }} />
            {t("pay.allocated")} <b>{cur} {money(allocated)}</b>
          </span>
          <span>
            <i style={{ background: "var(--warn)" }} />
            {t("pay.unallocated")} <b>{cur} {money(unallocated)}</b>
          </span>
        </div>
      </Card>

      <FormLayout aside={
        <>
          {unallocated > 0.005 && (
            <div className="alert">
              <span className="ic">!</span>
              <span>
                <b>{t("pay.unallocated")} — {cur} {money(unallocated)}</b>
                {t("pay.warn.leftB")}
              </span>
            </div>
          )}
          <div className="note">
            <span className="ic">✦</span>
            <span><b>{t("pay.noteT")}</b>{t("pay.noteB")}</span>
          </div>
        </>
      }>
          <Card title={t("pay.hDet")}>
            <div className="fg">
              <ReadRow k={t("pay.lType")} v={t(`pay.type.${type}`)} />
              <ReadRow k={t(`pay.party.${data.party_type ?? PARTY_TYPE[type]}`)}
                       v={data.party_name || data.party || "—"} />
              <ReadRow k={t("pay.lDate")} v={date(data.posting_date)} />
              <ReadRow k={t("pay.mode")} v={data.mode_of_payment || "—"} />
              <ReadRow k={t("pay.refNo")} v={<span className="mono">{data.reference_no || "—"}</span>} />
              <ReadRow k={t("pay.refDate")} v={date(data.reference_date)} />
            </div>
          </Card>

          <Card title={t("pay.hClear")} bodyClass={null as unknown as string}>
            {refs.length === 0 ? <Empty label={t("pay.noAllocations")} /> : (
              /* What this payment cleared, invoice by invoice. Read-only —
                 the allocation is edited on the form, never here — so no add
                 or remove, and collapse={false} keeps both figures visible
                 on a phone rather than behind "More". */
              <LineItems<Ref>
                rows={refs}
                collapse={false}
                fields={[
                  {
                    key: "inv", label: t("pay.aInv"), slot: "title", tdClass: "inv",
                    render: (r) => {
                      const link = r.reference_doctype === DT.salesInvoice
                        ? `/invoices/${encodeURIComponent(r.reference_name ?? "")}`
                        : r.reference_doctype === DT.purchaseInvoice
                          ? `/purchase-invoices/${encodeURIComponent(r.reference_name ?? "")}`
                          : "";
                      return (
                        <>
                          {link
                            ? <b><button type="button" className="btn quiet" onClick={() => nav(link)}>{r.reference_name}</button></b>
                            : <b>{r.reference_name}</b>}
                          <span>{r.reference_doctype}{r.payment_term ? ` · ${r.payment_term}` : ""}</span>
                        </>
                      );
                    },
                  },
                  {
                    key: "cleared", label: t("pay.cleared"), slot: "primary", numeric: true,
                    render: (r) => money(Number(r.allocated_amount) || 0),
                  },
                  {
                    key: "remaining", label: t("pay.remaining"), slot: "primary", numeric: true,
                    td: { color: "var(--muted)" },
                    render: (r) => {
                      const alloc = Number(r.allocated_amount) || 0;
                      const totalAmt = Number(r.total_amount) || 0;
                      return totalAmt ? money(Math.max(0, totalAmt - alloc)) : "—";
                    },
                  },
                ] as LineField<Ref>[]}
              />
            )}
          </Card>
      </FormLayout>
    </>
  );
}

/** Desk's Bank and Cash voucher hardcodes English and prints raw numbers.
    This format is the same voucher, bilingual, with the currency on every amount. */
function printUrl(name: string): string {
  return printDocUrl(DT.paymentEntry, name, "UAE Bilingual Payment");
}
