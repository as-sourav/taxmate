/**
 * Open a catalog mapper result on the draft form.
 * Callers: Customer, Lead, Supplier, Material Request, Delivery Note,
 * Sales Order, Sales Invoice, Purchase Order, Purchase Invoice, and the
 * new document screens. API: taxmate.api.linked_docs.*.
 * Schema: { message: ERPNext doc dict, optional _already_saved }.
 * User: build Opportunity, Request for Quotation, Shipment, Installation Note,
 * Delivery Trip, Payment Request, and the two subcontracting documents.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { t } from "../i18n/strings";
import { useInsert } from "./resource";

type MappedCall = { message?: Record<string, unknown> };

function stripRow(row: Record<string, unknown>): Record<string, unknown> {
  const child = { ...row };
  delete child.name;
  delete child.parent;
  delete child.parentfield;
  delete child.parenttype;
  delete child.doctype;
  delete child.owner;
  delete child.creation;
  delete child.modified;
  delete child.idx;
  return child;
}

export function stripForInsert(doc: Record<string, unknown>): Record<string, unknown> {
  const body: Record<string, unknown> = { ...doc };
  delete body.name;
  delete body.doctype;
  delete body.owner;
  delete body.creation;
  delete body.modified;
  delete body.modified_by;
  delete body.docstatus;
  delete body.idx;
  delete body.__islocal;
  delete body.__unsaved;
  delete body._already_saved;
  for (const [key, value] of Object.entries(body)) {
    if (!Array.isArray(value)) continue;
    body[key] = value.map((row) => (
      row && typeof row === "object" ? stripRow(row as Record<string, unknown>) : row
    ));
  }
  return body;
}

export function mappedDraft(message: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!message) throw new Error(t("doc.err.mapFailed"));
  const body: Record<string, unknown> = { ...message };
  delete body.doctype;
  delete body.__islocal;
  delete body.__unsaved;
  delete body._already_saved;
  delete body.name;
  return body;
}

export function useOpenMapped(listPath: string) {
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function open(call: () => Promise<MappedCall | undefined>) {
    setBusy(true);
    setError(null);
    try {
      const res = await call();
      const message = res?.message;
      if (!message) throw new Error(t("doc.err.mapFailed"));
      if (message._already_saved && message.name) {
        nav(`${listPath}/${encodeURIComponent(String(message.name))}`);
        return;
      }
      nav(`${listPath}/new`, { state: { mapped: mappedDraft(message) } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return { open, busy, error };
}

/** Insert a mapped draft and open it. Used when the target form does not apply a full mapped doc. */
export function useInsertMapped(doctype: string, detailPath: string) {
  const nav = useNavigate();
  const create = useInsert();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function open(call: () => Promise<MappedCall | undefined>) {
    setBusy(true);
    setError(null);
    try {
      const res = await call();
      const message = res?.message;
      if (!message) throw new Error(t("doc.err.mapFailed"));
      if (message._already_saved && message.name) {
        nav(`${detailPath}/${encodeURIComponent(String(message.name))}`);
        return;
      }
      const created = await create.createDoc(doctype, stripForInsert(mappedDraft(message)));
      const createdName = String((created as { name?: string }).name || "");
      if (!createdName) throw new Error(t("doc.err.mapFailed"));
      nav(`${detailPath}/${encodeURIComponent(createdName)}`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return { open, busy, error };
}
