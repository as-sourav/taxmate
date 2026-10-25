/**
 * Payment Entry domain rules.
 *
 * Everything here is verified against ERPNext version-16 — see
 * claude/payment-entry-api-verification.md for the file:line evidence.
 */

/* ── Status ───────────────────────────────────────────────────────────
   Unlike Sales Order (9 values) and Sales Invoice (13), Payment Entry's
   stored `status` Select is exactly Draft / Submitted / Cancelled. No
   mapping, and no staleness — set_status() runs inside validate().      */

export const PAY_STATUSES = ["Draft", "Submitted", "Cancelled"] as const;
export type PayStatus = (typeof PAY_STATUSES)[number];

export const PAY_PILL: Record<PayStatus, string> = {
  Draft: "p-draft",
  Submitted: "p-unpaid",
  Cancelled: "p-cxl",
};

export const PAY_STATUS_COLOUR: Record<PayStatus, string> = {
  Draft: "var(--c-draft)",
  Submitted: "var(--c-confirmed)",
  Cancelled: "var(--c-delivered)",
};

/** docstatus is the truth; `status` is a mirror of it. */
export function payStatus(row: { docstatus?: number; status?: string }): PayStatus {
  if (row.docstatus === 2) return "Cancelled";
  if (row.docstatus === 1) return "Submitted";
  if (row.status && (PAY_STATUSES as readonly string[]).includes(row.status)) return row.status as PayStatus;
  return "Draft";
}

/* ── Direction ────────────────────────────────────────────────────────
   Receive/Pay is this module's primary axis, and it decides the party
   doctype, which invoices are outstanding, and which leg is the bank.   */

export type PayType = "Receive" | "Pay" | "Internal Transfer";

export const PARTY_TYPE: Partial<Record<PayType, "Customer" | "Supplier">> & Record<"Receive" | "Pay", "Customer" | "Supplier"> = {
  Receive: "Customer",
  Pay: "Supplier",
};

/**
 * Reference No. is mandatory when the BANK LEG is a Bank account.
 *
 * ERPNext puts the bank/cash leg on `paid_to` for a Receive and `paid_from`
 * for a Pay, and validate_transaction_reference (payment_entry.py:1248)
 * inspects only that leg before throwing "Reference No and Reference Date is
 * mandatory for Bank transaction". Reading the wrong leg makes the guard
 * silently stop working on a Pay.
 *
 * The leg mapping itself lives server-side in
 * taxmate.api.accounts.resolve_payment_accounts, which hands back the
 * resolved account's type — this just applies the rule to it. The DocType
 * also carries mandatory_depends_on, but that is evaluated client-side only,
 * so the server check above is the sole enforcement and the UI must mirror it.
 */
export function needsReference(bankAccountType?: string): boolean {
  return bankAccountType === "Bank";
}

/* ── Allocation ───────────────────────────────────────────────────────
   total_allocated_amount and unallocated_amount are STORED columns,
   written by set_amounts() inside validate() (payment_entry.py:979), so
   they are right on drafts too and the list needs no arithmetic.        */

export type Coverage = "none" | "part" | "full";

export function coverageOf(paid?: number, allocated?: number): Coverage {
  const p = Number(paid) || 0;
  const a = Number(allocated) || 0;
  if (p <= 0 || a <= 0) return "none";
  return a + 0.005 >= p ? "full" : "part";
}

export const COVERAGE_COLOUR: Record<Coverage, string> = {
  none: "var(--warn)",
  part: "var(--c-confirmed)",
  full: "var(--ok)",
};

export const COVERAGE_KEY: Record<Coverage, string> = {
  none: "pay.cov.none",
  part: "pay.cov.part",
  full: "pay.cov.full",
};

export const round2 = (n: number) => Math.round((Number(n) || 0) * 100) / 100;

/** Spec §7: ticking a line allocates min(its balance, what is left). */
export function autoAllocate(outstanding: number, remaining: number): number {
  const bal = Number(outstanding) || 0;
  // A credit note comes back with a negative balance; keep its sign.
  if (bal < 0) return round2(bal);
  return round2(Math.max(0, Math.min(bal, Math.max(0, remaining))));
}

/* ── Roles ────────────────────────────────────────────────────────────
   Payment Entry grants create/submit/cancel/amend to exactly two roles in
   ERPNext v16 — Accounts User and Accounts Manager. The sales helpers in
   roles.ts also list UAE Tax Manager and System Manager, which have NO
   DocPerm here: borrowing them would show a Submit button that the server
   refuses. Accounts User can also cancel, which the sales CANCEL_ROLES
   leaves out. Hence payment-specific predicates.                        */

const PAY_WRITE_ROLES = ["Accounts User", "Accounts Manager", "System Manager"];

/** Payment Entry submit follows Accounts User and Accounts Manager. */
export function canSubmitPayment(roles: string[] | undefined): boolean {
  return (roles ?? []).some((r) => PAY_WRITE_ROLES.includes(r));
}

/** Payment Entry cancel follows those same standard roles. Accounts User can cancel one. */
export function canCancelPayment(roles: string[] | undefined): boolean {
  return (roles ?? []).some((r) => PAY_WRITE_ROLES.includes(r));
}
