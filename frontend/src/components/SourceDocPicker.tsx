/**
 * SourceDocPicker — load items from a submitted source via a catalogued make_* mapper.
 *
 * Callers: InvoiceForm, SalesOrderCreate, DeliveryNoteForm, Purchase forms.
 */
import { useId, useState } from "react";
import { useFrappePostCall } from "frappe-react-sdk";

import { readableError } from "../lib/frappe";
import { t } from "../i18n/strings";
import { Field } from "./ui";
import LinkField from "./LinkField";

export type SourceSpec = {
  label: string;
  doctype: string;
  method: string;
  /** Mapper argument name, usually source_name */
  arg?: string;
  /** Desk get-items filters. Defaults to submitted documents. */
  filters?: unknown;
};

type Props = {
  sources: SourceSpec[];
  onMapped: (doc: Record<string, unknown>) => void;
  disabled?: boolean;
};

function SourceFetch({
  method, arg, name, disabled, onMapped, onDone,
}: {
  method: string;
  arg: string;
  name: string;
  disabled?: boolean;
  onMapped: (doc: Record<string, unknown>) => void;
  onDone: (err: string[] | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  // The SDK freezes the method on the first render. This child is keyed by
  // method, so a source change mounts a caller for that mapper only.
  const call = useFrappePostCall<{ message: Record<string, unknown> }>(method);

  async function load() {
    if (!name) return;
    setBusy(true);
    onDone(null);
    try {
      const r = await call.call({ [arg]: name });
      const mapped = r?.message;
      if (!mapped) throw new Error(t("txn.mapEmpty"));
      const body: Record<string, unknown> = { ...mapped };
      delete body.name;
      delete body.__islocal;
      delete body.__unsaved;
      onMapped(body);
      onDone(null);
    } catch (e) {
      onDone(readableError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className="btn ghost"
      disabled={disabled || busy || !name}
      aria-busy={busy || undefined}
      onClick={() => void load()}
    >
      {busy ? t("txn.fetching") : t("txn.fetchItems")}
    </button>
  );
}

export default function SourceDocPicker({ sources, onMapped, disabled }: Props) {
  const id = useId();
  const [kind, setKind] = useState(0);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string[] | null>(null);
  const src = sources[kind] || sources[0];

  if (!sources.length) return null;

  const typeId = `${id}-type`;
  const docId = `${id}-doc`;

  return (
    <div className="fg" style={{ alignItems: "end" }}>
      <Field label={t("txn.sourceType")} htmlFor={typeId}>
        <select
          id={typeId}
          className="ctl"
          value={kind}
          disabled={disabled}
          onChange={(e) => {
            setKind(Number(e.target.value));
            setName("");
            setErr(null);
          }}
        >
          {sources.map((s, i) => (
            <option key={s.doctype + s.method} value={i}>
              {s.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("txn.sourceDoc")} htmlFor={docId}>
        <LinkField
          doctype={src.doctype}
          value={name}
          onChange={(v) => {
            setName(v);
            setErr(null);
          }}
          disabled={disabled}
          filters={src.filters ?? [["docstatus", "=", 1]]}
        />
      </Field>
      {src ? (
        <SourceFetch
          key={src.method}
          method={src.method}
          arg={src.arg || "source_name"}
          name={name}
          disabled={disabled}
          onMapped={(doc) => {
            onMapped(doc);
            setName("");
          }}
          onDone={setErr}
        />
      ) : null}
      {err?.length ? (
        <div role="alert" className="err" style={{ gridColumn: "1 / -1" }}>
          {err.map((line) => (
            <p key={line} style={{ margin: 0 }}>{line}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
