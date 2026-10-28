/**
 * Draft form for one of the eight Desk documents.
 * Callers: App.tsx /new and /:name/edit. Mapped creates arrive in location.state.mapped.
 * API: taxmate.api.resource.insert / save.
 * User: build Opportunity, Request for Quotation, Shipment, Installation Note,
 * Delivery Trip, Payment Request, and the two subcontracting documents.
 */
import { useEffect, useRef, useState } from "react";
import { useFrappePostCall } from "frappe-react-sdk";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import LinkField from "../../components/LinkField";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { t } from "../../i18n/strings";
import { METHOD } from "../../lib/frappe";
import { stripForInsert } from "../../lib/openMapped";
import { useInsert, useSave, useDoc } from "../../lib/resource";
import { useSession } from "../../lib/session";
import { REGISTERS, type FieldSpec } from "./config";

type Line = { item_code?: string; qty?: number; item_name?: string; name?: string; delivery_note?: string; customer?: string; address?: string };
type SupplierRow = { supplier?: string; name?: string; contact?: string; email_id?: string };
type ParcelRow = { weight?: number; count?: number; name?: string };
type StopRow = { customer?: string; address?: string; name?: string };

function textOf(doc: Record<string, unknown>, key: string): string {
  const value = doc[key];
  return value == null ? "" : String(value);
}

function localDateTime(value: string): string {
  if (!value) return "";
  return value.replace(" ", "T").slice(0, 16);
}

function frappeDateTime(value: string): string {
  if (!value) return "";
  const normalized = value.replace("T", " ");
  return normalized.length === 16 ? `${normalized}:00` : normalized;
}

export default function RegisterForm({ specKey }: { specKey: string }) {
  const spec = REGISTERS[specKey];
  const { name = "" } = useParams();
  const isNew = !name;
  const nav = useNavigate();
  const location = useLocation();
  const session = useSession();
  const existing = useDoc<Record<string, unknown>>(spec.doctype, isNew ? undefined : name);
  const create = useInsert();
  const save = useSave();
  const partyCall = useFrappePostCall<{ message?: { contact_person?: string; contact_email?: string } }>(METHOD.getPartyDetails);
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  const applied = useRef("");

  const mapped = (location.state as { mapped?: Record<string, unknown> } | null)?.mapped;
  const loaded = existing.data;
  const seedKey = !isNew
    ? (loaded ? `${name}:${String(loaded.modified || "loaded")}` : "")
    : mapped
      ? "mapped"
      : `blank:${session.company || ""}:${session.today || ""}`;

  useEffect(() => {
    if (!seedKey || applied.current === seedKey) return;
    applied.current = seedKey;
    if (!isNew) {
      if (loaded) setDraft({ ...loaded });
      return;
    }
    if (mapped) {
      setDraft({ ...mapped });
      return;
    }
    setDraft({
      company: session.company || "",
      status: spec.doctype === "Opportunity" ? "Open" : undefined,
      opportunity_from: spec.doctype === "Opportunity" ? "Customer" : undefined,
      transaction_date: session.today || "",
      inst_date: session.today || "",
      pickup_date: session.today || "",
      suppliers: spec.suppliers ? [{ supplier: "" }] : undefined,
      items: spec.editLines ? [] : undefined,
    });
    // seedKey is the signature. Typing must not reload the draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedKey]);

  function setField(key: string, value: string) {
    setDraft((current) => ({
      ...(current || {}),
      [key]: value,
      ...(key === "opportunity_from" ? { party_name: "" } : {}),
    }));
  }

  const lines = (draft?.items as Line[] | undefined) ?? [];
  const suppliers = (draft?.suppliers as SupplierRow[] | undefined) ?? [];
  const partyDoctype = textOf(draft || {}, "opportunity_from") === "Lead" ? "Lead" : "Customer";

  async function onSave() {
    if (!draft) return;
    const missing = spec.fields.find((field) => field.required && !textOf(draft, field.key).trim());
    if (missing) {
      setSaveError(new Error(`${missing.label} is required`));
      return;
    }
    if (spec.suppliers && !suppliers.some((row) => row.supplier)) {
      setSaveError(new Error("Supplier is required"));
      return;
    }
    if (spec.doctype === "Opportunity" && lines.some((row) => row.item_code && !(Number(row.qty) > 0))) {
      setSaveError(new Error("Quantity must be greater than 0"));
      return;
    }
    const stops = (draft.delivery_stops as StopRow[] | undefined) ?? [];
    if (spec.linesKey === "delivery_stops" && stops.some((row) => !String(row.address || "").trim())) {
      setSaveError(new Error("Address is required"));
      return;
    }
    const parcels = (draft.shipment_parcel as ParcelRow[] | undefined) ?? [];
    if (spec.doctype === "Shipment" && parcels.some((row) => !(Number(row.weight) > 0) || !(Number(row.count) > 0))) {
      setSaveError(new Error("Parcel weight and count are required"));
      return;
    }
    setSaveError(null);
    try {
      if (isNew) {
        const created = await create.createDoc(spec.doctype, stripForInsert(draft));
        const createdName = String((created as { name?: string }).name || "");
        nav(`${spec.path}/${encodeURIComponent(createdName)}`);
      } else {
        await save.updateDoc(spec.doctype, name, draft);
        nav(`${spec.path}/${encodeURIComponent(name)}`);
      }
    } catch (err) {
      setSaveError(err);
    }
  }

  if (!isNew && existing.isLoading) return <Loading />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} onRetry={() => existing.mutate()} />;
  if (!draft) return <Loading />;

  const title = isNew ? t(spec.titleKey) : name;
  const busy = create.loading || save.loading;

  return (
    <>
      <PageHead
        eyebrow={<button type="button" className="btn quiet" onClick={() => nav(spec.path)}>{t(spec.titleKey)}</button>}
        title={title}
        actions={(
          <>
            <button type="button" className="btn ghost" onClick={() => nav(isNew ? spec.path : `${spec.path}/${encodeURIComponent(name)}`)}>{t("soc.discard")}</button>
            <button type="button" className="btn" disabled={busy} onClick={() => void onSave()}>{busy ? t("soc.saving") : t("soc.save")}</button>
          </>
        )}
      />
      {saveError ? <ErrorBox error={saveError} /> : null}
      <Card title={t(spec.titleKey)}>
        <div className="grid2">
          {spec.fields.map((field) => (
            <Field key={field.key} label={field.label} required={field.required}>
              {fieldControl(field, textOf(draft, field.key), partyDoctype, (value) => setField(field.key, value))}
            </Field>
          ))}
        </div>
      </Card>
      {spec.suppliers ? (
        <Card title="Suppliers">
          {suppliers.map((row, index) => (
            <div className="grid2" key={row.name || index}>
              <Field label="Supplier" required>
                <LinkField
                  doctype="Supplier"
                  value={row.supplier || ""}
                  onChange={(value) => {
                    const next = suppliers.slice();
                    next[index] = { ...row, supplier: value, contact: "", email_id: "" };
                    setDraft((current) => ({ ...(current || {}), suppliers: next }));
                    const company = textOf(draft || {}, "company") || session.company || "";
                    if (!value || !company) return;
                    void partyCall.call({
                      party: value,
                      party_type: "Supplier",
                      company,
                      doctype: "Request for Quotation",
                    }).then((res) => {
                      const message = res?.message;
                      setDraft((current) => {
                        const rows = [...((current?.suppliers as SupplierRow[] | undefined) ?? [])];
                        if (rows[index]?.supplier !== value) return current;
                        rows[index] = {
                          ...rows[index],
                          supplier: value,
                          contact: message?.contact_person || "",
                          email_id: message?.contact_email || "",
                        };
                        return { ...(current || {}), suppliers: rows };
                      });
                    }).catch(() => undefined);
                  }}
                />
              </Field>
              <button
                type="button"
                className="btn quiet"
                onClick={() => setDraft((current) => ({
                  ...(current || {}),
                  suppliers: suppliers.filter((_, rowIndex) => rowIndex !== index),
                }))}
              >
                {t("soc.discard")}
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn ghost"
            onClick={() => setDraft((current) => ({ ...(current || {}), suppliers: [...suppliers, { supplier: "" }] }))}
          >
            {t("mr.addLine")}
          </button>
        </Card>
      ) : null}
      {spec.linesKey === "delivery_stops" ? (
        <Card title="Stops">
          {((draft?.delivery_stops as StopRow[] | undefined) ?? []).map((row, index) => (
            <div className="grid2" key={row.name || index}>
              <Field label="Customer">
                <input className="ctl" value={row.customer || ""} readOnly aria-label="Customer" />
              </Field>
              <Field label="Address" required>
                <LinkField
                  doctype="Address"
                  value={row.address || ""}
                  onChange={(value) => setDraft((current) => {
                    const next = [...((current?.delivery_stops as StopRow[] | undefined) ?? [])];
                    next[index] = { ...next[index], address: value };
                    return { ...(current || {}), delivery_stops: next };
                  })}
                />
              </Field>
            </div>
          ))}
        </Card>
      ) : null}
      {spec.doctype === "Shipment" ? (
        <Card title="Parcels">
          {((draft?.shipment_parcel as ParcelRow[] | undefined) ?? []).map((row, index) => (
            <div className="grid2" key={row.name || index}>
              <Field label="Weight (kg)" required>
                <input
                  className="ctl"
                  type="number"
                  min="0"
                  aria-label="Weight (kg)"
                  value={row.weight ?? ""}
                  onChange={(event) => setDraft((current) => {
                    const next = [...((current?.shipment_parcel as ParcelRow[] | undefined) ?? [])];
                    next[index] = { ...next[index], weight: Number(event.target.value) };
                    return { ...(current || {}), shipment_parcel: next };
                  })}
                />
              </Field>
              <Field label="Count" required>
                <input
                  className="ctl"
                  type="number"
                  min="1"
                  aria-label="Count"
                  value={row.count ?? ""}
                  onChange={(event) => setDraft((current) => {
                    const next = [...((current?.shipment_parcel as ParcelRow[] | undefined) ?? [])];
                    next[index] = { ...next[index], count: Number(event.target.value) };
                    return { ...(current || {}), shipment_parcel: next };
                  })}
                />
              </Field>
            </div>
          ))}
          <button
            type="button"
            className="btn ghost"
            onClick={() => setDraft((current) => ({
              ...(current || {}),
              shipment_parcel: [...((current?.shipment_parcel as ParcelRow[] | undefined) ?? []), { count: 1 }],
            }))}
          >
            {t("mr.addLine")}
          </button>
        </Card>
      ) : null}
      {spec.linesKey && !spec.editLines && spec.linesKey !== "delivery_stops" ? (
        <Card title={spec.linesKey === "shipment_delivery_note" ? "Delivery notes" : "Items"}>
          {((draft?.[spec.linesKey] as Line[] | undefined) ?? []).map((row, index) => (
            <div className="grid2" key={row.name || index}>
              <Field label={spec.linesKey === "shipment_delivery_note" ? "Delivery note" : "Item"}>
                <input className="ctl" readOnly aria-label="Line" value={row.delivery_note || row.item_code || row.item_name || ""} />
              </Field>
              {row.qty != null ? (
                <Field label="Qty">
                  <input className="ctl" readOnly aria-label="Qty" value={String(row.qty)} />
                </Field>
              ) : null}
            </div>
          ))}
        </Card>
      ) : null}
      {spec.editLines ? (
        <Card title="Items">
          {lines.map((row, index) => (
            <div className="grid2" key={row.name || index}>
              <Field label="Item" required>
                <LinkField
                  doctype="Item"
                  value={row.item_code || ""}
                  onChange={(value) => {
                    const next = lines.slice();
                    next[index] = { ...row, item_code: value };
                    setDraft((current) => ({ ...(current || {}), items: next }));
                  }}
                />
              </Field>
              <Field label="Qty" required>
                <input
                  className="ctl"
                  type="number"
                  min="0"
                  value={row.qty ?? ""}
                  onChange={(event) => {
                    const next = lines.slice();
                    next[index] = { ...row, qty: Number(event.target.value) };
                    setDraft((current) => ({ ...(current || {}), items: next }));
                  }}
                />
              </Field>
            </div>
          ))}
          <button
            type="button"
            className="btn ghost"
            onClick={() => setDraft((current) => ({ ...(current || {}), items: [...lines, { item_code: "", qty: 1 }] }))}
          >
            {t("mr.addLine")}
          </button>
        </Card>
      ) : null}
    </>
  );
}

function fieldControl(
  field: FieldSpec,
  value: string,
  partyDoctype: string,
  onChange: (value: string) => void,
) {
  if (field.readOnly) return <input className="ctl" value={value} readOnly aria-label={field.label} />;
  if (field.kind === "link") {
    return (
      <LinkField
        doctype={field.key === "party_name" ? partyDoctype : (field.link || "")}
        value={value}
        onChange={onChange}
        placeholder={field.label}
      />
    );
  }
  if (field.kind === "select") {
    return (
      <select className="ctl" value={value} aria-label={field.label} onChange={(event) => onChange(event.target.value)}>
        <option value="">—</option>
        {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }
  if (field.kind === "datetime") {
    return (
      <input
        className="ctl"
        type="datetime-local"
        aria-label={field.label}
        value={localDateTime(value)}
        onChange={(event) => onChange(frappeDateTime(event.target.value))}
      />
    );
  }
  return (
    <input
      className="ctl"
      type={field.kind === "date" ? "date" : field.kind === "number" ? "number" : "text"}
      aria-label={field.label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
