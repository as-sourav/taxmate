/**
 * DetailActions — reusable submit/cancel/amend/delete action cluster for detail screens.
 *
 * Callers: InvoiceDetail, PurchaseInvoiceDetail, DeliveryNoteDetail,
 *          PurchaseReceiptDetail, StockEntryDetail, JournalEntryDetail, …
 *
 * Renders Edit, Submit, Delete (drafts), Cancel (submitted), Amend (cancelled),
 * plus an optional extra slot. Labels come from i18n.
 */
import type { ReactNode } from "react";
import { t } from "../i18n/strings";
import { confirmCancel } from "../lib/workflow";
import DocHistory from "./DocHistory";

export type DetailActionsProps = {
  /** True when docstatus === 0. */
  draft?: boolean;
  /** True when docstatus === 1. */
  submitted?: boolean;
  /** True when docstatus === 2. */
  cancelled?: boolean;
  /** User may submit / amend documents. */
  canSubmit: boolean;
  /** User may cancel documents. */
  canCancel: boolean;
  /** User may create / edit / delete draft documents. */
  canWrite: boolean;
  /** True while any async action is in flight (disables Submit/Delete). */
  busy: boolean;
  /** Navigate to the edit route. Omit to hide the Edit button. */
  onEdit?: () => void;
  /** Call the submit RPC. Omit to hide the Submit button. */
  onSubmit?: () => void;
  /** Delete draft via taxmate.api.resource.delete. Omit to hide. */
  onDelete?: () => void;
  /** Call the cancel RPC. Omit to hide the Cancel button. */
  onCancel?: () => void;
  /** Call the amend RPC. Omit to hide the Amend button. */
  onAmend?: () => void;
  /**
   * Extra screen-specific buttons (receive payment, print, credit note, etc.).
   * Rendered between Submit and Cancel.
   */
  extra?: ReactNode;
  /** When set with `name`, shows the shared History control. */
  doctype?: string;
  name?: string;
};

/**
 * Renders Edit | Submit | Delete | [extra] | Cancel | Amend.
 * Callers place this in the `actions` prop of `<PageHead>`.
 */
export default function DetailActions({
  draft,
  submitted,
  cancelled,
  canSubmit,
  canCancel,
  canWrite,
  busy,
  onEdit,
  onSubmit,
  onDelete,
  onCancel,
  onAmend,
  extra,
  doctype,
  name,
}: DetailActionsProps) {
  function run(action: () => void | Promise<unknown>) {
    void Promise.resolve(action()).catch(() => undefined);
  }
  return (
    <>
      {doctype && name ? <DocHistory doctype={doctype} name={name} /> : null}
      {draft && canWrite && onEdit && (
        <button type="button" className="btn ghost" onClick={onEdit}>
          {t("inv.edit")}
        </button>
      )}
      {draft && canSubmit && onSubmit && (
        <button type="button" className="btn" disabled={busy} onClick={() => run(onSubmit)}>
          {busy ? t("soc.saving") : t("inv.submit")}
        </button>
      )}
      {draft && canWrite && canCancel && onDelete && (
        <button type="button" className="btn quiet" disabled={busy} onClick={onDelete}>
          {busy ? t("soc.saving") : t("inv.delete")}
        </button>
      )}
      {extra}
      {submitted && canCancel && onCancel && (
        <button
          type="button"
          className="btn quiet"
          disabled={busy}
          onClick={() => {
            if (!confirmCancel(name)) return;
            run(onCancel);
          }}
        >
          {busy ? t("soc.saving") : t("inv.cancel")}
        </button>
      )}
      {cancelled && canSubmit && onAmend && (
        <button type="button" className="btn ghost" disabled={busy} onClick={() => run(onAmend)}>
          {t("inv.amend")}
        </button>
      )}
    </>
  );
}
