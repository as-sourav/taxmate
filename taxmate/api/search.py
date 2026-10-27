"""AwesomeBar-style search for the TaxMate SPA.

Returns grouped hits with routes under /taxmate only, never Desk /app/.
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, cstr

from taxmate.api.resource import is_allowed_doctype, require_login
from taxmate.api.spa_routes import SPA_DOC_ROUTES as _SPA_DOC_ROUTES
from taxmate.api.spa_routes import doc_route as _doc_route
from taxmate.search import GLOBAL_SEARCH_DOCTYPES
from taxmate.utils.company import get_default_company, owning_company_field

_SPA_LIST_ROUTES: dict[str, str] = {
	"Customer": "/customers",
	"Supplier": "/suppliers",
	"Sales Order": "/orders",
	"Delivery Note": "/delivery-notes",
	"Sales Invoice": "/invoices",
	"Purchase Invoice": "/purchase-invoices",
	"Purchase Order": "/purchase-orders",
	"Purchase Receipt": "/purchase-receipts",
	"Stock Entry": "/stock-entries",
	"Stock Reconciliation": "/stock-reconciliations",
	"Material Request": "/material-requests",
	"Quotation": "/quotations",
	"UAE Incoming Invoice": "/incoming-invoices",
	"Journal Entry": "/journals",
	"Account": "/accounts",
	"Warehouse": "/warehouses",
	"Sales Taxes and Charges Template": "/tax-templates",
	"Purchase Taxes and Charges Template": "/tax-templates",
	"Payment Entry": "/payments",
	"Item": "/catalogue/items",
	"Item Group": "/catalogue/item-groups",
	"Brand": "/catalogue/brands",
	"UOM": "/catalogue/uoms",
	"UAE VAT 201 Filing Log": "/vat-201",
	"UAE CT Filing Log": "/ct-filings",
	"UAE ESR Filing": "/esr",
	"UAE UBO Register": "/ubo",
	"UAE Late Filing Notice": "/late-filings",
	"Bank Account": "/bank-accounts",
	"Mode of Payment": "/modes-of-payment",
	"Payment Terms Template": "/payment-terms-templates",
	"Price List": "/price-lists",
	"Serial No": "/serial-nos",
	"Batch": "/batches",
	"Landed Cost Voucher": "/landed-cost-vouchers",
	"Pricing Rule": "/pricing-rules",
	"Customer Group": "/customer-groups",
	"Supplier Group": "/supplier-groups",
	"Territory": "/territories",
	# Phase 11-15 new screens
	"Tax Category": "/tax-categories",
	"Item Tax Template": "/item-tax-templates",
	"Address": "/addresses",
	"Contact": "/contacts",
	"Fiscal Year": "/fiscal-years",
	"Terms and Conditions": "/terms-and-conditions",
	"Supplier Quotation": "/supplier-quotations",
	"Lead": "/leads",
	"UAE Related Party": "/uae-related-parties",
	"UAE VAT Group": "/uae-vat-groups",
	"UAE Bad Debt Relief": "/uae-bad-debt-relief",
	"UAE Customs Declaration": "/uae-customs-declarations",
	"UAE Capital Goods Adjustment": "/uae-capital-goods-adjustments",
	"BOM": "/boms",
	"Work Order": "/work-orders",
	"Pick List": "/pick-lists",
	"POS Invoice": "/pos-invoices",
	"POS Profile": "/pos-profiles",
	"Loyalty Program": "/loyalty-programs",
	"Loyalty Point Entry": "/loyalty-point-entries",
	"Currency Exchange": "/currency-exchanges",
	"Asset Category": "/asset-categories",
	"Asset": "/assets",
	"Opportunity": "/opportunities",
	"Request for Quotation": "/request-for-quotations",
	"Shipment": "/shipments",
	"Installation Note": "/installation-notes",
	"Delivery Trip": "/delivery-trips",
	"Payment Request": "/payment-requests",
	"Subcontracting Order": "/subcontracting-orders",
	"Subcontracting Inward Order": "/subcontracting-inward-orders",
}

# In-app pages (AwesomeBar “pages” feel) — SPA routes only.
_NAV_PAGES: tuple[dict[str, str], ...] = (
	{"label": "Dashboard", "route": "/", "keywords": "home overview kpi books"},
	{"label": "Sales Orders", "route": "/orders", "keywords": "home dashboard sales order so"},
	{"label": "Delivery Notes", "route": "/delivery-notes", "keywords": "dn delivery note despatch"},
	{
		"label": "Stock Entries",
		"route": "/stock-entries",
		"keywords": "stock entry material receipt issue transfer",
	},
	{
		"label": "Stock Reconciliation",
		"route": "/stock-reconciliations",
		"keywords": "stock count opening reconciliation",
	},
	{"label": "Material Requests", "route": "/material-requests", "keywords": "material request indent mr"},
	{"label": "Quotations", "route": "/quotations", "keywords": "quotation quote estimate"},
	{"label": "Customers", "route": "/customers", "keywords": "customer party"},
	{"label": "Suppliers", "route": "/suppliers", "keywords": "supplier vendor purchase party"},
	{
		"label": "Purchase Invoices",
		"route": "/purchase-invoices",
		"keywords": "purchase invoice bill pi vendor",
	},
	{"label": "Purchase Orders", "route": "/purchase-orders", "keywords": "purchase order po buying"},
	{
		"label": "Purchase Receipts",
		"route": "/purchase-receipts",
		"keywords": "purchase receipt pr goods received grn",
	},
	{
		"label": "Incoming e-Invoices",
		"route": "/incoming-invoices",
		"keywords": "incoming einvoice peppol received supplier bill asp",
	},
	{"label": "Sales Invoices", "route": "/invoices", "keywords": "sales invoice bill invoices"},
	{"label": "Payments", "route": "/payments", "keywords": "payment receipt"},
	{"label": "Receivables", "route": "/receivables", "keywords": "ar outstanding"},
	{"label": "Payables", "route": "/payables", "keywords": "ap aged payable supplier outstanding"},
	{
		"label": "Journal Entries",
		"route": "/journals",
		"keywords": "journal entry je voucher books ledger posting",
	},
	{
		"label": "Chart of Accounts",
		"route": "/accounts",
		"keywords": "chart of accounts coa ledger account tree",
	},
	{
		"label": "Reports",
		"route": "/reports",
		"keywords": "trial balance general ledger profit loss balance sheet cash flow reports vat 201 late filing esr compliance emaratax",
	},
	{"label": "Items", "route": "/catalogue/items", "keywords": "item product catalogue"},
	{
		"label": "Item Groups",
		"route": "/catalogue/item-groups",
		"keywords": "item group category catalogue tree",
	},
	{"label": "Brands", "route": "/catalogue/brands", "keywords": "brand manufacturer label"},
	{"label": "UOMs", "route": "/catalogue/uoms", "keywords": "uom unit of measure uom nos kg litre"},
	{"label": "Warehouses", "route": "/warehouses", "keywords": "warehouse stock location store"},
	{
		"label": "Tax Templates",
		"route": "/tax-templates",
		"keywords": "tax template vat sales purchase charges",
	},
	{"label": "VAT 201", "route": "/vat-201", "keywords": "vat 201 fta filing return boxes deadline"},
	{"label": "Corporate Tax", "route": "/ct-filings", "keywords": "corporate tax ct filing log worksheet"},
	{"label": "ESR", "route": "/esr", "keywords": "esr economic substance notification report"},
	{"label": "UBO Register", "route": "/ubo", "keywords": "ubo beneficial owner register"},
	{"label": "Late Filings", "route": "/late-filings", "keywords": "late filing notice overdue fta"},
	{"label": "E-Invoice Log", "route": "/e-invoice-log", "keywords": "einvoice peppol asp"},
	{
		"label": "E-Invoice ASP",
		"route": "/tax-settings",
		"keywords": "asp uae tax settings e-invoice einvoice complyance pint-ae access point",
	},
	{
		"label": "Team",
		"route": "/team",
		"keywords": "users roles team staff invite admin finance manager accounts user auditor owner accountant clerk viewer",
	},
	{"label": "Profile", "route": "/profile", "keywords": "profile password phone mobile name account me"},
	{"label": "Bank Accounts", "route": "/bank-accounts", "keywords": "bank account banking cash gl"},
	{
		"label": "Modes of Payment",
		"route": "/modes-of-payment",
		"keywords": "mode of payment cash bank general payment method",
	},
	{
		"label": "Payment Terms Templates",
		"route": "/payment-terms-templates",
		"keywords": "payment terms template net 30 days due date credit period",
	},
	{
		"label": "Price Lists",
		"route": "/price-lists",
		"keywords": "price list selling buying rate currency standard",
	},
	{
		"label": "Serial Numbers",
		"route": "/serial-nos",
		"keywords": "serial no number serialised traceable lot",
	},
	{"label": "Batches", "route": "/batches", "keywords": "batch lot expiry manufacturing date"},
	{
		"label": "Landed Cost Vouchers",
		"route": "/landed-cost-vouchers",
		"keywords": "landed cost voucher lcv freight customs duty charges allocation",
	},
	{
		"label": "Pricing Rules",
		"route": "/pricing-rules",
		"keywords": "pricing rule discount rate promotion item customer brand",
	},
	{
		"label": "Customer Groups",
		"route": "/customer-groups",
		"keywords": "customer group category classification party",
	},
	{
		"label": "Supplier Groups",
		"route": "/supplier-groups",
		"keywords": "supplier group vendor category classification",
	},
	{
		"label": "Territories",
		"route": "/territories",
		"keywords": "territory region zone sales area geography",
	},
	# Phase 11
	{
		"label": "Tax Categories",
		"route": "/tax-categories",
		"keywords": "tax category vat reverse charge uae",
	},
	{
		"label": "Item Tax Templates",
		"route": "/item-tax-templates",
		"keywords": "item tax template rate exemption zero rated",
	},
	# Phase 12
	{"label": "Addresses", "route": "/addresses", "keywords": "address billing shipping emirate location"},
	{"label": "Contacts", "route": "/contacts", "keywords": "contact person phone email mobile"},
	# Phase 13
	{"label": "Fiscal Years", "route": "/fiscal-years", "keywords": "fiscal year period accounting year"},
	{
		"label": "Chart of Accounts New",
		"route": "/accounts/new",
		"keywords": "create account leaf coa opening balance",
	},
	# Phase 14
	{
		"label": "Bank Reconciliation",
		"route": "/bank-reconciliation",
		"keywords": "bank reconciliation statement clearance uncleared",
	},
	# Phase 15
	{
		"label": "Terms and Conditions",
		"route": "/terms-and-conditions",
		"keywords": "terms conditions sales note template payment",
	},
	# Phase 16
	{
		"label": "Supplier Quotations",
		"route": "/supplier-quotations",
		"keywords": "supplier quotation rfq request for quotation vendor price",
	},
	# Phase 17/18
	{"label": "BOMs", "route": "/boms", "keywords": "bill of materials bom manufacturing component"},
	{"label": "Work Orders", "route": "/work-orders", "keywords": "work order manufacture production job"},
	# Phase 21
	{"label": "Leads", "route": "/leads", "keywords": "lead prospect crm potential customer sales inquiry"},
	{"label": "Opportunities", "route": "/opportunities", "keywords": "opportunity crm enquiry lead customer"},
	{"label": "Requests for Quotation", "route": "/request-for-quotations", "keywords": "request for quotation rfq supplier"},
	{"label": "Shipments", "route": "/shipments", "keywords": "shipment delivery dispatch parcel"},
	{"label": "Installation Notes", "route": "/installation-notes", "keywords": "installation note install delivery"},
	{"label": "Delivery Trips", "route": "/delivery-trips", "keywords": "delivery trip driver vehicle route"},
	{"label": "Payment Requests", "route": "/payment-requests", "keywords": "payment request collect pay"},
	{"label": "Subcontracting Orders", "route": "/subcontracting-orders", "keywords": "subcontracting order job worker purchase"},
	{"label": "Subcontracting Inward Orders", "route": "/subcontracting-inward-orders", "keywords": "subcontracting inward order customer sales"},
	# Phase 22 — UAE compliance write screens
	{
		"label": "UAE Related Parties",
		"route": "/uae-related-parties",
		"keywords": "ct corporate tax related party disclosure",
	},
	{"label": "UAE VAT Groups", "route": "/uae-vat-groups", "keywords": "vat group representative trn"},
	{
		"label": "UAE Bad Debt Relief",
		"route": "/uae-bad-debt-relief",
		"keywords": "bad debt vat relief write off",
	},
	{
		"label": "UAE Customs Declarations",
		"route": "/uae-customs-declarations",
		"keywords": "customs declaration import vat",
	},
	{
		"label": "UAE Capital Goods Adjustments",
		"route": "/uae-capital-goods-adjustments",
		"keywords": "capital goods adjustment vat",
	},
	{"label": "Pick Lists", "route": "/pick-lists", "keywords": "pick list picking delivery"},
	{"label": "POS Invoices", "route": "/pos-invoices", "keywords": "pos point of sale invoice retail"},
	{"label": "POS Profiles", "route": "/pos-profiles", "keywords": "pos profile point of sale setup"},
	{"label": "Loyalty Programs", "route": "/loyalty-programs", "keywords": "loyalty program points rewards"},
	{"label": "Loyalty Points", "route": "/loyalty-point-entries", "keywords": "loyalty points entries"},
	{
		"label": "Currency Exchange",
		"route": "/currency-exchanges",
		"keywords": "currency exchange rate forex fx",
	},
	{"label": "Assets", "route": "/assets", "keywords": "fixed asset asset register"},
	{"label": "Asset Categories", "route": "/asset-categories", "keywords": "asset category fixed assets"},
)

_SPA_DOCTYPES = frozenset(_SPA_DOC_ROUTES)


def _in_active_company(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Drop document hits that belong to a company other than the active one."""
	company = get_default_company()
	if not company:
		return hits
	by_doctype: dict[str, list[str]] = {}
	for hit in hits:
		if hit.get("type") == "document" and owning_company_field(hit["doctype"]):
			by_doctype.setdefault(hit["doctype"], []).append(hit["name"])
	keep: set[tuple[str, str]] = set()
	for doctype, names in by_doctype.items():
		field = owning_company_field(doctype)
		filters: dict[str, Any] = {"name": ["in", names]}
		# Mandatory link: equality. Optional link: the permission query keeps
		# this company and untagged rows, and get_list applies that query.
		if field and field[1]:
			filters[field[0]] = company
		for name in frappe.get_list(
			doctype,
			filters=filters,
			pluck="name",
			limit=len(names),
		):
			keep.add((doctype, name))
	return [
		hit
		for hit in hits
		if hit.get("type") != "document"
		or hit.get("doctype") not in by_doctype
		or (hit["doctype"], hit["name"]) in keep
	]


def _list_route(doctype: str) -> str | None:
	return _SPA_LIST_ROUTES.get(doctype)


def _fuzzy_score(query: str, text: str) -> float:
	"""Simple subsequence score in [0, 1]. Higher is better."""
	q = cstr(query).lower().strip()
	t = cstr(text).lower()
	if not q or not t:
		return 0.0
	if q == t:
		return 1.0
	if t.startswith(q):
		return 0.95
	if q in t:
		return 0.8
	ti = 0
	matched = 0
	for ch in q:
		found = t.find(ch, ti)
		if found < 0:
			return 0.0
		matched += 1
		ti = found + 1
	return 0.4 * (matched / max(len(t), 1))


def _nav_results(text: str, limit: int) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for page in _NAV_PAGES:
		hay = f"{page['label']} {page['keywords']}"
		score = _fuzzy_score(text, hay)
		if score <= 0:
			continue
		out.append(
			{
				"type": "page",
				"title": page["label"],
				"description": _("Go to {0}").format(page["label"]),
				"route": page["route"],
				"score": score,
			}
		)
	out.sort(key=lambda r: r["score"], reverse=True)
	return out[:limit]


def _doctype_list_results(text: str, limit: int) -> list[dict[str, Any]]:
	"""Match DocType titles like AwesomeBar 'List Customer' — SPA lists only."""
	out: list[dict[str, Any]] = []
	can_read = set(frappe.get_user().get_can_read())
	for doctype in _SPA_DOCTYPES:
		if doctype not in can_read or not is_allowed_doctype(doctype):
			continue
		route = _list_route(doctype)
		if not route:
			continue
		score = max(_fuzzy_score(text, doctype), _fuzzy_score(text, f"list {doctype}"))
		if score < 0.4:
			continue
		out.append(
			{
				"type": "list",
				"doctype": doctype,
				"title": _("List {0}").format(doctype),
				"description": doctype,
				"route": route,
				"score": score,
			}
		)
	out.sort(key=lambda r: r["score"], reverse=True)
	return out[:limit]


def _global_results(text: str, limit: int) -> list[dict[str, Any]]:
	from frappe.utils.global_search import search as frappe_global_search

	allowed = {dt for dt in GLOBAL_SEARCH_DOCTYPES if dt in _SPA_DOCTYPES and is_allowed_doctype(dt)}
	if not allowed:
		return []

	raw = frappe_global_search(text=text, start=0, limit=limit, doctype="")
	out: list[dict[str, Any]] = []
	seen: set[tuple[str, str]] = set()
	for row in raw or []:
		doctype = row.get("doctype")
		name = row.get("name")
		if not doctype or not name or doctype not in allowed:
			continue
		route = _doc_route(doctype, name)
		if not route:
			continue
		key = (doctype, name)
		if key in seen:
			continue
		seen.add(key)
		title = cstr(row.get("title") or name)
		content = cstr(row.get("content") or "")
		description = re.sub(r"<[^>]+>", " ", content)
		description = re.sub(r"\s+", " ", description).strip()
		if len(description) > 120:
			description = description[:117] + "…"
		out.append(
			{
				"type": "document",
				"doctype": doctype,
				"name": name,
				"title": title,
				"description": description or doctype,
				"route": route,
				"score": float(row.get("rank") or 0),
			}
		)
		if len(out) >= limit:
			break
	return out


def _exact_name_hits(text: str, limit: int) -> list[dict[str, Any]]:
	"""If the query looks like a document name, try exact matches on SPA doctypes."""
	if " " in text.strip() and not re.search(r"-\d", text):
		return []
	out: list[dict[str, Any]] = []
	for doctype in _SPA_DOCTYPES:
		if doctype not in _SPA_DOCTYPES:
			continue
		if not is_allowed_doctype(doctype) or not frappe.has_permission(doctype, "read"):
			continue
		if not frappe.db.exists(doctype, text):
			continue
		route = _doc_route(doctype, text)
		if not route:
			continue
		out.append(
			{
				"type": "document",
				"doctype": doctype,
				"name": text,
				"title": text,
				"description": doctype,
				"route": route,
				"score": 1.0,
			}
		)
		if len(out) >= limit:
			break
	return out


@frappe.whitelist()
def awesome(text: str = "", limit: int = 20) -> dict[str, Any]:
	"""Return grouped AwesomeBar-style hits for the SPA search field (SPA routes only)."""
	require_login()
	text = cstr(text).strip()
	limit = max(1, min(cint(limit) or 20, 50))
	if not text:
		return {"query": text, "groups": []}

	pages = _nav_results(text, limit=8)
	lists = _doctype_list_results(text, limit=8)
	exact = _exact_name_hits(text, limit=5)
	# Over-fetch: hits from other companies are dropped after the limit.
	documents = _global_results(text, limit=limit * 3)

	doc_keys = {(d["doctype"], d["name"]) for d in exact}
	documents = exact + [d for d in documents if (d["doctype"], d["name"]) not in doc_keys]
	documents = _in_active_company(documents)[:limit]

	groups: list[dict[str, Any]] = []
	if pages:
		groups.append({"title": _("Pages"), "results": pages})
	if lists:
		groups.append({"title": _("Lists"), "results": lists})
	if documents:
		groups.append({"title": _("Documents"), "results": documents[:limit]})

	return {"query": text, "groups": groups}
