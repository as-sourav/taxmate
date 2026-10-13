/**
 * Purchase Receipt return form. Mirrors DebitNoteForm pattern.
 * Callers: App.tsx /purchase-receipts/:name/return.
 * API: METHOD.makePrReturn -> resource.insert on Purchase Receipt.
 * User: "PurchaseReceiptReturn.tsx — mirror CreditNoteForm / DebitNoteForm"
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
import { Card, ErrorBox, Loading, PageHead } from "../../components/ui";
import { FormLayout } from "../../components/form";
import { TxnTotals } from "../../components/txnFields";

type ReturnLine = {
  item_code: string;
  item_name?: string;
  qty: number;
  rate: number;
  uom?: string;
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
  return_against?: string;
  is_return?: number;
  items?: ReturnLine[];
};

export default function PurchaseReceiptReturn() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const session = useSession();
  const make = useFrappePostCall<{ message: ReturnDoc }>(METHOD.makePrReturn);
  const create = useInsert();
  const [draft, setDraft] = useState<ReturnDoc | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const { previewTotals } = useTransactionRpc({
    doctype: DT.purchaseReceipt,
    side: "buying",
    company: draft?.company || session.company,
  });
  const qtyKey = (draft?.items ?? []).map((line) => line.qty).join(",");
  const { preview } = useTotalsPreview(
    () => {
      if (!draft) return null;
      const doc: Record<string, unknown> = { ...draft, doctype: DT.purchaseReceipt };
      delete doc.name;
      return doc;
    },
    [qtyKey, draft?.company, name],
    previewTotals,
  );

  useEffect(() => {
    make.call({ source_name: name }).then((r) => {
      setDraft(r?.message ?? null);
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  async function save() {
    if (!draft) return;
    setBusy(true); setSaveError(null);
    try {
      const body: Record<string, unknown> = { ...draft };
      delete body.name;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.purchaseReceipt, body) as { name: string };
      nav(`/purchase-receipts/${encodeURIComponent(created.name)}`);
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
  const net = preview?.net_total ?? fallbackNet;
  const grand = preview?.grand_total ?? fallbackNet;
  const cur = draft?.currency || "";
  const returning = t("pr.returning").replace("{amount}", `${cur ? `${cur} ` : ""}${money(Math.abs(Number(grand) || 0))}`);

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav(`/purchase-receipts/${encodeURIComponent(name)}`)}>
            {name}
          </button>
        }
        title={t("pr.returnTitle")}
        actions={
          <>
            <button type="button" className="btn ghost" onClick={() => nav(`/purchase-receipts/${encodeURIComponent(name)}`)}>
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
              net={net}
              vat={preview?.total_taxes_and_charges}
              grand={grand}
              netLabel={t("sod.net")}
              vatLabel={t("sod.vat")}
              grandLabel={t("pr.returnTotal")}
            />
          </Card>
        }
      >
      <Card title={t("soc.items")} bodyClass={null}>
        <div className="twrap">
          <table>
            <thead>
              <tr>
                <th>{t("soc.pickItem")}</th>
                <th className="n">{t("sod.col.qty")}</th>
                <th className="n">{t("sod.col.rate")}</th>
                <th className="n">{t("sod.col.amount")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => {
                const previewAmount = preview?.items?.[i]?.amount;
                const amount = previewAmount == null ? l.qty * l.rate : Number(previewAmount);
                return (
                <tr key={i}>
                  <td>{l.item_name || l.item_code}</td>
                  <td className="n">
                    <input
                      className="ctl mini nn"
                      style={{ width: 80 }}
                      inputMode="decimal"
                      aria-label={t("sod.col.qty")}
                      value={Math.abs(l.qty)}
                      onChange={(e) => setDraft((d) => d ? {
                        ...d,
                        items: (d.items ?? []).map((x, j) =>
                          j === i ? applyReturnQty(x, e.target.value) : x),
                      } : d)}
                    />
                  </td>
                  <td className="n">{money(l.rate)}</td>
                  <td className="n">{money(Math.abs(amount))}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      </FormLayout>
    </>
  );
}
