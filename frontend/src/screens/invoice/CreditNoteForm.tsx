import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useInsert } from "../../lib/resource";
import { money, parseNum } from "../../lib/format";
import { t } from "../../i18n/strings";
import { CREDIT_NOTE_REASON_LABELS, CREDIT_NOTE_REASONS, creditNoteReasonCode } from "../../lib/creditNoteReason";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import LineItems, { type LineField } from "../../components/LineItems";

type ReturnLine = { item_code: string; item_name?: string; qty: number; rate: number };

type ReturnDoc = {
  customer?: string;
  items?: ReturnLine[];
  uae_credit_note_reason?: string;
  return_against?: string;
  is_return?: number;
};

export default function CreditNoteForm() {
  const { name = "" } = useParams();
  const nav = useNavigate();
  const make = useFrappePostCall<{ message: ReturnDoc }>(METHOD.makeSalesReturn);
  const create = useInsert();
  const [draft, setDraft] = useState<ReturnDoc | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    make.call({ source_name: name }).then((r) => {
      const doc = r?.message ?? null;
      setDraft(doc);
      setReason(creditNoteReasonCode(doc?.uae_credit_note_reason));
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  async function save() {
    if (!draft) return;
    if (!creditNoteReasonCode(reason)) {
      setSaveError({ message: t("inv.reasonRequired") });
      return;
    }
    setBusy(true); setSaveError(null);
    try {
      const created = await create.createDoc(DT.salesInvoice, {
        ...draft,
        doctype: DT.salesInvoice,
        uae_credit_note_reason: reason,
      });
      nav(`/invoices/${encodeURIComponent((created as { name: string }).name)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  if (make.loading && !draft) return <Loading />;
  if (make.error) return <ErrorBox error={make.error} />;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav(`/invoices/${encodeURIComponent(name)}`)}>{name}</button>}
        title={t("inv.credit")}
        actions={
          <>
            <button className="btn ghost" onClick={() => nav(`/invoices/${encodeURIComponent(name)}`)}>{t("soc.discard")}</button>
            <button className="btn" disabled={busy || !creditNoteReasonCode(reason)} onClick={() => void save()}>
              {busy ? t("soc.saving") : t("soc.save")}
            </button>
          </>
        }
      />
      {saveError && <ErrorBox error={saveError} />}
      <Card title={t("inv.reason")}>
        <Field label={t("inv.reason")} required hint={t("inv.reasonHint")}>
          <select className="ctl" value={creditNoteReasonCode(reason)} onChange={(e) => setReason(e.target.value)}>
            <option value="">Choose a reason</option>
            {CREDIT_NOTE_REASONS.map((code) => (
              <option key={code} value={code}>{CREDIT_NOTE_REASON_LABELS[code]}</option>
            ))}
          </select>
        </Field>
      </Card>
      <Card title={t("inv.lines")} bodyClass={null}>
        {/* Item, Quantity and Amount on the face of a phone card; the rate is
            read-only on a credit note, so it sits behind "More". The lines
            come from the invoice being returned — they cannot be added or
            removed here. */}
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
                <input className="ctl mini nn" style={{ width: 80 }} value={l.qty}
                  onChange={(e) => setDraft((d) => d ? {
                    ...d,
                    items: (d.items ?? []).map((x, j) => j === i ? { ...x, qty: parseNum(e.target.value) } : x),
                  } : d)} />
              ),
            },
            {
              key: "rate", label: t("sod.col.rate"), numeric: true,
              render: (l) => <span>{money(l.rate)}</span>,
            },
            {
              key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
              render: (l) => <span>{money(l.qty * l.rate)}</span>,
            },
          ] as LineField<ReturnLine>[]}
        />
      </Card>
    </>
  );
}
