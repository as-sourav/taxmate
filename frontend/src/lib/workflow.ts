/**
 * Shared confirm for cancel.
 * Callers: DetailActions and detail screens that render their own Cancel button
 * (payment, supplier quotation, work order, stock reconciliation, material request).
 * API: guards taxmate.api.workflow.cancel. No request body of its own.
 * User: "Using frappe skills and anthropic skills, ensure that all our gaps are fixed and issues are fixed. Check buttons such as cancel, amend, and others - whether they work in all places or not. Review the complete frontend and make it robust- use gstack and production grade skills and development"
 */
import { t } from "../i18n/strings";

export function confirmCancel(name?: string): boolean {
  const label = t("inv.cancel");
  return window.confirm(name ? `${label} ${name}?` : `${label}?`);
}
