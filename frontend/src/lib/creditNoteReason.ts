/** BTAE-03 codes. Values match taxmate.uae_e_invoicing.constants.CREDIT_NOTE_REASON_CODES. */

export const CREDIT_NOTE_REASON_LABELS: Record<string, string> = {
  GOODS_OR_SERVICES_RETURNED: "Goods or services returned",
  SUPPLY_CANCELLED: "Supply cancelled",
  TAX_TREATMENT_CHANGED: "Tax treatment changed",
  CONSIDERATION_ALTERED: "Consideration altered",
  TAX_APPLIED_IN_ERROR: "Tax applied in error",
  VOLUME_DISCOUNT: "Volume discount",
};

export const CREDIT_NOTE_REASONS = Object.keys(CREDIT_NOTE_REASON_LABELS);

const LEGACY: Record<string, (typeof CREDIT_NOTE_REASONS)[number]> = {
  "goods returned": "GOODS_OR_SERVICES_RETURNED",
  "pricing correction": "CONSIDERATION_ALTERED",
  vd: "VOLUME_DISCOUNT",
  "volume discount": "VOLUME_DISCOUNT",
};

export function creditNoteReasonCode(raw: string | null | undefined): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const head = text.split(" - ")[0].trim();
  if ((CREDIT_NOTE_REASONS as readonly string[]).includes(head)) return head;
  return LEGACY[text.toLowerCase()] || "";
}
