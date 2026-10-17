"""TaxMate accounts API. UAE methods are catalogued, not wrapped again."""

from __future__ import annotations

from typing import Any

import frappe

from taxmate.api.resource import require_login
from taxmate.search import ALLOWED_SEARCH_DOCTYPES, DENIED_SEARCH_DOCTYPES, GLOBAL_SEARCH_DOCTYPES
from taxmate.setup.financial_reports import CORE_REPORT_LINKS, TAXMATE_REPORT_LINKS
from taxmate.setup.home import DAILY_SHORTCUTS, HOME_LINKS, UAE_SHORTCUTS
from taxmate.setup.company_owner import is_app_provider
from taxmate.setup.spa_roles import addon_roles_of, spa_role_of, spa_roles_of
from taxmate.utils.company import get_default_company

# Masters a books frontend needs that are not always in global search.
_CORE_MASTERS: tuple[str, ...] = (
	"Company",
	"Account",
	"Customer",
	"Supplier",
	"Item",
	"Warehouse",
	"Address",
	"Contact",
	"Mode of Payment",
	"Cost Center",
	"Bank Account",
	"Fiscal Year",
	"Currency",
	"Country",
	"Letter Head",
	"Holiday List",
	"Sales Taxes and Charges Template",
	"Purchase Taxes and Charges Template",
	"Item Tax Template",
	"Item Attribute",
	"Location",
	"Tax Category",
	"Payment Terms Template",
	"Price List",
	"Terms and Conditions",
	"UAE Related Party",
	"UAE VAT Group",
	"UAE Bad Debt Relief",
	"UAE Customs Declaration",
	"UAE Capital Goods Adjustment",
	"Brand",
	"UOM",
	"Customer Group",
	"Supplier Group",
	"Item Group",
	"Territory",
	"TaxMate Settings",
	"Accounts Settings",
	"Selling Settings",
	"Buying Settings",
	"Item Price",
	"ToDo",
	"Delivery Note",
	"UAE Tax Settings",
	"Stock Entry",
	"Stock Reconciliation",
	"Material Request",
	"Quotation",
	"Serial No",
	"Batch",
	"Landed Cost Voucher",
	"Pricing Rule",
	"Stock Ledger Entry",
	"Supplier Quotation",
	"Lead",
	"BOM",
	"Work Order",
	"Pick List",
	"POS Profile",
	"POS Invoice",
	"Loyalty Program",
	"Loyalty Point Entry",
	"Currency Exchange",
	"Asset Category",
	"Asset",
	"Period Closing Voucher",
	"Accounting Dimension",
)

# Existing TaxMate whitelist methods (not re-wrapped).
_EXISTING_ACTIONS: tuple[dict[str, str], ...] = (
	{
		"name": "get_uae_readiness_checklist",
		"method": "taxmate.uae.readiness.get_uae_readiness_checklist",
	},
	{
		"name": "get_e_invoice_mandate_status",
		"method": "taxmate.uae_e_invoicing.utils.mandate.get_e_invoice_mandate_status",
	},
	{
		"name": "generate_e_invoice",
		"method": "taxmate.uae_e_invoicing.utils.e_invoice.generate_e_invoice",
	},
	{
		"name": "sync_e_invoice_status",
		"method": "taxmate.uae_e_invoicing.utils.e_invoice.sync_status_from_asp",
	},
	{
		"name": "fetch_e_invoice_documents",
		"method": "taxmate.uae_e_invoicing.utils.e_invoice.fetch_asp_documents",
	},
	{
		"name": "bulk_generate_e_invoices",
		"method": "taxmate.uae_e_invoicing.utils.e_invoice.bulk_generate_e_invoices",
	},
	{
		"name": "draft_purchase_invoice_from_incoming",
		"method": "taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice.create_purchase_invoice",
	},
	{
		"name": "get_or_create_vat_201",
		"method": "taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.get_or_create",
	},
	{
		"name": "generate_vat_201",
		"method": "taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.generate_filing",
	},
	{
		"name": "get_ct_elections",
		"method": "taxmate.uae_corporate_tax.utils.corporate_tax.get_ct_elections",
	},
)


def catalog_doctypes() -> list[str]:
	names = set(GLOBAL_SEARCH_DOCTYPES)
	names.update(_CORE_MASTERS)
	for doctype in ALLOWED_SEARCH_DOCTYPES:
		if doctype.startswith(("UAE ", "TaxMate", "IDP ")):
			names.add(doctype)
	for row in (*DAILY_SHORTCUTS, *UAE_SHORTCUTS, *HOME_LINKS):
		link_to = row.get("link_to")
		kind = row.get("type") or row.get("link_type")
		if link_to and kind == "DocType":
			names.add(link_to)
	return sorted(
		name for name in names if name not in DENIED_SEARCH_DOCTYPES and frappe.db.exists("DocType", name)
	)


def catalog_reports() -> list[dict[str, str]]:
	out: list[dict[str, str]] = []
	seen: set[str] = set()
	for label, report in (*CORE_REPORT_LINKS, *TAXMATE_REPORT_LINKS):
		if report in seen:
			continue
		if not frappe.db.exists("Report", report):
			continue
		if frappe.db.get_value("Report", report, "disabled"):
			continue
		seen.add(report)
		out.append({"label": frappe._(label), "report": report})
	return out


@frappe.whitelist()
def get_catalog() -> dict[str, Any]:
	require_login()

	resources = []
	for doctype in catalog_doctypes():
		meta = frappe.get_meta(doctype)
		resources.append(
			{
				"doctype": doctype,
				"module": meta.module,
				"issingle": int(meta.issingle or 0),
				"is_submittable": int(meta.is_submittable or 0),
				"is_tree": int(meta.is_tree or 0),
			}
		)

	return {
		"resources": resources,
		"reports": catalog_reports(),
		"nav": {
			"daily": [row["label"] for row in DAILY_SHORTCUTS],
			"uae": [row["label"] for row in UAE_SHORTCUTS],
			"cards": [row["label"] for row in HOME_LINKS if row.get("type") == "Card Break"],
		},
		"actions": [
			{"name": "list_my_companies", "method": "taxmate.api.company.list_my_companies"},
			{"name": "switch_company", "method": "taxmate.api.company.switch_company"},
			{"name": "list_company_addresses", "method": "taxmate.api.company.list_company_addresses"},
			{"name": "upload_company_logo", "method": "taxmate.api.company.upload_company_logo"},
			{"name": "get_uae_tax_settings", "method": "taxmate.api.tax_settings.get_uae_tax_settings"},
			{"name": "save_uae_tax_settings", "method": "taxmate.api.tax_settings.save_uae_tax_settings"},
			{"name": "get_list", "method": "taxmate.api.resource.get_list"},
			{"name": "get", "method": "taxmate.api.resource.get"},
			{"name": "insert", "method": "taxmate.api.resource.insert"},
			{"name": "save", "method": "taxmate.api.resource.save"},
			{"name": "delete", "method": "taxmate.api.resource.delete"},
			{"name": "bulk_delete", "method": "taxmate.api.resource.bulk_delete"},
			{"name": "get_count", "method": "taxmate.api.resource.get_count"},
			{"name": "group_by_count", "method": "taxmate.api.resource.group_by_count"},
			{"name": "get_meta", "method": "taxmate.api.resource.get_meta"},
			{"name": "search_link", "method": "taxmate.api.resource.search_link"},
			{"name": "get_versions", "method": "taxmate.api.resource.get_versions"},
			{"name": "submit", "method": "taxmate.api.workflow.submit"},
			{"name": "cancel", "method": "taxmate.api.workflow.cancel"},
			{"name": "amend", "method": "taxmate.api.workflow.amend"},
			{"name": "get_party_details", "method": "taxmate.api.accounts.get_party_details"},
			{"name": "get_item_details", "method": "taxmate.api.accounts.get_item_details"},
			{"name": "apply_price_list", "method": "taxmate.api.accounts.apply_price_list"},
			{"name": "apply_pricing_rule", "method": "taxmate.api.accounts.apply_pricing_rule"},
			{"name": "get_taxes_and_charges", "method": "taxmate.api.accounts.get_taxes_and_charges"},
			{"name": "get_conversion_factor", "method": "taxmate.api.accounts.get_conversion_factor"},
			{"name": "get_exchange_rate", "method": "taxmate.api.accounts.get_exchange_rate"},
			{"name": "get_payment_terms", "method": "taxmate.api.accounts.get_payment_terms"},
			{"name": "get_credit_balance", "method": "taxmate.api.accounts.get_credit_balance"},
			{"name": "preview_taxes_and_totals", "method": "taxmate.api.accounts.preview_taxes_and_totals"},
			{"name": "get_account_tree", "method": "taxmate.api.accounts.get_account_tree"},
			{"name": "get_defaults", "method": "taxmate.api.accounts.get_defaults"},
			{"name": "get_outstanding_invoices", "method": "taxmate.api.accounts.get_outstanding_invoices"},
			{"name": "get_payment_entry", "method": "taxmate.api.accounts.get_payment_entry"},
			{"name": "resolve_payment_accounts", "method": "taxmate.api.accounts.resolve_payment_accounts"},
			{
				"name": "resolve_internal_transfer_accounts",
				"method": "taxmate.api.accounts.resolve_internal_transfer_accounts",
			},
			{"name": "get_je_account_details", "method": "taxmate.api.accounts.get_je_account_details"},
			{"name": "get_je_party_account", "method": "taxmate.api.accounts.get_je_party_account"},
			{"name": "get_accounting_dimensions", "method": "taxmate.api.accounts.get_accounting_dimensions"},
			{"name": "make_sales_return", "method": "taxmate.api.accounts.make_sales_return"},
			{"name": "make_purchase_return", "method": "taxmate.api.accounts.make_purchase_return"},
			{"name": "run_report", "method": "taxmate.api.reports.run_report"},
			{"name": "list_reports", "method": "taxmate.api.reports.list_reports"},
			{"name": "get_report_badges", "method": "taxmate.api.report_badges.get_report_badges"},
			{"name": "get_home", "method": "taxmate.api.dashboard.get_home"},
			{
				"name": "fulfilment_summary",
				"method": "taxmate.api.sales_order.fulfilment_summary",
			},
			{"name": "linked_documents", "method": "taxmate.api.sales_order.linked_documents"},
			{"name": "make_delivery_note", "method": "taxmate.api.sales_order.make_delivery_note"},
			{"name": "make_sales_invoice", "method": "taxmate.api.sales_order.make_sales_invoice"},
			{"name": "make_purchase_receipt", "method": "taxmate.api.purchase_order.make_purchase_receipt"},
			{"name": "make_purchase_invoice", "method": "taxmate.api.purchase_order.make_purchase_invoice"},
			{"name": "make_dn_sales_invoice", "method": "taxmate.api.delivery_note.make_sales_invoice"},
			{"name": "make_dn_return", "method": "taxmate.api.delivery_note.make_return"},
			{
				"name": "make_pr_purchase_invoice",
				"method": "taxmate.api.purchase_receipt.make_purchase_invoice",
			},
			{"name": "make_pr_return", "method": "taxmate.api.purchase_receipt.make_return"},
			{"name": "item_qty", "method": "taxmate.api.stock.item_qty"},
			{"name": "stock_entry_item_details", "method": "taxmate.api.stock.stock_entry_item_details"},
			{"name": "reconciliation_balance", "method": "taxmate.api.stock.reconciliation_balance"},
			{"name": "make_quotation_so", "method": "taxmate.api.quotation.make_sales_order"},
			{"name": "make_mr_purchase_order", "method": "taxmate.api.material_request.make_purchase_order"},
			{
				"name": "mr_item_default_suppliers",
				"method": "taxmate.api.material_request.get_item_default_suppliers",
			},
			{
				"name": "make_mr_purchase_orders_by_supplier",
				"method": "taxmate.api.material_request.make_purchase_orders_by_supplier",
			},
			{"name": "make_mr_stock_entry", "method": "taxmate.api.material_request.make_stock_entry"},
			{
				"name": "get_uncleared_transactions",
				"method": "taxmate.api.bank_reconciliation.get_uncleared_transactions",
			},
			{"name": "mark_cleared", "method": "taxmate.api.bank_reconciliation.mark_cleared"},
			{
				"name": "make_supplier_quotation_po",
				"method": "taxmate.api.supplier_quotation.make_purchase_order",
			},
			{"name": "convert_lead_to_customer", "method": "taxmate.api.lead.convert_to_customer"},
			{
				"name": "make_pick_list_from_dn",
				"method": "taxmate.api.pick_list.make_pick_list_from_dn",
			},
			{
				"name": "set_pick_list_item_locations",
				"method": "taxmate.api.pick_list.set_item_locations",
			},
			{
				"name": "get_feature_flags",
				"method": "taxmate.api.settings.get_feature_flags",
			},
			{"name": "awesome_search", "method": "taxmate.api.search.awesome"},
			{"name": "list_users", "method": "taxmate.api.users.list_users"},
			{"name": "get_user", "method": "taxmate.api.users.get_user"},
			{"name": "invite_user", "method": "taxmate.api.users.invite_user"},
			{"name": "onboard_company_owner", "method": "taxmate.api.users.onboard_company_owner"},
			{"name": "update_user", "method": "taxmate.api.users.update_user"},
			{"name": "set_user_role", "method": "taxmate.api.users.set_user_role"},
			{"name": "set_user_enabled", "method": "taxmate.api.users.set_user_enabled"},
			{"name": "reset_user_password", "method": "taxmate.api.users.reset_user_password"},
			{"name": "get_profile", "method": "taxmate.api.users.get_profile"},
			{"name": "update_profile", "method": "taxmate.api.users.update_profile"},
			{"name": "change_password", "method": "taxmate.api.users.change_password"},
			{"name": "update_ui_preferences", "method": "taxmate.api.ui_prefs.update_ui_preferences"},
			{"name": "get_session", "method": "taxmate.api.get_session"},
			{"name": "get_catalog", "method": "taxmate.api.get_catalog"},
			{"name": "owner_dashboard", "method": "taxmate.api.owner_dashboard.get_owner_dashboard"},
			{
				"name": "accountant_dashboard",
				"method": "taxmate.api.accountant_dashboard.get_accountant_dashboard",
			},
			{
				"name": "clients_dashboard",
				"method": "taxmate.api.clients_dashboard.get_clients_dashboard",
			},
			{"name": "idp_surface", "method": "taxmate.api.idp_desk.get_surface"},
			{"name": "idp_upload", "method": "taxmate.api.idp_desk.upload"},
			{"name": "idp_run", "method": "taxmate.api.idp_desk.run"},
			{"name": "idp_save", "method": "taxmate.api.idp_desk.save"},
			*_EXISTING_ACTIONS,
		],
	}


@frappe.whitelist()
def get_session() -> dict[str, Any]:
	require_login()

	company = get_default_company()
	currency = None
	country = None
	if company and frappe.has_permission("Company", "read", company):
		currency, country = frappe.db.get_value("Company", company, ["default_currency", "country"]) or (
			None,
			None,
		)

	provider = is_app_provider()
	from taxmate.api.ui_prefs import read_ui_prefs

	prefs = read_ui_prefs()
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"company": company,
		"currency": currency,
		"country": country,
		"roles": frappe.get_roles(),
		"spa_role": spa_role_of(),
		"spa_roles": spa_roles_of(),
		"extra_roles": addon_roles_of(),
		"is_app_provider": provider,
		# The SITE's today, not the browser's. Anything date-driven in the UI
		# -- most of all whether an invoice is overdue -- has to agree with the
		# server, and a viewer outside Asia/Dubai is a day off for part of it.
		"today": frappe.utils.today(),
		"time_zone": frappe.utils.get_system_timezone(),
		# User.language + User.desk_theme (SPA lang/theme aliases).
		"language": prefs.get("language"),
		"desk_theme": prefs.get("desk_theme"),
		"lang": prefs.get("lang"),
		"theme": prefs.get("theme"),
	}
