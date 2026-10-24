/** Spec §2 — SPA roles mapped to Frappe markers. Multiple markers → DocPerm union. */

export type SpaRole = "owner" | "accountant" | "clerk" | "viewer";

export const SPA_ROLES: SpaRole[] = ["owner", "accountant", "clerk", "viewer"];

export const POS_ADDON_ROLES = ["POSNext Cashier", "Nexus POS Manager"] as const;
export type PosAddonRole = (typeof POS_ADDON_ROLES)[number];

/**
 * Returns true when the current user is the *application provider* —
 * i.e. the TaxMate SaaS team, not a client employee.
 *
 * Heuristic: `Administrator` always qualifies (Frappe super-user).
 * A `System Manager` without any TaxMate-specific role is also treated as
 * a provider because the client's own owner would have been assigned
 * `TaxMate Owner`.
 */
export function isAppProvider(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  user?: string;
  is_app_provider?: boolean;
} | undefined): boolean {
  if (session?.is_app_provider) return true;
  if (session?.user === "Administrator") return true;
  const roles = session?.roles ?? [];
  const hasTaxMateRole = roles.some((r) =>
    [
      "TaxMate Owner",
      "TaxMate Accountant",
      "TaxMate Accounts User",
      "TaxMate Accounts Officer",
      "TaxMate Auditor",
      "TaxMate Clerk",
      "TaxMate Viewer",
    ].includes(r),
  );
  if (roles.includes("System Manager") && !hasTaxMateRole) return true;
  return false;
}

/** Standard Frappe role each frontend role requires. Viewer has none. */
const STANDARD_ROLE: Record<Exclude<SpaRole, "viewer">, string> = {
  owner: "Accounts Manager",
  accountant: "Accounts Manager",
  clerk: "Accounts User",
};

function holdsStandardRole(roles: string[], spa: SpaRole): boolean {
  if (roles.includes("System Manager")) return true;
  if (spa === "viewer") return true;
  if (spa === "accountant" && roles.includes("UAE Tax Manager")) return true;
  return roles.includes(STANDARD_ROLE[spa]);
}

export function spaRolesOf(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  user?: string;
} | undefined): SpaRole[] {
  const roles = session?.roles ?? [];
  if (session?.user === "Administrator") return [];
  if (roles.includes("System Manager") && !roles.some((role) => role.startsWith("TaxMate"))) return [];

  const found: SpaRole[] = [];
  if (roles.includes("TaxMate Owner") && holdsStandardRole(roles, "owner")) found.push("owner");
  if (roles.includes("TaxMate Accountant") && holdsStandardRole(roles, "accountant")) found.push("accountant");
  if (
    (roles.includes("TaxMate Accounts User")
      || roles.includes("TaxMate Accounts Officer")
      || roles.includes("TaxMate Clerk"))
    && holdsStandardRole(roles, "clerk")
  ) found.push("clerk");
  if (roles.includes("TaxMate Auditor") || roles.includes("TaxMate Viewer")) found.push("viewer");
  if (
    !found.includes("accountant")
    && !found.includes("owner")
    && (roles.includes("Accounts Manager") || roles.includes("UAE Tax Manager"))
  ) found.push("accountant");
  if (
    !found.includes("clerk")
    && !found.includes("accountant")
    && !found.includes("owner")
    && roles.includes("Accounts User")
  ) found.push("clerk");
  if (found.length) return SPA_ROLES.filter((role) => found.includes(role));
  return ["viewer"];
}

export function spaRoleOf(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
} | undefined): SpaRole {
  return spaRolesOf(session)[0] ?? "viewer";
}

export type HomeView = "owner" | "accountant" | "clients";

/** Home screens this person may open. Null until the session has loaded. */
export function allowedDashModes(session: {
  user?: string;
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
} | undefined): HomeView[] | null {
  if (!session?.user) return null;
  const roles = session.roles ?? [];
  if (session.user === "Administrator" || roles.includes("System Manager")) {
    return ["owner", "accountant", "clients"];
  }
  const role = spaRoleOf(session);
  // Owner stays on the owner view only. Accountant may open the owner view
  // as well as the books / all-clients views; clerk and viewer stay on books.
  if (role === "owner") return ["owner"];
  if (role === "accountant") return ["accountant", "owner", "clients"];
  return ["accountant"];
}

export function canWrite(session: { spa_role?: string | null; spa_roles?: string[]; roles?: string[] } | undefined): boolean {
  return spaRoleOf(session) !== "viewer";
}

export function canManageUsers(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  is_app_provider?: boolean;
  user?: string;
} | undefined): boolean {
  if (isAppProvider(session)) return false;
  const roles = session?.roles ?? [];
  if (!roles.includes("TaxMate Owner")) return false;
  return spaRoleOf(session) === "owner";
}

/** Provider (Administrator) may assign a company TaxMate Owner, never be one. */
export function canOnboardCompanyOwner(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  is_app_provider?: boolean;
  user?: string;
} | undefined): boolean {
  return isAppProvider(session);
}

/** True when the user may edit all curated Company Settings fields (Owner + Provider). */
export function canManageCompany(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  user?: string;
} | undefined): boolean {
  if (isAppProvider(session)) return true;
  return spaRoleOf(session) === "owner";
}

/**
 * Accounts / stock / buying-selling / practice VAT / books-lock tabs.
 * Owner and Accountant (DocPerm already grants Company write to both).
 */
export function canEditCompanyAccounts(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  user?: string;
} | undefined): boolean {
  if (canManageCompany(session)) return true;
  return spaRoleOf(session) === "accountant";
}

/** Site-wide UAE Tax Settings (ASP). Same write roles as settings Singles. */
export function canEditTaxSettings(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  user?: string;
} | undefined): boolean {
  return canEditCompanyAccounts(session);
}

/**
 * Desk (`/app`, `/desk`) is gated server-side to Administrator only
 * (`taxmate.setup.desk_gate`). Mirror that here so the SPA never offers
 * a Desk link that the gate would bounce.
 */
export function canOpenDesk(session: { user?: string } | undefined): boolean {
  return session?.user === "Administrator";
}

export function canViewTeam(session: { spa_role?: string | null; spa_roles?: string[]; roles?: string[] } | undefined): boolean {
  const spa = spaRoleOf(session);
  return spa === "owner" || spa === "accountant";
}

export function canOpenPosNext(session: {
  spa_role?: string | null;
  spa_roles?: string[];
  roles?: string[];
  extra_roles?: string[];
} | undefined): boolean {
  if (spaRoleOf(session) === "owner") return true;
  const roles = session?.roles ?? [];
  const extras = session?.extra_roles ?? [];
  return (
    roles.includes("POSNext Cashier")
    || roles.includes("Nexus POS Manager")
    || extras.includes("POSNext Cashier")
    || extras.includes("Nexus POS Manager")
  );
}

const SUBMIT_ROLES = ["Accounts User", "Accounts Manager", "UAE Tax Manager", "System Manager"];
const CANCEL_ROLES = ["Accounts Manager", "UAE Tax Manager", "System Manager"];
const DELETE_ROLES = ["Accounts Manager", "Sales Manager", "Purchase Manager", "System Manager"];

/** Submit is shown only when a standard role that can submit is on the user. */
export function canSubmitSales(roles: string[] | undefined): boolean {
  return (roles ?? []).some((r) => SUBMIT_ROLES.includes(r));
}

/** Cancel is shown only when a standard role that can cancel is on the user. */
export function canCancelSales(roles: string[] | undefined): boolean {
  return (roles ?? []).some((r) => CANCEL_ROLES.includes(r));
}

/** Draft delete is shown only when a standard role that can delete is on the user. */
export function canDeleteDraft(roles: string[] | undefined): boolean {
  return (roles ?? []).some((r) => DELETE_ROLES.includes(r));
}

export function eInvoiceLocked(status?: string | null): boolean {
  return ["Queued", "Submitted", "Accepted"].includes(status ?? "");
}
