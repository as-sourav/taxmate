import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  useFrappeGetCall, useFrappePostCall,
} from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useDoc, useDocList, useInsert, useSave } from "../../lib/resource";
import { useSession } from "../../lib/session";
import {
  PARTY_TYPE, autoAllocate, canSubmitPayment, needsReference, round2,
  type PayType,
} from "../../lib/payments";
import { date, money, parseNum, toIsoDate } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, Empty, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { FormActions, FormLayout, ReadinessCard, type Check } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";

type Ref = {
  reference_doctype?: string;
  reference_name?: string;
  payment_term?: string;
  allocated_amount?: number;
  outstanding_amount?: number;
  total_amount?: number;
  due_date?: string;
  bill_no?: string;
};

type Deduction = { account: string; cost_center: string; amount: number; description: string };

type PayDoc = {
  name?: string;
  payment_type?: PayType;
  party_type?: string;
  party?: string;
  party_name?: string;
  posting_date?: string;
  paid_amount?: number;
  received_amount?: number;
  mode_of_payment?: string;
  reference_no?: string;
  reference_date?: string;
  company?: string;
  paid_from?: string;
  paid_to?: string;
  paid_from_account_currency?: string;
  paid_to_account_currency?: string;
  source_exchange_rate?: number;
  target_exchange_rate?: number;
  write_off_amount?: number;
  write_off_account?: string;
  docstatus?: number;
  references?: Ref[];
  deductions?: Deduction[];
};

/** A row from erpnext get_outstanding_reference_documents. */
type Outstanding = {
  voucher_type: string;
  voucher_no: string;
  invoice_amount: number;
  outstanding_amount: number;
  posting_date?: string;
  due_date?: string;
  currency?: string;
  payment_term?: string;
  payment_term_outstanding?: number;
  bill_no?: string;
};

type Resolved = {
  paid_from?: string; paid_to?: string;
  paid_from_account_currency?: string; paid_to_account_currency?: string;
  bank_account_type?: string; party_name?: string;
};

const sumAllocated = (refs: Ref[] | undefined) =>
  round2((refs ?? []).reduce((a, r) => a + (Number(r.allocated_amount) || 0), 0));

/**
 * One invoice can appear several times — get_outstanding_reference_documents
 * splits a row per payment term when the terms template asks for it
 * (payment_entry.py:2529). Identity is invoice + term, or the rows tick
 * together and collapse into a single allocation.
 */
const refKey = (r: { reference_doctype?: string; reference_name?: string; payment_term?: string }) =>
  `${r.reference_doctype ?? ""}|${r.reference_name ?? ""}|${r.payment_term ?? ""}`;
const rowKey = (r: Outstanding) =>
  refKey({
    reference_doctype: r.voucher_type,
    reference_name: r.voucher_no,
    payment_term: r.payment_term,
  });

export default function PaymentForm() {
  const { name = "new" } = useParams();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const session = useSession();
  const isNew = name === "new";

  const invoice = params.get("dn") || params.get("invoice") || "";
  const sourceDoctype = params.get("dt") || "";
  const urlParty = params.get("party") || "";
  const urlType = (params.get("type") === "Pay" ? "Pay" : "Receive") as PayType;

  const existing = useDoc<PayDoc>(DT.paymentEntry, isNew ? undefined : name, isNew ? null : name);
  const mapper = useFrappePostCall<{ message: PayDoc }>(METHOD.getPaymentEntry);
  const submitCall = useFrappePostCall(METHOD.submit);
  const create = useInsert();
  const update = useSave();
  const exchangeRateCall = useFrappePostCall<{ message: number }>(METHOD.getExchangeRate);
  const modes = useDocList<{ name: string; type?: string }>(DT.modeOfPayment, {
    fields: ["name", "type"],
    filters: [["enabled", "=", 1]],
    limit: 30,
  });

  const [doc, setDoc] = useState<PayDoc>({
    payment_type: urlType,
    party_type: PARTY_TYPE[urlType],
    party: urlParty || undefined,
    posting_date: toIsoDate(new Date()),
    paid_amount: 0,
    references: [],
  });
  /* True once the amount has been typed by hand. Until then it tracks the
     allocations, which is what makes the two agree by default.           */
  const [manualAmount, setManualAmount] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [sourceExchangeRate, setSourceExchangeRate] = useState(1);
  const [targetExchangeRate, setTargetExchangeRate] = useState(1);
  const [writeOffAmount, setWriteOffAmount] = useState(0);
  const [writeOffAccount, setWriteOffAccount] = useState("");
  const [deductions, setDeductions] = useState<Deduction[]>([]);

  const cur = session.currency || "";
  const type: PayType = doc.payment_type ?? "Receive";
  const partyType = PARTY_TYPE[type];
  const company = doc.company || session.company;
  const locked = (existing.data?.docstatus ?? 0) > 0;

  useEffect(() => {
    if (existing.data) {
      setDoc(existing.data);
      setManualAmount(true);
      setDeductions(
        (existing.data.deductions ?? []).map((d) => ({
          account: d.account || "",
          cost_center: d.cost_center || "",
          amount: Number(d.amount) || 0,
          description: d.description || "",
        })),
      );
    }
  }, [existing.data]);

  /* Both legs. The Payment Entry controller never reads mode_of_payment, so
     paid_from / paid_to have to be resolved and sent — see
     claude/payment-entry-api-verification.md §1.                          */
  const isInternalTransfer = type === "Internal Transfer";
  const accounts = useFrappeGetCall<{ message: Resolved }>(
    isInternalTransfer ? METHOD.resolveInternalTransferAccounts : METHOD.resolvePaymentAccounts,
    isInternalTransfer
      ? { company, mode_of_payment: doc.mode_of_payment }
      : { company, payment_type: type, mode_of_payment: doc.mode_of_payment, party_type: partyType, party: doc.party },
    company && doc.mode_of_payment && !locked && (isInternalTransfer || doc.party)
      ? `pay-accounts-${company}-${type}-${doc.mode_of_payment}-${doc.party ?? "xfr"}`
      : null,
    { shouldRetryOnError: false },
  );
  const resolved = accounts.data?.message;

  /* Reference No. is mandatory when the BANK LEG is a Bank account, and the
     bank leg swaps with the direction (payment_entry.py:1248). Reading the
     wrong leg on a Pay makes the guard silently stop working.             */
  const bankType = locked ? undefined : resolved?.bank_account_type;
  const refRequired = needsReference(bankType);

  const outstanding = useFrappeGetCall<{ message: Outstanding[] }>(
    METHOD.getOutstandingInvoices,
    { company, party_type: partyType, party: doc.party },
    locked || !doc.party || !company ? null : `pay-outstanding-${company}-${partyType}-${doc.party}`,
    { shouldRetryOnError: false },
  );

  /** Seed the plumbing from ERPNext's own mapper for the deep-link case. */
  const seedFrom = useCallback(
    async (sourceDoctype: string, voucherNo: string, current: PayDoc): Promise<PayDoc> => {
      const r = await mapper.call({ dt: sourceDoctype, dn: voucherNo });
      const m = r?.message;
      if (!m) throw new Error(t("pay.err.invoiceAccounts"));
      return {
        ...m,
        posting_date: current.posting_date || m.posting_date || toIsoDate(new Date()),
        mode_of_payment: current.mode_of_payment || m.mode_of_payment,
        reference_no: current.reference_no || m.reference_no,
        reference_date: current.reference_date || m.reference_date || m.posting_date,
      };
    },
    [mapper],
  );

  /* Deep link: /payments/new?invoice=SINV-0001 (§9 — nothing repeated). */
  const [seeded, setSeeded] = useState(false);
  useEffect(() => {
    if (!isNew || !invoice || seeded) return;
    let cancelled = false;
    void (async () => {
      try {
        const source = sourceDoctype || (urlType === "Pay" ? DT.purchaseInvoice : DT.salesInvoice);
        const next = await seedFrom(source, invoice, { posting_date: toIsoDate(new Date()) });
        if (cancelled) return;
        setDoc(next);
        setManualAmount(true);
        setSeeded(true);
      } catch (err) {
        if (!cancelled) { setSaveError(err); setSeeded(true); }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoice, isNew, seeded]);

  /** True when the two account legs use different currencies. */
  const isMcurr = !!(
    resolved?.paid_from_account_currency &&
    resolved?.paid_to_account_currency &&
    resolved.paid_from_account_currency !== resolved.paid_to_account_currency
  );

  /** Fetch exchange rates whenever the resolved accounts change currencies. */
  useEffect(() => {
    if (!isMcurr || !resolved) return;
    const companyCurrency = session.currency || "";
    const fromCur = resolved.paid_from_account_currency!;
    const toCur = resolved.paid_to_account_currency!;
    void (async () => {
      try {
        if (fromCur !== companyCurrency) {
          const r = await exchangeRateCall.call({ from_currency: fromCur, to_currency: companyCurrency, transaction_date: doc.posting_date, args: "for_buying" });
          setSourceExchangeRate(Number(r?.message) || 1);
        } else {
          setSourceExchangeRate(1);
        }
        if (toCur !== companyCurrency) {
          const r = await exchangeRateCall.call({ from_currency: toCur, to_currency: companyCurrency, transaction_date: doc.posting_date, args: "for_buying" });
          setTargetExchangeRate(Number(r?.message) || 1);
        } else {
          setTargetExchangeRate(1);
        }
      } catch { /* non-fatal */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMcurr, resolved?.paid_from_account_currency, resolved?.paid_to_account_currency, doc.posting_date]);

  const refs = useMemo(() => doc.references ?? [], [doc.references]);
  const allocated = sumAllocated(refs);
  const amount = round2(doc.paid_amount ?? 0);
  const receivedAmount = round2(isMcurr ? (doc.received_amount ?? 0) : amount);
  const deductionTotal = round2(deductions.reduce((s, d) => s + (Number(d.amount) || 0), 0));
  const unallocated = round2(
    type === "Pay"
      ? receivedAmount - deductionTotal - allocated
      : amount + deductionTotal - allocated,
  );
  const overAllocated = allocated > amount + 0.005;

  const selected = useMemo(() => new Set(refs.map(refKey)), [refs]);
  const byKey = useMemo(() => new Map(refs.map((r) => [refKey(r), r])), [refs]);

  const applyRefs = useCallback((next: Ref[]) => {
    setDoc((d) => ({
      ...d,
      references: next,
      ...(!manualAmount && !isMcurr ? { paid_amount: sumAllocated(next), received_amount: sumAllocated(next) } : {}),
    }));
  }, [manualAmount, isMcurr]);

  function toggleInvoice(row: Outstanding) {
    const key = rowKey(row);
    if (selected.has(key)) {
      applyRefs(refs.filter((r) => refKey(r) !== key));
      return;
    }
    const balance = row.payment_term
      ? Number(row.payment_term_outstanding ?? row.outstanding_amount)
      : Number(row.outstanding_amount);
    const addition: Ref = {
      reference_doctype: row.voucher_type,
      reference_name: row.voucher_no,
      payment_term: row.payment_term,
      allocated_amount: manualAmount ? autoAllocate(balance, amount - allocated) : round2(balance),
      outstanding_amount: round2(balance),
      total_amount: round2(row.invoice_amount),
      due_date: row.due_date,
      bill_no: row.bill_no,
    };
    applyRefs([...refs, addition]);
  }

  function setAllocation(key: string, value: number) {
    applyRefs(refs.map((r) => {
      if (refKey(r) !== key) return r;
      const bal = Number(r.outstanding_amount) || 0;
      const clamped = bal < 0
        ? Math.min(0, Math.max(value, bal))
        : Math.max(0, Math.min(value, bal));
      return { ...r, allocated_amount: round2(clamped) };
    }));
  }

  /** Changing the direction changes the party doctype and the whole book. */
  function setType(next: PayType) {
    if (next === type) return;
    setDoc((d) => ({
      payment_type: next,
      party_type: PARTY_TYPE[next],
      posting_date: d.posting_date,
      mode_of_payment: d.mode_of_payment,
      reference_date: d.reference_date,
      paid_amount: manualAmount ? d.paid_amount : 0,
      received_amount: manualAmount ? d.paid_amount : 0,
      company: d.company,
      references: [],
    }));
  }

  const canSubmit = canSubmitPayment(session.roles);
  const saveable =
    (isInternalTransfer || !!doc.party) && !!doc.mode_of_payment && !!doc.posting_date &&
    amount > 0 && !overAllocated &&
    (!refRequired || !!doc.reference_no) &&
    !!resolved;

  async function save(submitAfter: boolean) {
    setBusy(true); setSaveError(null);
    try {
      if (!resolved) throw new Error(t("pay.err.noAccounts"));
      if (overAllocated) {
        throw new Error(`${t("pay.warn.over")} — ${money(allocated)} / ${money(amount)}`);
      }
      const body: Record<string, unknown> = {
        ...doc,
        payment_type: type,
        party_type: isInternalTransfer ? undefined : partyType,
        company,
        paid_amount: amount,
        received_amount: isMcurr ? receivedAmount : amount,
        paid_from: resolved.paid_from,
        paid_to: resolved.paid_to,
        paid_from_account_currency: resolved.paid_from_account_currency,
        paid_to_account_currency: resolved.paid_to_account_currency,
        ...(isMcurr ? { source_exchange_rate: sourceExchangeRate, target_exchange_rate: targetExchangeRate } : {}),
        references: refs.filter((r) => (Number(r.allocated_amount) || 0) !== 0),
        deductions: deductions.filter((d) => d.account && d.amount),
        ...(writeOffAmount > 0.005 && writeOffAccount
          ? { write_off_amount: writeOffAmount, write_off_account: writeOffAccount }
          : {}),
      };
      let payName: string;
      if (isNew) {
        const created = await create.createDoc(DT.paymentEntry, body);
        payName = (created as { name: string }).name;
      } else {
        await update.updateDoc(DT.paymentEntry, name, body);
        payName = name;
      }
      /* workflow.submit re-reads the document from the database, so the save
         above has to land first — sending a submit with unsaved changes
         would silently post the previous values.                         */
      if (submitAfter && canSubmit) {
        await submitCall.call({ doc: { doctype: DT.paymentEntry, name: payName } });
      }
      nav(`/payments/${encodeURIComponent(payName)}`);
    } catch (err) { setSaveError(err); }
    finally { setBusy(false); }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  /* A submitted payment has posted to the ledger. Everything after that
     lives on the read-only screen. */
  if (!isNew && existing.data && existing.data.docstatus !== 0) {
    return <Navigate to={`/payments/${encodeURIComponent(name)}`} replace />;
  }

  const rows = outstanding.data?.message ?? [];
  const checks: Check[] = [
    { ok: !!type, label: t("pay.check.type") },
    ...(isInternalTransfer ? [] : [{ ok: !!doc.party, label: t("pay.check.party") }]),
    { ok: !!doc.posting_date, label: t("pay.check.date") },
    { ok: amount > 0, label: t("pay.check.amount") },
    { ok: !!doc.mode_of_payment, label: t("pay.check.mode") },
    ...(refRequired ? [{ ok: !!doc.reference_no, label: t("pay.check.ref") }] : []),
  ];

  return (
    <>
      <PageHead
        eyebrow={
          <>
            <button type="button" className="btn quiet" onClick={() => nav("/payments")}>
              {t("nav.payments")}
            </button>{" / "}{isNew ? t(`pay.new${type === "Pay" ? "Out" : ""}`) : name}
          </>
        }
        title={isNew ? t(`pay.new${type === "Pay" ? "Out" : ""}`) : name}
        actions={
          <FormActions
            onDiscard={() => nav("/payments")}
            onSave={() => void save(false)}
            onSubmit={canSubmit ? () => void save(true) : undefined}
            busy={busy} ready={saveable} submitLabel={t("pay.submit")} />
        }
      />

      {(saveError || mapper.error || submitCall.error || accounts.error) && (
        <ErrorBox error={saveError || mapper.error || submitCall.error || accounts.error} />
      )}


      <FormLayout aside={
        <>
          <Card bodyClass="cbody">
            <h2 style={{ margin: "0 0 13px", fontSize: 13.5, fontWeight: 600 }}>{t("pay.sumTitle")}</h2>
            <div className="srow">
              <span className="k">{t("pay.sAmount")}</span>
              <span className="v"><span className="cur">{cur}</span>{money(amount)}</span>
            </div>
            <div className="srow">
              <span className="k">{t("pay.allocated")}</span>
              <span className="v"><span className="cur">{cur}</span>{money(allocated)}</span>
            </div>
            <div className={`srow rule ${overAllocated ? "over" : "left"} ${Math.abs(unallocated) < 0.005 ? "zero" : ""}`}>
              <span className="k">{t("pay.unallocated")}</span>
              <span className="v"><span className="cur">{cur}</span>{money(unallocated)}</span>
            </div>
            <div className="allocbar">
              <i style={{ width: `${amount ? Math.min(100, (allocated / amount) * 100) : 0}%`, background: "var(--c-billed)" }} />
              <i style={{ width: `${amount ? Math.max(0, Math.min(100, (unallocated / amount) * 100)) : 0}%`, background: "var(--warn)" }} />
            </div>
          </Card>

          <ReadinessCard checks={checks} title={t("pay.ready")} />
        </>
      }>
          <Card title={<><span className="snum">1</span>{t("pay.b1")}</>}>
            <div className="f" style={{ marginBlockEnd: 14 }}>
              <label>{t("pay.lType")} <span className="req">*</span></label>
              <div className="seg" role="group" aria-label={t("pay.lType")}>
                {(["Receive", "Pay", "Internal Transfer"] as PayType[]).map((x) => (
                  <button key={x} type="button" aria-pressed={type === x} onClick={() => setType(x)}>
                    <span className={`dot ${x === "Receive" ? "in" : x === "Pay" ? "out" : "xfr"}`} />
                    {x === "Internal Transfer" ? t("pay.internal") : t(`pay.type.${x}`)}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid2">
              {!isInternalTransfer && (
                <Field label={t(`pay.party.${partyType ?? "Customer"}`)} required>
                  <LinkField doctype={partyType === "Supplier" ? DT.supplier : DT.customer}
                    value={doc.party ?? ""}
                    onChange={(v) => setDoc((d) => ({ ...d, party: v, references: [] }))} />
                </Field>
              )}
              <Field label={t("pay.lDate")} required>
                <input className="ctl" type="date" value={doc.posting_date ?? ""}
                  onChange={(e) => setDoc((d) => ({ ...d, posting_date: e.target.value }))} />
              </Field>
            </div>
          </Card>

          <Card title={<><span className="snum">2</span>{t("pay.b2")}</>}>
            <div className="grid2">
              <Field label={isMcurr ? `${t("pay.lAmount")} (${resolved?.paid_from_account_currency ?? cur})` : `${t("pay.lAmount")} (${cur})`} required>
                <input className="ctl nn" value={doc.paid_amount ?? 0}
                  onChange={(e) => {
                    const v = parseNum(e.target.value);
                    setManualAmount(true);
                    setDoc((d) => ({ ...d, paid_amount: v, ...(!isMcurr ? { received_amount: v } : {}) }));
                  }} />
              </Field>
              {isMcurr && (
                <Field label={`${t("pay.receivedAmount")} (${resolved?.paid_to_account_currency ?? cur})`} required>
                  <input className="ctl nn" value={doc.received_amount ?? 0}
                    onChange={(e) => {
                      const v = parseNum(e.target.value);
                      setManualAmount(true);
                      setDoc((d) => ({ ...d, received_amount: v }));
                    }} />
                </Field>
              )}
              {isMcurr && (
                <Field label={t("pay.sourceRate")}>
                  <input className="ctl nn" value={sourceExchangeRate}
                    onChange={(e) => setSourceExchangeRate(parseNum(e.target.value) || 1)} />
                </Field>
              )}
              {isMcurr && (
                <Field label={t("pay.targetRate")}>
                  <input className="ctl nn" value={targetExchangeRate}
                    onChange={(e) => setTargetExchangeRate(parseNum(e.target.value) || 1)} />
                </Field>
              )}
              <Field label={t("pay.mode")} required>
                <select className="ctl" value={doc.mode_of_payment ?? ""}
                  onChange={(e) => setDoc((d) => ({ ...d, mode_of_payment: e.target.value }))}>
                  <option value="" />
                  {(modes.data ?? []).map((m) => (
                    <option key={m.name} value={m.name}>{m.name}{m.type ? ` · ${m.type}` : ""}</option>
                  ))}
                </select>
              </Field>
              <Field label={t("pay.refNo")} required={refRequired}>
                <input className="ctl" value={doc.reference_no ?? ""}
                  onChange={(e) => setDoc((d) => ({ ...d, reference_no: e.target.value }))} />
              </Field>
              <Field label={t("pay.refDate")}>
                <input className="ctl" type="date" value={doc.reference_date ?? ""}
                  onChange={(e) => setDoc((d) => ({ ...d, reference_date: e.target.value }))} />
              </Field>
            </div>
            {accounts.isLoading && (
              <p className="specnote" style={{ padding: "10px 0 0" }}>{t("pay.resolving")}</p>
            )}
          </Card>

          <Card title={<><span className="snum">3</span>{t("pay.b3")}</>}
                bodyClass={null as unknown as string}>
            {isInternalTransfer ? <Empty label={t("pay.internal")} /> : !doc.party ? <Empty label={t("pay.emptyParty")} />
              : outstanding.isLoading ? <Loading />
              : outstanding.error ? <ErrorBox error={outstanding.error} onRetry={() => outstanding.mutate()} />
              : rows.length === 0 ? (
                <div className="empty">
                  {t("pay.emptyNone")}
                  {/* A supplier on hold returns an empty list with no message
                      (payment_entry.py:2328), so name the possibility. */}
                  {type === "Pay" && <div style={{ marginTop: 6 }}>{t("pay.holdHint")}</div>}
                </div>
              ) : (
                /* An allocation table, not a list of item lines: the rows are
                   the party's outstanding invoices, so none can be added or
                   removed here — only ticked and allocated against. The
                   invoice names the row; the outstanding balance and the
                   allocation are on the face of a phone card. */
                <LineItems<Outstanding>
                  rows={rows}
                  rowClass={(r) => (selected.has(rowKey(r)) ? "picked" : undefined)}
                  fields={[
                    {
                      /* On the card face, not behind "More": this tick is what
                         enables the allocation input beside it, so hiding it
                         leaves a disabled field with no visible way to enable
                         it — the same trap the journal's required party hit. */
                      key: "pick", label: t("list.selectAll"), slot: "primary",
                      /* The column heading was blank before and stays blank:
                         "Select all" is the card's label for the tick, not a
                         new desktop column heading. */
                      thLabel: "", thClass: "pick", tdClass: "pick",
                      render: (r) => (
                        <input type="checkbox" checked={selected.has(rowKey(r))} aria-label={r.voucher_no}
                          onChange={() => toggleInvoice(r)} />
                      ),
                    },
                    {
                      key: "inv", label: t("pay.aInv"), slot: "title", tdClass: "inv",
                      render: (r) => (
                        <div className="inv">
                          <b>{r.voucher_no}</b>
                          <span>
                            {date(r.posting_date)}
                            {/* The supplier's own invoice number — the
                                thing an AP clerk matches against. */}
                            {r.bill_no ? ` · ${r.bill_no}` : ""}
                            {r.payment_term ? ` · ${r.payment_term}` : ""}
                          </span>
                        </div>
                      ),
                    },
                    {
                      key: "due", label: t("pay.aDue"), tdClass: "dt",
                      render: (r) => <span className="dt">{date(r.due_date)}</span>,
                    },
                    {
                      key: "out", label: t("pay.aOut"), numeric: true,
                      render: (r) => (
                        <span>{money(r.payment_term
                          ? Number(r.payment_term_outstanding ?? r.outstanding_amount)
                          : Number(r.outstanding_amount))}</span>
                      ),
                    },
                    {
                      key: "alloc", label: t("pay.aAlloc"), slot: "primary", numeric: true,
                      th: { width: 150 },
                      render: (r) => {
                        const key = rowKey(r);
                        return (
                          <input className="ctl mini nn" style={{ width: 130 }} disabled={!selected.has(key)}
                            value={byKey.get(key)?.allocated_amount ?? 0}
                            onChange={(e) => setAllocation(key, parseNum(e.target.value))} />
                        );
                      },
                    },
                  ] as LineField<Outstanding>[]}
                  /* The allocated total the table carried in its <tfoot>. */
                  footer={
                    <tr>
                      <td colSpan={4} className="n">{t("pay.allocated")}</td>
                      <td className="n">{money(allocated)}</td>
                    </tr>
                  }
                  footerCard={<><span>{t("pay.allocated")}</span><span>{money(allocated)}</span></>}
                />
              )}
          </Card>

          <Card title={t("pay.deductions")}>
            {deductions.map((d, i) => (
              <div className="grid2" key={i}>
                <Field label={t("pay.writeOffAccount")}>
                  <LinkField doctype={DT.account} value={d.account}
                    onChange={(v) => setDeductions((rows) => rows.map((r, j) => j === i ? { ...r, account: v } : r))}
                    filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined} />
                </Field>
                <Field label={t("pay.writeOffAmount")}>
                  <input className="ctl nn" value={d.amount}
                    onChange={(e) => setDeductions((rows) => rows.map((r, j) => j === i ? { ...r, amount: parseNum(e.target.value) } : r))} />
                </Field>
              </div>
            ))}
            <button type="button" className="btn ghost sm" onClick={() => setDeductions((rows) => [...rows, { account: "", cost_center: "", amount: 0, description: "" }])}>
              {t("pay.deductAdd")}
            </button>
          </Card>

          {overAllocated && (
            <div className="alert bad">
              <span className="ic">!</span>
              <span><b>{t("pay.warn.over")}</b>{t("pay.warn.overB")}</span>
            </div>
          )}
          {!overAllocated && unallocated > 0.005 && amount > 0 && (
            <>
              <div className="alert">
                <span className="ic">!</span>
                <span>
                  <b>{t("pay.warn.left")} — {cur} {money(unallocated)}</b>
                  {t("pay.warn.leftB")}
                </span>
              </div>
              <Card title={t("pay.writeOff")}>
                <div className="grid2">
                  <Field label={t("pay.writeOffAmount")}>
                    <input className="ctl nn" value={writeOffAmount}
                      onChange={(e) => setWriteOffAmount(parseNum(e.target.value))} />
                  </Field>
                  <Field label={t("pay.writeOffAccount")}>
                    <LinkField
                      doctype={DT.account}
                      value={writeOffAccount}
                      onChange={setWriteOffAccount}
                      filters={company ? [["company", "=", company], ["is_group", "=", 0]] : undefined}
                    />
                  </Field>
                </div>
              </Card>
            </>
          )}
      </FormLayout>
    </>
  );
}
