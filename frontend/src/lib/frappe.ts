/**
 * Thin typed wrappers over frappe-react-sdk.
 *
 * Two rules this file enforces:
 *  1. The site name and CSRF token come from the server (injected by
 *     taxmate/www/taxmate.py), never from a constant in the bundle.
 *  2. Everything is same-origin, so no base URL is configured anywhere.
 */

declare global {
  interface Window {
    csrf_token?: string;
    site_name?: string;
    taxmate_boot?: { user?: string; socket_port?: string };
  }
}

/** Site name as rendered by the server. Empty in `npm run dev` against a proxy. */
export function getSiteName(): string | undefined {
  const s = window.site_name;
  // Unsubstituted Jinja means the page was served statically — treat as absent.
  if (!s || s.startsWith("{{")) return undefined;
  return s;
}

export function getSocketPort(): string | undefined {
  const p = window.taxmate_boot?.socket_port;
  if (!p || p.startsWith("{{")) return undefined;
  return p;
}

/**
 * True when the page was rendered by Frappe and carries a live CSRF token.
 * frappe-js-sdk skips the header when the value is the literal placeholder,
 * so a static serve fails loudly on the first write instead of silently.
 */
export function hasCsrfToken(): boolean {
  const t = window.csrf_token;
  return !!t && !t.startsWith("{{");
}

/* ── Doctype names in one place, so a rename is one edit ─────────────── */
export const DT = {
  salesOrder: "Sales Order",
  salesOrderItem: "Sales Order Item",
  salesInvoice: "Sales Invoice",
  salesInvoiceItem: "Sales Invoice Item",
  deliveryNote: "Delivery Note",
  deliveryNoteItem: "Delivery Note Item",
  customer: "Customer",
  item: "Item",
  itemPrice: "Item Price",
  address: "Address",
  contact: "Contact",
  account: "Account",
  journalEntry: "Journal Entry",
  costCenter: "Cost Center",
  paymentEntry: "Payment Entry",
  supplier: "Supplier",
  purchaseInvoice: "Purchase Invoice",
  purchaseOrder: "Purchase Order",
  purchaseReceipt: "Purchase Receipt",
  incomingInvoice: "UAE Incoming Invoice",
  paymentEntryRef: "Payment Entry Reference",
  modeOfPayment: "Mode of Payment",
  bankAccount: "Bank Account",
  taxTemplate: "Sales Taxes and Charges Template",
  purchaseTaxTemplate: "Purchase Taxes and Charges Template",
  warehouse: "Warehouse",
  paymentTerms: "Payment Terms Template",
  sellingSettings: "Selling Settings",
  buyingSettings: "Buying Settings",
  itemGroup: "Item Group",
  brand: "Brand",
  customerGroup: "Customer Group",
  supplierGroup: "Supplier Group",
  uom: "UOM",
  priceList: "Price List",
  uomConversion: "UOM Conversion Detail",
  stockEntry: "Stock Entry",
  stockReconciliation: "Stock Reconciliation",
  materialRequest: "Material Request",
  quotation: "Quotation",
  eInvoiceLog: "UAE E-Invoice Log",
  vat201: "UAE VAT 201 Filing Log",
  ctFiling: "UAE CT Filing Log",
  esrFiling: "UAE ESR Filing",
  uboRegister: "UAE UBO Register",
  lateFiling: "UAE Late Filing Notice",
  serialNo: "Serial No",
  batch: "Batch",
  landedCostVoucher: "Landed Cost Voucher",
  pricingRule: "Pricing Rule",
  territory: "Territory",
  stockLedgerEntry: "Stock Ledger Entry",
  taxCategory: "Tax Category",
  itemTaxTemplate: "Item Tax Template",
  fiscalYear: "Fiscal Year",
  termsAndConditions: "Terms and Conditions",
  uaeRelatedParty: "UAE Related Party",
  uaeVatGroup: "UAE VAT Group",
  uaeBadDebt: "UAE Bad Debt Relief",
  uaeCustoms: "UAE Customs Declaration",
  uaeCapitalGoods: "UAE Capital Goods Adjustment",
  supplierQuotation: "Supplier Quotation",
  lead: "Lead",
  bom: "BOM",
  workOrder: "Work Order",
  posInvoice: "POS Invoice",
  posProfile: "POS Profile",
  loyaltyProgram: "Loyalty Program",
  loyaltyPointEntry: "Loyalty Point Entry",
  pickList: "Pick List",
  currencyExchange: "Currency Exchange",
  assetCategory: "Asset Category",
  asset: "Asset",
  company: "Company",
} as const;

/**
 * RPC names from taxmate.api.get_catalog() where available.
 * Prefer taxmate.api.* over raw erpnext.* / frappe.desk.*.
 */
export const METHOD = {
  getCatalog: "taxmate.api.get_catalog",
  getSession: "taxmate.api.get_session",
  listMyCompanies: "taxmate.api.company.list_my_companies",
  switchCompany: "taxmate.api.company.switch_company",
  listCompanyAddresses: "taxmate.api.company.list_company_addresses",
  uploadCompanyLogo: "taxmate.api.company.upload_company_logo",
  getUaeTaxSettings: "taxmate.api.tax_settings.get_uae_tax_settings",
  saveUaeTaxSettings: "taxmate.api.tax_settings.save_uae_tax_settings",
  getHome: "taxmate.api.dashboard.get_home",
  ownerDashboard: "taxmate.api.owner_dashboard.get_owner_dashboard",
  accountantDashboard: "taxmate.api.accountant_dashboard.get_accountant_dashboard",
  clientsDashboard: "taxmate.api.clients_dashboard.get_clients_dashboard",
  idpSurface: "taxmate.api.idp_desk.get_surface",
  idpUpload: "taxmate.api.idp_desk.upload",
  idpRun: "taxmate.api.idp_desk.run",
  idpSave: "taxmate.api.idp_desk.save",
  getList: "taxmate.api.resource.get_list",
  get: "taxmate.api.resource.get",
  insert: "taxmate.api.resource.insert",
  save: "taxmate.api.resource.save",
  delete: "taxmate.api.resource.delete",
  bulkDelete: "taxmate.api.resource.bulk_delete",
  getCount: "taxmate.api.resource.get_count",
  groupByCount: "taxmate.api.resource.group_by_count",
  getDefaults: "taxmate.api.accounts.get_defaults",
  getPartyDetails: "taxmate.api.accounts.get_party_details",
  partyDetails: "taxmate.api.accounts.get_party_details",
  getItemDetails: "taxmate.api.accounts.get_item_details",
  itemDetails: "taxmate.api.accounts.get_item_details",
  applyPriceList: "taxmate.api.accounts.apply_price_list",
  applyPricingRule: "taxmate.api.accounts.apply_pricing_rule",
  getTaxesAndCharges: "taxmate.api.accounts.get_taxes_and_charges",
  getConversionFactor: "taxmate.api.accounts.get_conversion_factor",
  getExchangeRate: "taxmate.api.accounts.get_exchange_rate",
  getPaymentTerms: "taxmate.api.accounts.get_payment_terms",
  getCreditBalance: "taxmate.api.accounts.get_credit_balance",
  previewTaxesAndTotals: "taxmate.api.accounts.preview_taxes_and_totals",
  getOutstandingInvoices: "taxmate.api.accounts.get_outstanding_invoices",
  resolvePaymentAccounts: "taxmate.api.accounts.resolve_payment_accounts",
  resolveInternalTransferAccounts: "taxmate.api.accounts.resolve_internal_transfer_accounts",
  getJeAccountDetails: "taxmate.api.accounts.get_je_account_details",
  getJePartyAccount: "taxmate.api.accounts.get_je_party_account",
  getAccountingDimensions: "taxmate.api.accounts.get_accounting_dimensions",
  getPaymentEntry: "taxmate.api.accounts.get_payment_entry",
  getAccountTree: "taxmate.api.accounts.get_account_tree",
  makeSalesReturn: "taxmate.api.accounts.make_sales_return",
  // DebitNoteForm + catalog make_purchase_return. User: Implement the plan… complete all the to-dos.
  makePurchaseReturn: "taxmate.api.accounts.make_purchase_return",
  submit: "taxmate.api.workflow.submit",
  cancel: "taxmate.api.workflow.cancel",
  amend: "taxmate.api.workflow.amend",
  searchLink: "taxmate.api.resource.search_link",
  getVersions: "taxmate.api.resource.get_versions",
  runReport: "taxmate.api.reports.run_report",
  listReports: "taxmate.api.reports.list_reports",
  reportBadges: "taxmate.api.report_badges.get_report_badges",
  fulfilmentSummary: "taxmate.api.sales_order.fulfilment_summary",
  salesOrderLinks: "taxmate.api.sales_order.linked_documents",
  draftPurchaseInvoiceFromIncoming: "taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice.create_purchase_invoice",
  makeDeliveryNote: "taxmate.api.sales_order.make_delivery_note",
  makeSalesInvoice: "taxmate.api.sales_order.make_sales_invoice",
  makePurchaseReceipt: "taxmate.api.purchase_order.make_purchase_receipt",
  makePurchaseInvoice: "taxmate.api.purchase_order.make_purchase_invoice",
  makeDnSalesInvoice: "taxmate.api.delivery_note.make_sales_invoice",
  makeDnReturn: "taxmate.api.delivery_note.make_return",
  makePrPurchaseInvoice: "taxmate.api.purchase_receipt.make_purchase_invoice",
  makePrReturn: "taxmate.api.purchase_receipt.make_return",
  itemQty: "taxmate.api.stock.item_qty",
  stockEntryItemDetails: "taxmate.api.stock.stock_entry_item_details",
  reconciliationBalance: "taxmate.api.stock.reconciliation_balance",
  makeQuotationSO: "taxmate.api.quotation.make_sales_order",
  makeMrPO: "taxmate.api.material_request.make_purchase_order",
  mrDefaultSuppliers: "taxmate.api.material_request.get_item_default_suppliers",
  makeMrPOs: "taxmate.api.material_request.make_purchase_orders_by_supplier",
  makeMrSE: "taxmate.api.material_request.make_stock_entry",
  awesomeSearch: "taxmate.api.search.awesome",
  generateEInvoice: "taxmate.uae_e_invoicing.utils.e_invoice.generate_e_invoice",
  bulkGenerateEInvoices: "taxmate.uae_e_invoicing.utils.e_invoice.bulk_generate_e_invoices",
  syncEInvoiceStatus: "taxmate.uae_e_invoicing.utils.e_invoice.sync_status_from_asp",
  fetchEInvoiceDocuments: "taxmate.uae_e_invoicing.utils.e_invoice.fetch_asp_documents",
  getOrCreateVat201: "taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.get_or_create",
  generateVat201: "taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.generate_filing",
  listUsers: "taxmate.api.users.list_users",
  getUser: "taxmate.api.users.get_user",
  inviteUser: "taxmate.api.users.invite_user",
  onboardCompanyOwner: "taxmate.api.users.onboard_company_owner",
  updateUser: "taxmate.api.users.update_user",
  setUserRole: "taxmate.api.users.set_user_role",
  setUserEnabled: "taxmate.api.users.set_user_enabled",
  resetUserPassword: "taxmate.api.users.reset_user_password",
  getProfile: "taxmate.api.users.get_profile",
  updateProfile: "taxmate.api.users.update_profile",
  changePassword: "taxmate.api.users.change_password",
  getUnclearedTransactions: "taxmate.api.bank_reconciliation.get_uncleared_transactions",
  markCleared: "taxmate.api.bank_reconciliation.mark_cleared",
  makeSupplierQuotationPO: "taxmate.api.supplier_quotation.make_purchase_order",
  convertLeadToCustomer: "taxmate.api.lead.convert_to_customer",
  makePickListFromDn: "taxmate.api.pick_list.make_pick_list_from_dn",
  setPickListItemLocations: "taxmate.api.pick_list.set_item_locations",
  getFeatureFlags: "taxmate.api.settings.get_feature_flags",
} as const;


function splitErrorText(raw: string): string[] {
  return raw
    .split(/<br\s*\/?>/i)
    .map((s) => s.replace(/<[^>]+>/g, "").replace(/^(?:[\w.]+\.)?(?:[\w]+Error|Exception):\s*/g, "").trim())
    .filter(Boolean);
}

/** Server errors arrive as HTML, often several messages joined by <br>. */
export function readableError(err: unknown): string[] {
  if (typeof err === "string") {
    const lines = splitErrorText(err);
    return lines.length ? lines : ["Something went wrong."];
  }
  const e = err as { message?: string; exception?: string; _server_messages?: string };
  let raw = "";
  if (e?._server_messages) {
    try {
      raw = (JSON.parse(e._server_messages) as string[])
        .map((m) => {
          try {
            return (JSON.parse(m) as { message?: string }).message ?? m;
          } catch {
            return m;
          }
        })
        .join("<br>");
    } catch {
      raw = e._server_messages;
    }
  }
  raw = raw || e?.message || e?.exception || "Something went wrong.";
  const lines = splitErrorText(raw);
  return lines.length ? lines : ["Something went wrong."];
}
