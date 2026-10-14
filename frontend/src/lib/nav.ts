/**
 * Sidebar entries for shipped SPA routes only.
 * Feature flags from taxmate.api.settings.get_feature_flags gate optional packs.
 * A missing flag key is treated as enabled (fail-open) to avoid hiding nav on error.
 */

export interface FeatureFlags {
  enable_pos?: boolean;
  enable_serial?: boolean;
  enable_loyalty?: boolean;
  enable_bom?: boolean;
  enable_assets?: boolean;
  enable_pick_list?: boolean;
  /** True when BrainWise POSNext (pos_next) is installed on the site. */
  enable_pos_next?: boolean;
  /** Website route for POSNext SPA, typically /pos. */
  pos_next_url?: string | null;
  /** Assignable add-on Role names (POSNext Cashier, Nexus POS Manager). */
  addon_roles?: string[];
}

export type NavEntry =
  | { type: "section"; key: string }
  | { type: "link"; to: string; key: string }
  | { type: "external"; href: string; key: string };

export type NavLinkItem =
  | { to: string; key: string; external?: false }
  | { href: string; key: string; external: true };
export type NavGroup = { key: string; links: NavLinkItem[] };

export function groupedNav(entries: NavEntry[]): { top: NavLinkItem[]; groups: NavGroup[] } {
  const top: NavLinkItem[] = [];
  const groups: NavGroup[] = [];
  let current: NavGroup | null = null;
  for (const n of entries) {
    if (n.type === "section") {
      current = { key: n.key, links: [] };
      groups.push(current);
      continue;
    }
    const item: NavLinkItem =
      n.type === "external"
        ? { href: n.href, key: n.key, external: true }
        : { to: n.to, key: n.key };
    if (!current) {
      top.push(item);
      continue;
    }
    current.links.push(item);
  }
  return { top, groups: groups.filter((g) => g.links.length > 0) };
}

export function groupForPath(groups: NavGroup[], path: string): string | null {
  for (const group of groups) {
    for (const link of group.links) {
      if ("external" in link && link.external) continue;
      const to = "to" in link ? link.to : "";
      if (path === to || (to !== "/" && path.startsWith(`${to}/`))) {
        return group.key;
      }
    }
  }
  return null;
}

const _BASE_NAV: NavEntry[] = [
  { type: "link", to: "/", key: "nav.dashboard" },
  { type: "section", key: "nav.sales" },
  { type: "link", to: "/customers", key: "nav.customers" },
  { type: "link", to: "/orders", key: "nav.salesOrders" },
  { type: "link", to: "/quotations", key: "nav.quotations" },
  { type: "link", to: "/delivery-notes", key: "nav.deliveryNotes" },
  { type: "link", to: "/invoices", key: "nav.invoices" },
  { type: "link", to: "/payments", key: "nav.payments" },
  { type: "link", to: "/receivables", key: "nav.receivables" },
  { type: "link", to: "/leads", key: "nav.leads" },
  { type: "section", key: "nav.purchase" },
  { type: "link", to: "/suppliers", key: "nav.suppliers" },
  { type: "link", to: "/supplier-quotations", key: "nav.supplierQuotations" },
  { type: "link", to: "/purchase-orders", key: "nav.purchaseOrders" },
  { type: "link", to: "/purchase-receipts", key: "nav.purchaseReceipts" },
  { type: "link", to: "/incoming-invoices", key: "nav.incomingInvoices" },
  { type: "link", to: "/purchase-invoices", key: "nav.purchaseInvoices" },
  { type: "link", to: "/payables", key: "nav.payables" },
  { type: "section", key: "nav.stock" },
  { type: "link", to: "/stock-entries", key: "nav.stockEntries" },
  { type: "link", to: "/stock-reconciliations", key: "nav.stockReconciliations" },
  { type: "link", to: "/material-requests", key: "nav.materialRequests" },
  { type: "link", to: "/serial-nos", key: "nav.serialNos" },
  { type: "link", to: "/batches", key: "nav.batches" },
  { type: "link", to: "/landed-cost-vouchers", key: "nav.landedCostVouchers" },
  { type: "link", to: "/boms", key: "nav.boms" },
  { type: "link", to: "/work-orders", key: "nav.workOrders" },
  { type: "link", to: "/pick-lists", key: "nav.pickLists" },
  // Quotation under Sales; stock nav for SE/SR/MR. Callers: AppShell. User: Implement the plan… complete all the to-dos.
  { type: "section", key: "nav.accounting" },
  { type: "link", to: "/journals", key: "nav.journals" },
  { type: "link", to: "/bank-accounts", key: "nav.bankAccounts" },
  { type: "link", to: "/modes-of-payment", key: "nav.modesOfPayment" },
  { type: "link", to: "/bank-reconciliation", key: "nav.bankReconciliation" },
  { type: "link", to: "/fiscal-years", key: "nav.fiscalYears" },
  { type: "link", to: "/accounts", key: "nav.accounts" },
  { type: "link", to: "/cost-centers", key: "nav.costCenters" },
  { type: "link", to: "/period-closing", key: "nav.periodClosing" },
  { type: "link", to: "/currency-exchanges", key: "nav.currencyExchanges" },
  { type: "link", to: "/reports", key: "nav.reports" },
  { type: "section", key: "nav.masters" },
  { type: "link", to: "/catalogue/items", key: "nav.items" },
  { type: "link", to: "/catalogue/item-groups", key: "nav.itemGroups" },
  { type: "link", to: "/catalogue/brands", key: "nav.brands" },
  { type: "link", to: "/catalogue/uoms", key: "nav.uoms" },
  { type: "link", to: "/warehouses", key: "nav.warehouses" },
  { type: "link", to: "/price-lists", key: "nav.priceLists" },
  { type: "link", to: "/payment-terms-templates", key: "nav.paymentTermsTemplates" },
  { type: "link", to: "/tax-templates", key: "nav.taxTemplates" },
  { type: "link", to: "/tax-categories", key: "nav.taxCategories" },
  { type: "link", to: "/item-tax-templates", key: "nav.itemTaxTemplates" },
  { type: "link", to: "/pricing-rules", key: "nav.pricingRules" },
  { type: "link", to: "/customer-groups", key: "nav.customerGroups" },
  { type: "link", to: "/supplier-groups", key: "nav.supplierGroups" },
  { type: "link", to: "/territories", key: "nav.territories" },
  { type: "link", to: "/addresses", key: "nav.addresses" },
  { type: "link", to: "/contacts", key: "nav.contacts" },
  { type: "link", to: "/terms-and-conditions", key: "nav.termsAndConditions" },
  { type: "section", key: "nav.compliance" },
  { type: "link", to: "/vat-201", key: "nav.vat201" },
  { type: "link", to: "/ct-filings", key: "nav.ct" },
  { type: "link", to: "/esr", key: "nav.esr" },
  { type: "link", to: "/ubo", key: "nav.ubo" },
  { type: "link", to: "/late-filings", key: "nav.lateFilings" },
  { type: "link", to: "/e-invoice-log", key: "nav.eInvoiceLog" },
  { type: "link", to: "/tax-settings", key: "nav.taxSettings" },
  { type: "link", to: "/uae-related-parties", key: "nav.uaeRelatedParties" },
  { type: "link", to: "/uae-vat-groups", key: "nav.uaeVatGroups" },
  { type: "link", to: "/uae-bad-debt-relief", key: "nav.uaeBadDebt" },
  { type: "link", to: "/uae-customs-declarations", key: "nav.uaeCustoms" },
  { type: "link", to: "/uae-capital-goods-adjustments", key: "nav.uaeCapitalGoods" },
  { type: "section", key: "nav.pos" },
  { type: "link", to: "/pos-invoices", key: "nav.posInvoices" },
  { type: "link", to: "/pos-profiles", key: "nav.posProfiles" },
  { type: "external", href: "/pos", key: "nav.posNext" },
  { type: "link", to: "/loyalty-programs", key: "nav.loyaltyPrograms" },
  { type: "link", to: "/loyalty-point-entries", key: "nav.loyaltyPointEntries" },
  { type: "section", key: "nav.fixedAssets" },
  { type: "link", to: "/assets", key: "nav.assets" },
  { type: "link", to: "/asset-categories", key: "nav.assetCategories" },
  { type: "section", key: "nav.company" },
  { type: "link", to: "/company", key: "nav.companySettings" },
  { type: "link", to: "/team", key: "nav.team" },
];

/**
 * Returns a filtered nav array respecting feature flags.
 * Callers: AppShell. User: "Implement the plan… complete all the to-dos."
 */
export function buildNav(flags: FeatureFlags = {}): NavEntry[] {
  const enabled = (k: keyof FeatureFlags) => flags[k] !== false;

  const gated: Record<string, boolean> = {
    "nav.pickLists": enabled("enable_pick_list"),
    "nav.boms": enabled("enable_bom"),
    "nav.workOrders": enabled("enable_bom"),
    "nav.serialNos": enabled("enable_serial"),
    "nav.batches": enabled("enable_serial"),
    "nav.posInvoices": enabled("enable_pos"),
    "nav.posProfiles": enabled("enable_pos"),
    "nav.posNext": !!flags.enable_pos_next,
    "nav.loyaltyPrograms": enabled("enable_loyalty"),
    "nav.loyaltyPointEntries": enabled("enable_loyalty"),
    "nav.assets": enabled("enable_assets"),
    "nav.assetCategories": enabled("enable_assets"),
    // Sections: keep only if at least one link inside is enabled
    "nav.pos": enabled("enable_pos") || enabled("enable_loyalty") || !!flags.enable_pos_next,
    "nav.fixedAssets": enabled("enable_assets"),
  };

  const posUrl = (flags.pos_next_url || "/pos").trim() || "/pos";

  return _BASE_NAV.filter((e) => {
    if (e.key in gated) return gated[e.key];
    return true;
  }).map((e) => {
    if (e.type === "external" && e.key === "nav.posNext") {
      return { ...e, href: posUrl };
    }
    return e;
  });
}

/** Default nav (all packs enabled). Kept for backward-compat. */
export const NAV: NavEntry[] = buildNav({
  enable_pos: true,
  enable_serial: true,
  enable_loyalty: true,
  enable_bom: true,
  enable_assets: true,
  enable_pick_list: true,
  enable_pos_next: false,
});

/* ── Mobile bottom tabs ──────────────────────────────────────────────
   Five tabs stand in for the rail below 900px. A tab lights up for a
   whole route family, not just its own destination, so /orders and
   /quotations both read as "Sales" even though the tab points at
   /invoices. Callers: components/MobileNav.tsx.
   ──────────────────────────────────────────────────────────────────── */

export type MobileTabId = "home" | "sales" | "money" | "reports";

/** Route families per tab. Order matters only in that families must not overlap. */
export const MOBILE_TAB_PATHS: Record<Exclude<MobileTabId, "home">, string[]> = {
  sales: [
    "/customers",
    "/orders",
    "/quotations",
    "/delivery-notes",
    "/invoices",
    "/leads",
    "/pos-invoices",
  ],
  // Purchase stays in More only — lighting Money while browsing POs was confusing.
  money: [
    "/payments",
    "/receivables",
    "/payables",
    "/journals",
    "/bank-reconciliation",
    "/bank-accounts",
  ],
  reports: ["/reports"],
};

/**
 * Nav keys omitted from the phone More sheet only.
 * Redundant with a bottom tab, or desktop-oriented setup/masters.
 * Routes stay reachable by URL; AppShell rail is unchanged.
 * Callers: MobileNav. docs/mobile-ux/PLAN.md Phase B.
 */
export const MOBILE_MORE_OMIT = new Set<string>([
  // Redundant with tabs
  "nav.dashboard",
  "nav.invoices",
  "nav.payments",
  "nav.reports",
  // Desktop-oriented
  "nav.serialNos",
  "nav.batches",
  "nav.landedCostVouchers",
  "nav.boms",
  "nav.modesOfPayment",
  "nav.fiscalYears",
  "nav.accounts",
  "nav.costCenters",
  "nav.periodClosing",
  "nav.currencyExchanges",
  "nav.itemGroups",
  "nav.brands",
  "nav.uoms",
  "nav.priceLists",
  "nav.paymentTermsTemplates",
  "nav.taxTemplates",
  "nav.taxCategories",
  "nav.itemTaxTemplates",
  "nav.pricingRules",
  "nav.customerGroups",
  "nav.supplierGroups",
  "nav.territories",
  "nav.termsAndConditions",
  "nav.taxSettings",
  "nav.uaeRelatedParties",
  "nav.uaeVatGroups",
  "nav.uaeBadDebt",
  "nav.uaeCustoms",
  "nav.uaeCapitalGoods",
  "nav.posProfiles",
  "nav.loyaltyPrograms",
  "nav.assetCategories",
  "nav.companySettings",
]);

/** Drop omitted keys from top links and groups for the phone More sheet. */
export function filterNavForMobileMore(top: NavLinkItem[], groups: NavGroup[]): {
  top: NavLinkItem[];
  groups: NavGroup[];
} {
  const keep = (item: NavLinkItem) => !MOBILE_MORE_OMIT.has(item.key);
  return {
    top: top.filter(keep),
    groups: groups
      .map((g) => ({ ...g, links: g.links.filter(keep) }))
      .filter((g) => g.links.length > 0),
  };
}

function inFamily(paths: string[], path: string): boolean {
  return paths.some((p) => path === p || path.startsWith(`${p}/`));
}

/**
 * Which bottom tab owns a pathname, or null when none does (Stock, Masters,
 * Compliance… — those live behind "More", which owns its own active state).
 * Home is an exact match on "/" so every other screen does not light it up.
 */
export function mobileTabForPath(path: string): MobileTabId | null {
  if (path === "/") return "home";
  if (inFamily(MOBILE_TAB_PATHS.sales, path)) return "sales";
  if (inFamily(MOBILE_TAB_PATHS.money, path)) return "money";
  if (inFamily(MOBILE_TAB_PATHS.reports, path)) return "reports";
  return null;
}
