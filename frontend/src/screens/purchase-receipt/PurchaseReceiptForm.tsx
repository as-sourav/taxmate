/**
 * Purchase Receipt create/edit. Catalog txn helpers + get-items-from.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canSubmitSales, canWrite } from "../../lib/roles";
import { money, parseNum, toIsoDate } from "../../lib/format";
import { linePayload, mappedItem, stampItemDetails, useTotalsPreview, useTransactionRpc, type PartyDetails, type TxnLine } from "../../lib/txn";
import { ExchangeRateField, LineTrack, PartyFields } from "../../components/txnFields";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead, SumRow } from "../../components/ui";
import { FormActions, FormLayout, ReadinessCard } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";
import SourceDocPicker from "../../components/SourceDocPicker";

type Line = TxnLine & { warehouse?: string; batch_no?: string; serial_no?: string };

const today = toIsoDate(new Date());

export default function PurchaseReceiptForm() {
  const { name = "new" } = useParams();
  const isNew = name === "new";
  const editing = !isNew;
  const nav = useNavigate();
  const session = useSession();
  const canSubmit = canSubmitSales(session.roles);
  const company = session.company;

  const existing = useDoc<{
    name: string; supplier?: string; posting_date?: string; set_warehouse?: string;
    taxes_and_charges?: string; supplier_delivery_note?: string; rejected_warehouse?: string; docstatus?: number; items?: Line[];
  }>(DT.purchaseReceipt, isNew ? undefined : name, isNew ? null : name);

  const [supplier, setSupplier] = useState("");
  const [postingDate, setPostingDate] = useState(today);
  const [warehouse, setWarehouse] = useState("");
  const [supplierDn, setSupplierDn] = useState("");
  const [rejectedWh, setRejectedWh] = useState("");
  const [taxTemplate, setTaxTemplate] = useState("");
  const [party, setParty] = useState<PartyDetails>({});
  const [conversionRate, setConversionRate] = useState(1);
  const [lines, setLines] = useState<Line[]>([{ item_code: "", qty: 1, rate: 0 }]);
  const [hydrated, setHydrated] = useState(isNew);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [skipReprice, setSkipReprice] = useState(false);

  const templates = useDocList<{ name: string }>(DT.purchaseTaxTemplate, { fields: ["name"], limit: 50 });
  const txn = useTransactionRpc({ doctype: DT.purchaseReceipt, side: "buying", company });
  const create = useInsert();
  const update = useSave();
  const submitCall = useFrappePostCall<{ message: { name: string } }>(METHOD.submit);
  const busy = create.loading || update.loading || submitCall.loading;

  useEffect(() => {
    if (!editing || !existing.data || hydrated) return;
    const d = existing.data;
    setSupplier(d.supplier || "");
    setPostingDate(d.posting_date || today);
    setWarehouse(d.set_warehouse || "");
    setSupplierDn(d.supplier_delivery_note || "");
    setRejectedWh(d.rejected_warehouse || "");
    setTaxTemplate(d.taxes_and_charges || "");
    setLines(
      (d.items ?? []).length
        ? (d.items ?? []).map((row) => mappedItem(row, d.set_warehouse || ""))
        : [{ item_code: "", qty: 1, rate: 0 }],
    );
    setSkipReprice(true);
    setHydrated(true);
  }, [editing, existing.data, hydrated]);

  useEffect(() => {
    if (!supplier) return;
    void txn.fetchParty(supplier, postingDate).then(async (m) => {
      if (!m) return;
      if (skipReprice) { setSkipReprice(false); return; }
      setParty(m);
      if (m.taxes_and_charges) setTaxTemplate(m.taxes_and_charges);
      const cur = m.currency || session.currency || "";
      const rate = await txn.fetchExchangeRate(cur, session.currency || cur, postingDate);
      setConversionRate(rate);
      if (lines.some((l) => l.item_code)) {
        setLines(await txn.repriceLines({ party: m, lines, transactionDate: postingDate, currency: m.currency, conversionRate: rate, supplier }));
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplier]);

  async function pickItem(idx: number, item_code: string) {
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, item_code } : l)));
    if (!item_code) return;
    const m = await txn.fetchItem({
      item_code, supplier,
      buying_price_list: party.buying_price_list,
      currency: party.currency,
      transaction_date: postingDate,
      warehouse,
      qty: lines[idx]?.qty || 1,
    });
    if (!m) return;
    setLines((ls) => ls.map((l, i) => (i === idx ? stampItemDetails({ ...l, item_code }, m) : l)));
  }

  function applyMapped(mapped: Record<string, unknown>) {
    setSkipReprice(true);
    if (mapped.supplier) setSupplier(String(mapped.supplier));
    if (mapped.posting_date) setPostingDate(String(mapped.posting_date));
    if (mapped.set_warehouse) setWarehouse(String(mapped.set_warehouse));
    if (mapped.taxes_and_charges) setTaxTemplate(String(mapped.taxes_and_charges));
    const items = (mapped.items as Line[] | undefined) ?? [];
    setLines(items.map((l) => mappedItem(l, String(mapped.set_warehouse || ""))));
  }

  const buildPreviewDoc = useCallback(() => {
    if (!supplier || !lines.some((l) => l.item_code)) return null;
    return {
      supplier,
      posting_date: postingDate,
      set_warehouse: warehouse || undefined,
      company,
      taxes_and_charges: taxTemplate || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      currency: party.currency || session.currency,
      conversion_rate: conversionRate,
      items: lines.filter((l) => l.item_code).map((l) => ({
        item_code: l.item_code, qty: l.qty, rate: l.rate, uom: l.uom,
        warehouse: l.warehouse || warehouse,
      })),
    };
  }, [supplier, postingDate, warehouse, company, taxTemplate, party, session.currency, lines]);

  const { preview, previewing } = useTotalsPreview(
    buildPreviewDoc,
    [supplier, postingDate, taxTemplate, lines],
    txn.previewTotals,
  );

  const net = useMemo(() => lines.reduce((s, l) => s + l.qty * l.rate, 0), [lines]);
  const showNet = preview?.net_total ?? net;
  const showVat = preview?.total_taxes_and_charges ?? 0;
  const showGrand = preview?.grand_total ?? net;

  const checks = [
    [t("nav.suppliers"), !!supplier],
    [t("inv.date"), !!postingDate],
    [t("nav.warehouses"), !!warehouse],
    [t("inv.lines"), lines.length > 0 && lines.every((l) => l.item_code)],
  ] as const;
  const ready = checks.every(([, ok]) => ok);

  if (!canWrite(session)) {
    return <ErrorBox error={new Error(t("team.denied"))} />;
  }
  if (editing && existing.isLoading && !hydrated) return <Loading />;
  if (editing && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (editing && existing.data && existing.data.docstatus !== 0) {
    return <Navigate to={`/purchase-receipts/${encodeURIComponent(name)}`} replace />;
  }

  function buildBody() {
    return {
      supplier,
      posting_date: postingDate,
      set_posting_time: 1,
      set_warehouse: warehouse,
      supplier_delivery_note: supplierDn || undefined,
      rejected_warehouse: rejectedWh || undefined,
      taxes_and_charges: taxTemplate || undefined,
      supplier_address: party.supplier_address,
      buying_price_list: party.buying_price_list,
      company: company || undefined,
      currency: party.currency || session.currency || undefined,
      conversion_rate: conversionRate,
      contact_person: party.contact_person,
      items: lines.map((l) => ({
        ...linePayload(l),
        warehouse: l.warehouse || warehouse || undefined,
      })),
    };
  }

  async function save(shouldSubmit: boolean) {
    setSaveError(null);
    try {
      let docName = name;
      if (editing) {
        await update.updateDoc(DT.purchaseReceipt, name, buildBody());
      } else {
        const created = (await create.createDoc(DT.purchaseReceipt, buildBody())) as { name: string };
        docName = created.name;
      }
      if (shouldSubmit && docName) {
        await submitCall.call({ doc: { doctype: DT.purchaseReceipt, name: docName } });
      }
      nav(`/purchase-receipts/${encodeURIComponent(docName)}`);
    } catch (err) {
      setSaveError(err);
    }
  }

  const err = saveError || txn.pricingError || create.error || update.error || submitCall.error || txn.partyCall.error;

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet"
            onClick={() => nav(editing ? `/purchase-receipts/${encodeURIComponent(name)}` : "/purchase-receipts")}>
            {t("nav.purchaseReceipts")}
          </button>
        }
        title={editing ? t("pr.editTitle") : t("pr.new")}
        actions={
          <FormActions
            onDiscard={() => nav(editing ? `/purchase-receipts/${encodeURIComponent(name)}` : "/purchase-receipts")}
            onSave={() => void save(false)}
            onSubmit={canSubmit ? () => void save(true) : undefined}
            busy={busy} ready={ready} submitLabel={t("inv.submit")}
          />
        }
      />
      {err && <ErrorBox error={err} />}
      <FormLayout
        aside={
          <>
            <Card bodyClass="cbody">
              <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>
                {t("soc.summary")}{previewing ? "…" : ""}
              </h2>
              <SumRow k={t("sod.net")} v={money(showNet)} />
              <SumRow k={t("sod.vat")} v={money(showVat)} />
              <SumRow k={t("sod.grand")} v={money(showGrand)} cls="rule total" />
            </Card>
            <ReadinessCard
              checks={checks.map(([label, ok]) => ({ label, ok }))}
              title={t("soc.ready")} caption={t("soc.readyCap")}
            />
          </>
        }
      >
        {isNew && (
          <Card title={t("txn.getItemsFrom")}>
            <SourceDocPicker
              sources={[
                {
                  label: t("nav.purchaseOrders"), doctype: DT.purchaseOrder,
                  method: METHOD.makePurchaseReceipt, arg: "source_name",
                  filters: [["docstatus", "=", 1], ["status", "not in", ["Closed", "On Hold"]], ["per_received", "<", 99.99]],
                },
              ]}
              onMapped={applyMapped}
            />
          </Card>
        )}
        <Card num={1} title={t("pi.who")}>
          <div className="grid2">
            <Field label={t("nav.suppliers")} required>
              <LinkField doctype={DT.supplier} value={supplier} onChange={setSupplier} />
            </Field>
            <Field label={t("pi.supplierTrn")}>
              <input className="ctl readonly" readOnly value={party.tax_id || ""} />
            </Field>
            <Field label={t("inv.date")} required htmlFor="pr-posting-date">
              <input id="pr-posting-date" name="posting_date" className="ctl" type="date"
                value={postingDate} onChange={(e) => setPostingDate(e.target.value)} />
            </Field>
            <Field label={t("pi.supplierDn")}>
              <input className="ctl" value={supplierDn} onChange={(e) => setSupplierDn(e.target.value)} />
            </Field>
            <Field label={t("pi.rejectedWh")}>
              <LinkField doctype={DT.warehouse} value={rejectedWh} onChange={setRejectedWh}
                filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
            </Field>
            <Field label={t("nav.warehouses")} required>
              <LinkField doctype={DT.warehouse} value={warehouse} onChange={setWarehouse}
                filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
            </Field>
            <Field label={t("f.taxTemplate")} htmlFor="pr-tax-template">
              <select id="pr-tax-template" name="taxes_and_charges" className="ctl" value={taxTemplate}
                onChange={(e) => setTaxTemplate(e.target.value)} aria-label={t("f.taxTemplate")}>
                <option value="" />
                {(templates.data ?? []).map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
          </div>
          <PartyFields side="buying" partyName={supplier} party={party} onChange={(patch) => setParty((p) => ({ ...p, ...patch }))} />
          <div className="grid3" style={{ marginBlockStart: 14 }}>
            <ExchangeRateField currency={party.currency || session.currency || undefined} companyCurrency={session.currency || undefined} value={conversionRate} onChange={setConversionRate} />
          </div>
        </Card>
        <Card num={2} title={t("inv.lines")} bodyClass={null as unknown as string}>
          {/* Item, Quantity and Amount on the face of a phone card. The
              warehouse defaults from the header, and the rate arrives priced;
              batch and serial are typed only for the items that carry them —
              all four sit behind "More". */}
          <LineItems<Line>
            rows={lines}
            showIndex
            onRemove={(i) => setLines((ls) => ls.filter((_, j) => j !== i))}
            addLabel={t("soc.addLine")}
            onAdd={() => setLines((ls) => [...ls, { item_code: "", qty: 1, rate: 0, warehouse }])}
            fields={[
              {
                key: "item", label: t("soc.pickItem"), slot: "title", td: { minWidth: 220 },
                render: (l, i) => (
                  <>
                    <LinkField doctype={DT.item} value={l.item_code} onChange={(v) => void pickItem(i, v)} />
                    <LineTrack line={l} onChange={(patch) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, ...patch } : x))} />
                  </>
                ),
              },
              {
                key: "warehouse", label: t("nav.warehouses"), td: { minWidth: 160 },
                render: (l, i) => (
                  <LinkField doctype={DT.warehouse} value={l.warehouse ?? warehouse}
                    onChange={(v) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, warehouse: v } : x)))}
                    filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
                ),
              },
              {
                key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 80 }} value={l.qty}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, qty: parseNum(e.target.value) } : x)))} />
                ),
              },
              {
                key: "rate", label: t("sod.col.rate"), numeric: true,
                render: (l, i) => (
                  <input className="ctl mini nn" style={{ width: 104 }} value={l.rate}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, rate: parseNum(e.target.value) } : x)))} />
                ),
              },
              {
                key: "amount", label: t("sod.col.amount"), slot: "primary", numeric: true,
                td: { fontWeight: 600 },
                render: (l) => <span>{money(l.qty * l.rate)}</span>,
              },
              {
                key: "batch", label: t("pr.batchNo"), td: { minWidth: 100 },
                render: (l, i) => (
                  <input className="ctl mini" placeholder={t("txn.ph.batch")} value={l.batch_no ?? ""}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, batch_no: e.target.value } : x))} />
                ),
              },
              {
                key: "serial", label: t("pr.serialNo"), td: { minWidth: 100 },
                render: (l, i) => (
                  <input className="ctl mini" placeholder="SN" value={l.serial_no ?? ""}
                    onChange={(e) => setLines((ls) => ls.map((x, j) => j === i ? { ...x, serial_no: e.target.value } : x))} />
                ),
              },
            ] as LineField<Line>[]}
          />
        </Card>
      </FormLayout>
    </>
  );
}
