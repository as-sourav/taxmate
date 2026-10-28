/**
 * Material Request detail.
 * Importers: App.tsx route /material-requests/:name.
 * API: taxmate.api.resource.get on Material Request; taxmate.api.material_request.make_purchase_order / make_stock_entry.
 * Schema: name, material_request_type, transaction_date, schedule_date, status, docstatus, items[{item_code,qty,warehouse}].
 * User: "Implement the plan as specified… complete all the to-dos."
 */
import { useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "../../lib/frappe";
import { useOpenMapped } from "../../lib/openMapped";
import { confirmCancel } from "../../lib/workflow";
import { useDeleteDraftAction } from "../../lib/useDraftDelete";
import { useDoc, useInsert } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { canCancelSales, canSubmitSales } from "../../lib/roles";
import { date, qty } from "../../lib/format";
import { t } from "../../i18n/strings";
import { Card, ErrorBox, Field, Loading, PageHead, Pill, ReadRow } from "../../components/ui";
import DocHistory from "../../components/DocHistory";
import { FormLayout } from "../../components/form";
import LinkField from "../../components/LinkField";
import LineItems, { type LineField } from "../../components/LineItems";

type Line = {
  item_code?: string; item_name?: string; qty?: number; uom?: string; warehouse?: string;
  schedule_date?: string; ordered_qty?: number; received_qty?: number;
  stock_qty?: number; picked_qty?: number;
};
type Doc = {
  name: string; material_request_type?: string; transaction_date?: string; schedule_date?: string;
  status?: string; docstatus?: number; company?: string; customer?: string;
  set_warehouse?: string; set_from_warehouse?: string; buying_price_list?: string;
  per_ordered?: number; per_received?: number; tc_name?: string; terms?: string;
  items?: Line[];
};
type PendingRow = {
  material_request_item: string;
  item_code: string;
  item_name?: string;
  pending_qty: number;
  uom?: string;
  supplier: string;
  qty: number;
};

function termsHtml(raw?: string) {
  return (raw || "").replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
}

function mrPill(status?: string): string {
  if (status === "Cancelled" || status === "Stopped") return "p-cxl";
  if (status === "Ordered" || status === "Transferred" || status === "Issued") return "p-done";
  if (status === "Pending") return "p-open";
  return "p-draft";
}

export default function MaterialRequestDetail() {
  const { name = "" } = useParams();
  const deleteAction = useDeleteDraftAction({ doctype: DT.materialRequest, name, listPath: "/material-requests" });
  const nav = useNavigate();
  const session = useSession();
  const { data, error, isLoading, mutate } = useDoc<Doc>(DT.materialRequest, name);
  const submitCall = useFrappePostCall(METHOD.submit);
  const cancelCall = useFrappePostCall(METHOD.cancel);
  const amendCall = useFrappePostCall<{ message?: { name?: string } }>(METHOD.amend);
  const makePO = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeMrPO);
  const suppliersCall = useFrappePostCall<{ message: Omit<PendingRow, "qty">[] }>(METHOD.mrDefaultSuppliers);
  const makeMany = useFrappePostCall<{ message: string[] }>(METHOD.makeMrPOs);
  const makeSE = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeMrSE);
  const makeSq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeMrSupplierQuotation);
  const makeRfq = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeRfqFromMaterialRequest);
  const rfq = useOpenMapped("/request-for-quotations");
  const makePick = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.makeMrPickList);
  const makeWo = useFrappePostCall<{ message: { names?: string[] } }>(METHOD.makeMrWorkOrders);
  const stopCall = useFrappePostCall(METHOD.setMaterialRequestStatus);
  const create = useInsert();
  const [busy, setBusy] = useState<"" | "po" | "se" | "sq" | "pick" | "wo">("");
  const [mapError, setMapError] = useState<unknown>(null);
  const [poRows, setPoRows] = useState<PendingRow[] | null>(null);
  const [tab, setTab] = useState<"details" | "terms" | "more">("details");
  const canSubmit = canSubmitSales(session.roles);
  const canCancel = canCancelSales(session.roles);

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const draft = data.docstatus === 0;
  const submitted = data.docstatus === 1;
  const isPurchase = data.material_request_type === "Purchase" || data.material_request_type === "Subcontracting";
  const openOrder = submitted && data.status !== "Stopped" && (data.per_ordered ?? 0) < 100;
  const canStop = submitted && data.status !== "Stopped" && (data.per_received ?? 0) < 100;
  const canPick = openOrder && data.material_request_type === "Material Transfer"
    && (data.items ?? []).some((row) => Number(row.stock_qty) > Number(row.picked_qty || 0));
  const canManufacture = openOrder && data.material_request_type === "Manufacture";
  const isTransferOrIssue = data.material_request_type === "Material Transfer"
    || data.material_request_type === "Material Issue"
    || data.material_request_type === "Customer Provided";

  async function openPurchaseOrder(supplier?: string) {
    const res = await makePO.call({ source_name: name, supplier: supplier || undefined });
    const mapped = res?.message;
    if (!mapped) throw new Error(t("txn.mapEmpty"));
    const body: Record<string, unknown> = { ...mapped };
    delete body.name;
    delete body.doctype;
    delete body.__islocal;
    delete body.__unsaved;
    nav("/purchase-orders/new", { state: { mapped: body } });
  }

  async function startPurchaseOrder() {
    setBusy("po");
    setMapError(null);
    try {
      const res = await suppliersCall.call({ source_name: name });
      const items = res?.message ?? [];
      if (!items.length) {
        setMapError(new Error(t("mr.nothingToOrder")));
        return;
      }
      const suppliers = new Set(items.map((row) => row.supplier || ""));
      if (suppliers.size > 1) {
        setPoRows(items.map((row) => ({
          ...row,
          supplier: row.supplier || "",
          qty: Number(row.pending_qty) || 0,
        })));
        return;
      }
      await openPurchaseOrder(items[0]?.supplier || undefined);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  async function createFromSuppliers() {
    if (!poRows?.length) return;
    setBusy("po");
    setMapError(null);
    try {
      const res = await makeMany.call({
        source_name: name,
        item_suppliers: poRows.map((row) => ({
          material_request_item: row.material_request_item,
          item_code: row.item_code,
          supplier: row.supplier,
          qty: row.qty,
        })),
      });
      const names = res?.message ?? [];
      setPoRows(null);
      if (names[0]) nav(`/purchase-orders/${encodeURIComponent(names[0])}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  async function createPickList() {
    setBusy("pick");
    setMapError(null);
    try {
      const res = await makePick.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("txn.mapEmpty"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name; delete body.doctype; delete body.__islocal; delete body.__unsaved;
      const created = await create.createDoc(DT.pickList, body) as { name: string };
      nav(`/pick-lists/${encodeURIComponent(created.name)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  async function createWorkOrders() {
    setBusy("wo");
    setMapError(null);
    try {
      const res = await makeWo.call({ source_name: name });
      const next = res?.message?.names?.[0];
      if (!next) throw new Error(t("txn.mapEmpty"));
      nav(`/work-orders/${encodeURIComponent(next)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  async function stopRequest() {
    setMapError(null);
    try {
      await stopCall.call({ name, status: "Stopped" });
      await mutate();
    } catch (err) {
      setMapError(err);
    }
  }

  async function createSupplierQuotation() {
    setBusy("sq");
    setMapError(null);
    try {
      const res = await makeSq.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("txn.mapEmpty"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      nav("/supplier-quotations/new", { state: { mapped: body } });
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  async function createStockEntry() {
    setBusy("se");
    setMapError(null);
    try {
      const res = await makeSE.call({ source_name: name });
      const mapped = res?.message;
      if (!mapped) throw new Error(t("txn.mapEmpty"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.doctype;
      delete body.__islocal;
      delete body.__unsaved;
      const created = await create.createDoc(DT.stockEntry, body);
      nav(`/stock-entries/${encodeURIComponent((created as { name: string }).name)}`);
    } catch (err) {
      setMapError(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav("/material-requests")}>{t("nav.materialRequests")}</button>}
        title={data.material_request_type || data.name}
        actions={
          <>
            <DocHistory doctype={DT.materialRequest} name={name} />
            {draft && (
              <>
                <button type="button" className="btn ghost"
                  onClick={() => nav(`/material-requests/${encodeURIComponent(name)}/edit`)}>{t("inv.edit")}</button>
                <button type="button" className="btn quiet" disabled={deleteAction.loading}
                  onClick={deleteAction.onDelete}>
                  {deleteAction.loading ? t("soc.saving") : t("inv.delete")}
                </button>
              </>
            )}
            {draft && canSubmit && (
              <button type="button" className="btn" disabled={submitCall.loading}
                onClick={() => void submitCall.call({ doc: { doctype: DT.materialRequest, name } }).then(() => mutate()).catch(() => undefined)}>
                {t("inv.submit")}
              </button>
            )}
            {submitted && isPurchase && (
              <button type="button" className="btn" disabled={!!busy}
                onClick={() => void startPurchaseOrder()}>
                {busy === "po" ? t("soc.saving") : t("mr.makePO")}
              </button>
            )}
            {submitted && data.material_request_type === "Purchase" && data.status !== "Stopped" && (data.per_ordered ?? 0) < 100 && (
              <>
              <button type="button" className="btn ghost" disabled={!!busy}
                onClick={() => void createSupplierQuotation()}>
                {busy === "sq" ? t("soc.saving") : t("nav.supplierQuotations")}
              </button>
              <button type="button" className="btn ghost" disabled={!!busy || rfq.busy}
                onClick={() => void rfq.open(() => makeRfq.call({ source_name: name }))}>
                Request for Quotation
              </button>
              </>
            )}
            {canPick && (
              <button type="button" className="btn ghost" disabled={!!busy} onClick={() => void createPickList()}>
                {busy === "pick" ? t("soc.saving") : t("nav.pickLists")}
              </button>
            )}
            {canManufacture && (
              <button type="button" className="btn ghost" disabled={!!busy} onClick={() => void createWorkOrders()}>
                {busy === "wo" ? t("soc.saving") : t("nav.workOrders")}
              </button>
            )}
            {canStop && (
              <button type="button" className="btn quiet" disabled={stopCall.loading} onClick={() => void stopRequest()}>
                Stop
              </button>
            )}
            {submitted && isTransferOrIssue && (
              <button type="button" className="btn ghost" disabled={!!busy}
                onClick={() => void createStockEntry()}>
                {busy === "se" ? t("soc.saving") : t("mr.makeSE")}
              </button>
            )}
            {submitted && canCancel && (
              <button type="button" className="btn quiet" disabled={cancelCall.loading}
                onClick={() => {
                  if (!confirmCancel(name)) return;
                  void cancelCall.call({ doctype: DT.materialRequest, name }).then(() => mutate()).catch(() => undefined);
                }}>
                {t("inv.cancel")}
              </button>
            )}
            {data.docstatus === 2 && canSubmit && (
              <button type="button" className="btn ghost" disabled={amendCall.loading}
                onClick={() => void amendCall.call({ doctype: DT.materialRequest, name }).then((res) => {
                  const next = res?.message?.name;
                  if (next) nav(`/material-requests/${encodeURIComponent(next)}`);
                  else mutate();
                }).catch(() => undefined)}>
                {amendCall.loading ? t("soc.saving") : t("inv.amend")}
              </button>
            )}
          </>
        }
      >
        <p className="sub" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 7 }}>
          <span className="ordno">{data.name}</span>
          <Pill cls={mrPill(data.status)}>{data.status || t("pay.status.Draft")}</Pill>
        </p>
      </PageHead>

      {(submitCall.error || cancelCall.error || amendCall.error || mapError || rfq.error) && (
        <ErrorBox error={submitCall.error || cancelCall.error || amendCall.error || mapError || rfq.error} />
      )}

      <div className="ftabs" role="tablist">
        {(["details", "terms", "more"] as const).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`ftab${tab === id ? " on" : ""}`}
            onClick={() => setTab(id)}
          >
            {t(id === "details" ? "mr.tab.details" : id === "terms" ? "mr.tab.terms" : "mr.tab.more")}
          </button>
        ))}
      </div>

      <FormLayout>
        {tab === "details" && (
          <>
            <Card>
              <div className="fg">
                <ReadRow k={t("mr.purpose")} v={data.material_request_type || "—"} />
                <ReadRow k={t("quot.date")} v={date(data.transaction_date)} />
                <ReadRow k={t("mr.requiredBy")} v={date(data.schedule_date)} />
                <ReadRow k={t("mr.company")} v={data.company || "—"} />
                <ReadRow k={t("mr.targetWarehouse")} v={data.set_warehouse || "—"} />
                {data.set_from_warehouse ? <ReadRow k={t("se.warehouse.from")} v={data.set_from_warehouse} /> : null}
                {data.customer ? <ReadRow k={t("mr.customer")} v={data.customer} /> : null}
              </div>
            </Card>
            <Card title={t("mr.items")}>
              {/* Read-only: the request's lines cannot be added or removed here.
                  The requested and the completed quantity are the pair a reader
                  compares, so both take the card face; UOM, warehouse and the
                  required-by date sit below, still visible with collapse off. */}
              <LineItems<Line>
                rows={data.items ?? []}
                showIndex
                collapse={false}
                fields={[
                  {
                    key: "item", label: t("soc.pickItem"), slot: "title",
                    render: (l) => (
                      <><div className="icode">{l.item_code}</div><div className="iname">{l.item_name}</div></>
                    ),
                  },
                  {
                    key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                    render: (l) => <>{qty(l.qty)}</>,
                  },
                  {
                    key: "uom", label: t("mr.uom"),
                    render: (l) => <>{l.uom || "—"}</>,
                  },
                  {
                    key: "warehouse", label: t("mr.targetWarehouse"),
                    render: (l) => <>{l.warehouse || "—"}</>,
                  },
                  {
                    key: "requiredBy", label: t("mr.requiredBy"),
                    render: (l) => <>{date(l.schedule_date || data.schedule_date)}</>,
                  },
                  {
                    key: "completedQty", label: t("mr.completedQty"), slot: "primary", numeric: true,
                    render: (l) => <>{qty(l.ordered_qty)}</>,
                  },
                ] as LineField<Line>[]}
              />
            </Card>
          </>
        )}
        {tab === "terms" && (
          <Card title={t("mr.tab.terms")}>
            {data.tc_name ? <ReadRow k={t("mr.tab.terms")} v={data.tc_name} /> : null}
            {data.terms
              ? <div dangerouslySetInnerHTML={{ __html: termsHtml(data.terms) }} />
              : <p className="sub">{t("mr.termsEmpty")}</p>}
          </Card>
        )}
        {tab === "more" && (
          <Card title={t("mr.tab.more")}>
            <div className="fg">
              <ReadRow k={t("mr.col.status")} v={data.status || "—"} />
              <ReadRow k={t("mr.ordered")} v={`${Number(data.per_ordered || 0)}%`} />
              <ReadRow k={t("mr.received")} v={`${Number(data.per_received || 0)}%`} />
              <ReadRow k={t("mr.priceList")} v={data.buying_price_list || "—"} />
              <ReadRow k={t("mr.company")} v={data.company || "—"} />
            </div>
          </Card>
        )}
      </FormLayout>

      {poRows && createPortal(
        <div className="msgdlg-back" onMouseDown={() => setPoRows(null)}>
          <div
            className="msgdlg wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mr-supplier-title"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="msgdlg-head">
              <h2 id="mr-supplier-title">{t("mr.supplierForItems")}</h2>
              <button type="button" className="msgdlg-x" aria-label={t("m.close")} onClick={() => setPoRows(null)}>×</button>
            </div>
            <div className="msgdlg-body">
              <Field label={t("mr.setSupplierAll")}>
                <LinkField
                  doctype={DT.supplier}
                  value=""
                  onChange={(supplier) => {
                    if (!supplier) return;
                    setPoRows((rows) => rows?.map((row) => ({ ...row, supplier })) ?? rows);
                  }}
                />
              </Field>
              <p className="sub">{t("mr.separatePO")}</p>
              {/* Not a line table but a per-item supplier split: the rows come
                  back from mrDefaultSuppliers, so none can be added or removed
                  here — only the quantity and the supplier are editable. With
                  collapse off, the supplier picker stays on the phone card
                  rather than behind a "More" toggle it would be useless behind. */}
              <LineItems<PendingRow>
                rows={poRows}
                collapse={false}
                fields={[
                  {
                    key: "item", label: t("soc.pickItem"), slot: "title",
                    render: (row) => (
                      <>
                        <div className="icode">{row.item_code}</div>
                        <div className="iname">{row.item_name}</div>
                      </>
                    ),
                  },
                  {
                    key: "qty", label: t("sod.col.qty"), slot: "primary", numeric: true,
                    render: (row) => (
                      <input
                        className="ctl mini nn"
                        style={{ width: 80 }}
                        value={row.qty}
                        onChange={(e) => {
                          const next = Number(e.target.value);
                          setPoRows((rows) => rows?.map((item) => (
                            item.material_request_item === row.material_request_item
                              ? { ...item, qty: Number.isFinite(next) ? next : 0 }
                              : item
                          )) ?? rows);
                        }}
                      />
                    ),
                  },
                  {
                    key: "uom", label: t("mr.uom"),
                    render: (row) => <>{row.uom || "—"}</>,
                  },
                  {
                    key: "supplier", label: t("nav.suppliers"), td: { minWidth: 180 },
                    render: (row) => (
                      <LinkField
                        doctype={DT.supplier}
                        value={row.supplier}
                        onChange={(supplier) => setPoRows((rows) => rows?.map((item) => (
                          item.material_request_item === row.material_request_item ? { ...item, supplier } : item
                        )) ?? rows)}
                      />
                    ),
                  },
                ] as LineField<PendingRow>[]}
              />
              <div className="addrow">
                <button type="button" className="btn" disabled={!!busy} onClick={() => void createFromSuppliers()}>
                  {busy === "po" ? t("soc.saving") : t("mr.create")}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
