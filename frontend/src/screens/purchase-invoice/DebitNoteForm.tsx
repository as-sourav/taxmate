/**
 * Purchase Debit Note (return against Purchase Invoice).
 * Callers: App.tsx will import and route /purchase-invoices/:name/return (~after CreditNoteForm pattern L142);
 * PurchaseInvoiceDetail will add Debit Note button for submitted invoices.
 * No existing DebitNoteForm — CreditNoteForm.tsx is sales-only (METHOD.makeSalesReturn).
 * Schema: make_purchase_return → { supplier, is_return, return_against, items:[{item_code, qty, rate}] } → insert Purchase Invoice.
 * User: "Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself. … Don't stop until you have completed all the to-dos."
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { money } from "../../lib/format";
import { applyReturnQty, useTotalsPreview, useTransactionRpc } from "../../lib/txn";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormLayout } from "../../components/form";
import { TxnTotals } from "../../components/txnFields";
import LineItems, { type LineField } from "../../components/LineItems";

type ReturnLine = {
  item_code: string;
  item_name?: string;
  qty: number;
  rate: number;
  conversion_factor?: number;
  rejected_qty?: number;
  received_qty?: number;
  stock_qty?: number;
  received_stock_qty?: number;
  amount?: number;
};

type ReturnDoc = {
  supplier?: string;
  company?: string;
  currency?: string;
  items?: ReturnLine[];
  return_against?: string;
  is_return?: number;
};

export default function DebitNoteForm() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const make = useFrappePostCall<{ message: ReturnDoc }>(METHOD.makePurchaseReturn);
  const create = useInsert();
  const [draft, setDraft] = useState<ReturnDoc | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const { previewTotals } = useTransactionRpc({
    doctype: DT.purchaseInvoice,
    side: "buying",
    company: draft?.company || session.company,
  });
  const qtyKey = (draft?.items ?? []).map((line) => line.qty).join(",");
  const { preview } = useTotalsPreview(
    () => {
      if (!draft) return null;
      const doc: Record<string, unknown> = { ...draft, doctype: DT.purchaseInvoice };
      delete doc.name;
      return doc;
    },
    [qtyKey, draft?.company, name],
    previewTotals,
  );

  useEffect(() => {
    make
      .call({ source_name: name })
      .then((r) => setDraft(r?.message ?? null))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  async function save() {
    if (!draft) return;
    setBusy(true);
    setSaveError(null);
    try {
      const body: Record<string, unknown> = { ...draft, doctype: DT.purchaseInvoice };
      delete body.name;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.purchaseInvoice, body);
      nav(`/purchase-invoices/${encodeURIComponent((created as { name: string }).name)}`);
    } catch (err) {
      setSaveError(err);
    } finally {
      setBusy(false);
    }
  }

  if (make.loading && !draft) return <Loading />;
  if (make.error) return <ErrorBox error={make.error} />;

  const lines = draft?.items ?? [];
  const fallbackNet = lines.reduce((sum, line) => sum + line.qty * line.rate, 0);
  const grand = preview?.grand_total ?? fallbackNet;
  const cur = draft?.currency || "";
  const returning = t("pr.returning").replace("{amount}", `${cur ? `${cur} ` : ""}${money(Math.abs(Number(grand) || 0))}`);

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav(`/purchase-invoices/${encodeURIComponent(name)}`)}>
            {name}
          </button>
        }
        title={t("pi.debit")}
        actions={
          <>
            <button type="button" className="btn ghost" onClick={() => nav(`/purchase-invoices/${encodeURIComponent(name)}`)}>
              {t("soc.discard")}
            </button>
            <button type="button" className="btn" disabled={busy || !draft} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
          </>
        }
      />
      {saveError && <ErrorBox error={saveError} />}
      <FormLayout
        aside={
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("dn.summary")}</h2>
            <p className="sub" role="status" aria-live="polite">{returning}</p>
            <TxnTotals
              currency={cur}
              itemsTotal={preview?.total ?? fallbackNet}
              net={preview?.net_total ?? fallbackNet}
              vat={preview?.total_taxes_and_charges}
              grand={grand}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("pr.returnTotal")}
            />
          </Card>
        }
      >
      <Card title={t("inv.lines")} bodyClass={null}>
        {/* The returned item and its Quantity and Amount on the face of a
            phone card; the rate comes from the invoice being returned and is
            read-only, so it sits behind "More". The lines themselves come
            from make_purchase_return — none can be added or removed here. */}
        <LineItems<ReturnLine>
          rows={draft?.items ?? []}
          fields={[
            {
              key: "item", label: t("soc.pickItem"), slot: "title",
              render: (l) => l.item_name || l.item_code,
            },
            {
              key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
              render: (l, i) => (
                <input
                  className="ctl mini nn"
                  style={{ width: 80 }}
                  inputMode="decimal"
                  aria-label={t("sod.col.qty")}
                  value={Math.abs(l.qty)}
                  onChange={(e) =>
                    setDraft((d) =>
                      d
                        ? {
                            ...d,
                            items: (d.items ?? []).map((x, j) =>
                              j === i ? applyReturnQty(x, e.target.value) : x,
                            ),
                          }
                        : d,
                    )
                  }
                />
              ),
            },
            {
              key: "rate", label: t("sod.col.rate"), numeric: true,
              render: (l) => <span>{money(l.rate)}</span>,
            },
            {
              key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
              render: (l, i) => {
                const previewAmount = preview?.items?.[i]?.amount;
                const amount = previewAmount == null ? l.qty * l.rate : Number(previewAmount);
                return <span>{money(Math.abs(amount))}</span>;
              },
            },
          ] as LineField<ReturnLine>[]}
        />
      </Card>
      <Field label={t("pi.returnAgainst")}>
        <input className="ctl readonly" readOnly value={draft?.return_against || name} />
      </Field>
      </FormLayout>
    </>
  );
}
