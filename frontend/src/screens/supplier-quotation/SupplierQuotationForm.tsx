/**
 * Supplier Quotation create/edit. Catalog party/item helpers.
 * Routes: /supplier-quotations/new, /supplier-quotations/:name/edit
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import SourceDocPicker from "../../components/SourceDocPicker";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { linePayload, stampItemDetails, useTotalsPreview, useTransactionRpc, type PartyDetails, type TxnLine } from "../../lib/txn";
import { ExchangeRateField, LineTrack, PartyFields } from "../../components/txnFields";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, PageHead, SumRow } from "../../components/ui";
import { FormActions, FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";

const today = toIsoDate(new Date());
const plus = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
};

export default function SupplierQuotationForm() {
  const nav = useNavigate();
  const session = useSession();
  const canSubmit = canSubmitSales(session.roles);
  const location = useLocation();
  const { name: editName } = useParams<{ name?: string }>();
  const isEdit = !!editName;
  const company = session.company;

  const [supplier, setSupplier] = useState("");
  useEffect(() => {
    if (isEdit) return;
    const mapped = (location.state as { mapped?: { supplier?: string } } | null)?.mapped;
    if (mapped?.supplier) setSupplier(String(mapped.supplier));
    const items = (mapped && "items" in mapped ? (mapped as { items?: { item_code?: string; qty?: number; rate?: number; uom?: string }[] }).items : undefined) ?? [];
    if (items.length) {
      setLines(items.map((row) => ({ item_code: row.item_code || "", qty: Number(row.qty) || 1, rate: Number(row.rate) || 0, uom: row.uom })));
    }
  }, [isEdit, location.state]);
  const [transDate, setTransDate] = useState(today);
  const [validTill, setValidTill] = useState(plus(30));
  const [taxTemplate, setTaxTemplate] = useState("");
  const [party, setParty] = useState<PartyDetails>({});
  const [conversionRate, setConversionRate] = useState(1);
  const [lines, setLines] = useState<TxnLine[]>([]);
  const [skipReprice, setSkipReprice] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  type SqDoc = {
    name: string;
    supplier?: string;
    transaction_date?: string;
    valid_till?: string;
    taxes_and_charges?: string;
    docstatus?: number;
    items?: TxnLine[];
  };
  const existing = useDoc<SqDoc>(DT.supplierQuotation, isEdit ? editName : undefined, isEdit ? editName : null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (isEdit && existing.data && !loaded) {
      const d = existing.data;
      if (d.docstatus !== 0) {
        nav(`/supplier-quotations/${encodeURIComponent(editName!)}`, { replace: true });
        return;
      }
      setSupplier(d.supplier ?? "");
      setTransDate(d.transaction_date ?? today);
      setValidTill(d.valid_till ?? plus(30));
      setTaxTemplate(d.taxes_and_charges ?? "");
      setLines(
        (d.items ?? []).map((l) => ({
          item_code: l.item_code ?? "",
          item_name: l.item_name,
          uom: l.uom,
          qty: l.qty ?? 1,
          rate: l.rate ?? 0,
        })),
      );
      setSkipReprice(true);
      setLoaded(true);
    }
  }, [isEdit, existing.data, loaded, nav, editName]);

  const templates = useDocList<{ name: string }>(DT.purchaseTaxTemplate, { fields: ["name"], limit: 50 });
  const txn = useTransactionRpc({ doctype: DT.supplierQuotation, side: "buying", company });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall<{ message: { name: string } }>(METHOD.submit);
  const busy = create.loading || update.loading || submitCall.loading;

  useEffect(() => {
    if (!supplier) return;
    void txn.fetchParty(supplier, transDate).then(async (m) => {
      if (!m) return;
      if (skipReprice) {
        setSkipReprice(false);
        return;
      }
      setParty(m);
      if (m.taxes_and_charges) setTaxTemplate(m.taxes_and_charges);
      const cur = m.currency || session.currency || "";
      const rate = await txn.fetchExchangeRate(cur, session.currency || cur, transDate);
      setConversionRate(rate);
      if (lines.some((l) => l.item_code)) {
        setLines(
          await txn.repriceLines({
            party: m,
            lines,
            transactionDate: transDate,
            currency: m.currency,
            conversionRate: rate,
            supplier,
          }),
        );
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplier]);

  async function pickItem(idx: number, item_code: string) {
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, item_code } : l)));
    if (!item_code) return;
    const m = await txn.fetchItem({
      item_code,
      supplier,
      buying_price_list: party.buying_price_list,
      currency: party.currency,
      transaction_date: transDate,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  const buildPreviewDoc = useCallback(() => {
    if (!supplier || !lines.some((l) => l.item_code)) return null;
    return {
      supplier,
      transaction_date: transDate,
      valid_till: validTill,
      company,
      taxes_and_charges: taxTemplate || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      currency: party.currency || session.currency,
      conversion_rate: conversionRate,
      items: lines
        .filter((l) => l.item_code)
        .map((l) => ({ item_code: l.item_code, qty: l.qty, rate: l.rate, uom: l.uom })),
    };
  }, [supplier, transDate, validTill, company, taxTemplate, party, session.currency, lines]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [supplier, transDate, taxTemplate, lines],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const showNet = preview?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? net;
  const ready = !!supplier && lines.length > 0 && lines.every((l) => l.item_code && l.qty > 0);

  async function saveFn(andSubmit = false) {
    if (!ready) return;
    setSaveError(null);
    try {
      const payload = {
        supplier,
        company,
        transaction_date: transDate,
        valid_till: validTill,
        taxes_and_charges: taxTemplate || undefined,
        supplier_address: party.supplier_address,
        buying_price_list: party.buying_price_list,
        payment_terms_template: party.payment_terms_template,
        currency: party.currency || session.currency,
        conversion_rate: conversionRate,
        contact_person: party.contact_person,
        items: lines.map((l) => linePayload(l)),
      };
      let name: string;
      if (isEdit) {
        await update.updateDoc(DT.supplierQuotation, editName!, payload);
        name = editName!;
      } else {
        const doc = (await create.createDoc(DT.supplierQuotation, payload)) as { name: string };
        name = doc.name;
      }
      if (andSubmit) {
        await submitCall.call({ doc: { doctype: DT.supplierQuotation, name } });
      }
      nav(`/supplier-quotations/${encodeURIComponent(name)}`);
    } catch (e) {
      setSaveError(e);
    }
  }

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/supplier-quotations")}>
            {t("sq.title")}
          </button>
        }
        title={isEdit ? (editName ?? t("sq.new")) : t("sq.new")}
      />
      {(saveError || txn.pricingError || txn.partyCall.error || submitCall.error) && (
        <ErrorBox error={saveError || txn.pricingError || txn.partyCall.error || submitCall.error} />
      )}
      <FormLayout
        aside={
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>
              {t("sq.subtotal")}
              {previewing ? "…" : ""}
            </h2>
            <SumRow k={t("sod.net")} v={money(showNet)} />
            <SumRow k={t("sod.vat")} v={money(showVat)} />
            <SumRow k={t("sod.grand")} v={money(showGrand)} cls="rule total" />
          </Card>
        }
      >
        {!isEdit && (
          <Card title={t("txn.getItemsFrom")}>
            <SourceDocPicker
              sources={[{
                label: t("nav.materialRequests"),
                doctype: DT.materialRequest,
                method: METHOD.makeMrSupplierQuotation,
                arg: "source_name",
                filters: [["docstatus", "=", 1], ["material_request_type", "=", "Purchase"], ["status", "!=", "Stopped"], ["per_ordered", "<", 100]],
              }]}
              onMapped={(mapped) => {
                if (mapped.supplier) setSupplier(String(mapped.supplier));
                const items = (mapped.items as { item_code?: string; qty?: number; rate?: number; uom?: string }[] | undefined) ?? [];
                if (items.length) setLines(items.map((row) => ({ item_code: row.item_code || "", qty: Number(row.qty) || 1, rate: Number(row.rate) || 0, uom: row.uom })));
              }}
            />
          </Card>
        )}
        <Card title={t("sq.details")}>
          <div className="fg">
            <Field label={t("sq.col.supplier")} required>
              <LinkField doctype={DT.supplier} value={supplier} onChange={setSupplier} placeholder={t("sq.supplierPh")} />
            </Field>
            <Field label={t("sq.col.date")}>
              <input className="ctl" type="date" value={transDate} onChange={(e) => setTransDate(e.target.value)} />
            </Field>
            <Field label={t("sq.col.validTill")}>
              <input className="ctl" type="date" value={validTill} onChange={(e) => setValidTill(e.target.value)} />
            </Field>
            <Field label={t("sq.col.taxTemplate")}>
              <select className="ctl" value={taxTemplate} onChange={(e) => setTaxTemplate(e.target.value)}>
                <option value="">{t("sq.taxTemplatePh")}</option>
                {(templates.data ?? []).map((row) => (
                  <option key={row.name} value={row.name}>
                    {row.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <PartyFields side="buying" partyName={supplier} party={party} onChange={(patch) => setParty((p) => ({ ...p, ...patch }))} />
          <div className="grid3" style={{ marginBlockStart: 14 }}>
            <ExchangeRateField currency={party.currency || session.currency || undefined} companyCurrency={session.currency || undefined} value={conversionRate} onChange={setConversionRate} />
          </div>
          <div className="numblk">
            <span className="infochip">
              <span className="k2">P</span>
              {t("f.priceList")} <b>{party.buying_price_list || "—"}</b>
            </span>
            <span className="infochip">
              <span className="k2">$</span>
              {t("f.currency")} <b>{party.currency || session.currency || "—"}</b>
            </span>
          </div>
        </Card>
        <Card title={t("sq.items")}>
          {/* Item, Quantity and Amount on the face of a phone card; the rate
              sits behind "More", as on the sales invoice. */}
          <LineItems<TxnLine>
            rows={lines}
            onRemove={(i) => setLines((ls) => ls.filter((_, idx) => idx !== i))}
            addWrap="inline"
            addLabel={t("sq.addLine")}
            onAdd={() => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0 }])}
            fields={[
              {
                key: "item", label: t("sq.col.item"), slot: "title",
                render: (l, i) => (
                  <>
                    <LinkField
                      doctype={DT.item}
                      value={l.item_code}
                      onChange={(v) => void pickItem(i, v)}
                      placeholder={t("sq.itemPh")}
                    />
                    <LineTrack line={l} onChange={(patch) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, ...patch } : x))} />
                  </>
                ),
              },
              {
                key: "qty", label: t("sq.col.qty"), slot: "primary", numeric: true,
                render: (l, i) => (
                  <input
                    className="ctl"
                    type="number"
                    min={0.001}
                    step={0.001}
                    value={l.qty}
                    onChange={(e) =>
                      setLines((ls) =>
                        ls.map((row, idx) => (idx === i ? { ...row, qty: parseNum(e.target.value) } : row)),
                      )
                    }
                  />
                ),
              },
              {
                key: "rate", label: t("sq.col.rate"), numeric: true,
                render: (l, i) => (
                  <input
                    className="ctl"
                    type="number"
                    min={0}
                    step={0.01}
                    value={l.rate}
                    onChange={(e) =>
                      setLines((ls) =>
                        ls.map((row, idx) => (idx === i ? { ...row, rate: parseNum(e.target.value) } : row)),
                      )
                    }
                  />
                ),
              },
              {
                key: "amount", label: t("sq.col.amount"), slot: "primary", numeric: true,
                td: { fontWeight: 600 },
                render: (l) => money(l.qty * l.rate),
              },
            ] as LineField<TxnLine>[]}
          />
        </Card>
        <FormActions
          onSave={() => void saveFn(false)}
          onSubmit={canSubmit ? () => void saveFn(true) : undefined}
          onDiscard={() =>
            nav(isEdit ? `/supplier-quotations/${encodeURIComponent(editName!)}` : "/supplier-quotations")
          }
          busy={busy}
          ready={ready}
        />
      </FormLayout>
    </>
  );
}
