"""Dashboard view of IDP. Decisions live here. The SPA only renders them.

IDP's agent has more tools than a clerk should see. This module lists the
jobs a person can start from the TaxMate dashboard, drops anything they
cannot permission, and refuses Desk links.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Same set as idp.core.constants.SUPPORTED_DOCTYPES. A test checks they match
# when the IDP app is importable.
TARGETS: tuple[dict[str, str | None], ...] = (
	{"doctype": "Opportunity", "route": None},
	{"doctype": "Sales Invoice", "route": "/invoices"},
	{"doctype": "Purchase Invoice", "route": "/purchase-invoices"},
	{"doctype": "Quotation", "route": "/quotations"},
	{"doctype": "Sales Order", "route": "/orders"},
	{"doctype": "Supplier Quotation", "route": "/supplier-quotations"},
	{"doctype": "Purchase Order", "route": "/purchase-orders"},
	{"doctype": "Delivery Note", "route": "/delivery-notes"},
	{"doctype": "Purchase Receipt", "route": "/purchase-receipts"},
	{"doctype": "Payment Entry", "route": "/payments"},
	{"doctype": "Journal Entry", "route": "/journals"},
)

# What the scan dialog offers. The other TARGETS stay available to IDP
# tooling. A clerk scans a bill, a purchase, a quote, or a payment.
SCAN_DOCTYPES: frozenset[str] = frozenset({
	"Sales Invoice",
	"Purchase Invoice",
	"Quotation",
	"Payment Entry",
})

# User-facing IDP jobs. Internal tools (ask_user, audit, validate,
# read_attachment_more) are not jobs. create_master is not a job: the scan
# never invents masters alone. Supplier / Customer / Item may be proposed and
# created only after the clerk confirms (taxmate.idp.masters).
# Local OCR feeds compare, match, and update. None of these jobs call the model.
JOBS: tuple[dict[str, Any], ...] = (
	{
		"id": "create",
		"needs_file": True,
		"needs_target": True,
		"needs_query": False,
		"permission": "create",
		"needs_model": False,
		"runnable": True,
		"query_key": None,
		"run_key": "idp.read",
		"save_key": "idp.save",
	},
	{
		"id": "compare",
		"needs_file": True,
		"needs_target": True,
		"needs_query": True,
		"permission": "read",
		"needs_model": False,
		"runnable": True,
		"query_key": "idp.query.doc",
		"run_key": "idp.compare",
		"save_key": None,
	},
	{
		"id": "search",
		"needs_file": False,
		"needs_target": True,
		"needs_query": True,
		"permission": "read",
		"needs_model": False,
		"runnable": True,
		"query_key": "idp.query.find",
		"run_key": "idp.find",
		"save_key": None,
	},
	{
		"id": "update",
		"needs_file": True,
		"needs_target": True,
		"needs_query": True,
		"permission": "write",
		"needs_model": False,
		"runnable": True,
		"query_key": "idp.query.doc",
		"run_key": "idp.update",
		"save_key": "idp.apply",
	},
	{
		"id": "match",
		"needs_file": True,
		"needs_target": True,
		"needs_query": False,
		"permission": "read",
		"needs_model": False,
		"runnable": True,
		"query_key": None,
		"run_key": "idp.match",
		"save_key": None,
	},
	{
		"id": "delete",
		"needs_file": False,
		"needs_target": True,
		"needs_query": True,
		"permission": "delete",
		"needs_model": False,
		"runnable": True,
		"query_key": "idp.query.doc",
		"run_key": "idp.delete",
		"save_key": "idp.deleteConfirm",
	},
)

# Equality field used when a find box is not a document name.
PARTY_FIELD: dict[str, str] = {
	"Sales Invoice": "customer",
	"Purchase Invoice": "supplier",
	"Quotation": "party_name",
	"Sales Order": "customer",
	"Supplier Quotation": "supplier",
	"Purchase Order": "supplier",
	"Delivery Note": "customer",
	"Purchase Receipt": "supplier",
	"Payment Entry": "party",
	"Opportunity": "party_name",
}

# Panel copy stays short. Masters / language notes are not on the first screen;
# propose still appears on review when the file names an unknown party or item.
NOTICES: tuple[str, ...] = ()

# Jobs the dashboard Scan panel offers. Other JOBS rows stay for plan_run tests
# and tooling; the SPA surface is create-draft only.
SURFACE_JOB_IDS: frozenset[str] = frozenset({"create"})

READ_STAGES: tuple[dict[str, str], ...] = (
	{"key": "upload", "label_key": "idp.stage.upload"},
	{"key": "ocr", "label_key": "idp.stage.ocr"},
	{"key": "parties", "label_key": "idp.stage.parties"},
	{"key": "items", "label_key": "idp.stage.items"},
	{"key": "review", "label_key": "idp.stage.review"},
)

ACCEPT: tuple[str, ...] = (
	".pdf",
	".png",
	".jpg",
	".jpeg",
	".webp",
	".tif",
	".tiff",
	".xlsx",
	".xls",
	".csv",
	".docx",
)

# Header keys the mapper must not write onto a new document.
BLOCKED_HEADER: frozenset[str] = frozenset(
	{
		"name",
		"doctype",
		"docstatus",
		"owner",
		"amended_from",
		"creation",
		"modified",
		"modified_by",
		"idx",
		"parent",
		"parenttype",
		"parentfield",
	}
)

# Review labels. Keys that already exist on the document screens stay on f.*.
FIELD_LABELS: dict[str, str] = {
	"customer": "f.customer",
	"currency": "f.currency",
	"cost_center": "f.costCenter",
	"expense_account": "f.expenseAccount",
	"due_date": "txn.dueDate",
	"supplier": "idp.field.supplier",
	"posting_date": "idp.field.date",
	"bill_no": "idp.field.billNo",
	"taxes_and_charges": "idp.field.vat",
	"net_total": "idp.field.net",
	"grand_total": "idp.field.total",
	"remarks": "idp.field.remarks",
	"terms": "idp.field.terms",
	"company": "idp.field.company",
	"vat_emirate": "idp.field.emirate",
}

Can = Callable[[str, str], bool]


def build_surface(
	*,
	can: Can,
	llm_ready: bool,
	job_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
	"""Return the panel payload for one user.

	`can(doctype, permission)` is the only permission check. A target with
	no TaxMate route is included and marked not ready, so the screen can
	say so without linking to Desk.

	`job_ids` defaults to SURFACE_JOB_IDS (create only). Pass the full JOBS
	set when a caller needs compare / search / update for tests or tooling.
	"""
	wanted = job_ids if job_ids is not None else SURFACE_JOB_IDS
	actions: list[dict[str, Any]] = []
	for job in JOBS:
		if job["id"] not in wanted:
			continue
		perm = job["permission"]
		targets = []
		limit = SCAN_DOCTYPES if wanted == SURFACE_JOB_IDS else None
		for row in TARGETS:
			doctype = str(row["doctype"])
			if limit is not None and doctype not in limit:
				continue
			if not can(doctype, perm):
				continue
			route = row["route"]
			targets.append(
				{
					"doctype": doctype,
					"label_key": f"idp.dt.{doctype}",
					"route": route,
					"ready": bool(route),
				}
			)
		if not targets:
			continue
		needs_model = bool(job["needs_model"])
		runnable = bool(job["runnable"]) and (llm_ready or not needs_model)
		actions.append(
			{
				"id": job["id"],
				"label_key": f"idp.job.{job['id']}",
				"needs_file": bool(job["needs_file"]),
				"needs_target": bool(job["needs_target"]),
				"needs_query": bool(job["needs_query"]),
				"query_key": job.get("query_key"),
				"pick_key": {
					"search": "idp.pickName",
					"delete": "idp.pickName",
					"compare": "idp.pickDoc",
					"update": "idp.pickDoc",
				}.get(job["id"], "idp.pick"),
				"run_key": job.get("run_key") or "idp.read",
				"save_key": job.get("save_key"),
				"runnable": runnable,
				"pending_key": "idp.llm" if needs_model and not llm_ready else "idp.pending",
				"targets": targets,
			}
		)

	return {
		"title_key": "idp.title",
		"notices": list(NOTICES),
		"accept": list(ACCEPT),
		"read_stages": [dict(row) for row in READ_STAGES],
		"llm_ready": bool(llm_ready),
		"blocked_key": None,
		"actions": actions,
	}


def _extension(file_name: str) -> str:
	name = (file_name or "").rsplit("/", 1)[-1].lower()
	if "." not in name:
		return ""
	return "." + name.rsplit(".", 1)[-1]


def plan_run(
	surface: dict[str, Any],
	*,
	action: str,
	target: str | None,
	file_name: str | None,
	query: str | None = None,
) -> dict[str, Any]:
	"""Decide whether this user may run this job. Does not read the file."""
	job = next((row for row in surface.get("actions") or [] if row.get("id") == action), None)
	if not job:
		return {"ok": False, "error_key": "idp.denied"}
	if not job.get("runnable"):
		return {"ok": False, "error_key": job.get("pending_key") or "idp.pending"}
	chosen = None
	if job.get("needs_target"):
		chosen = next((row for row in job.get("targets") or [] if row.get("doctype") == target), None)
		if not chosen:
			return {"ok": False, "error_key": "idp.denied"}
		if not chosen.get("ready"):
			return {"ok": False, "error_key": "idp.noRoute"}
	if job.get("needs_file"):
		ext = _extension(file_name or "")
		if ext not in (surface.get("accept") or []):
			return {"ok": False, "error_key": "idp.file"}
	text = (query or "").strip()
	if job.get("needs_query") and not text:
		return {"ok": False, "error_key": "idp.query"}
	return {
		"ok": True,
		"action": action,
		"doctype": chosen["doctype"] if chosen else None,
		"route": chosen.get("route") if chosen else None,
		"query": text,
		"save_key": job.get("save_key"),
	}


def search_arguments(doctype: str, query: str) -> dict[str, Any]:
	"""Exact name, or the same text on the party field. IDP search is equality only."""
	text = query.strip()
	party = PARTY_FIELD.get(doctype)
	or_filters: dict[str, str] = {"name": text}
	fields = ["name"]
	if party:
		or_filters[party] = text
		fields.append(party)
	return {
		"doctype": doctype,
		"filters": {},
		"or_filters": or_filters,
		"fields": fields,
		"limit": 20,
	}


def match_filters(header: dict[str, Any]) -> dict[str, Any]:
	"""Fields a scan can use to find an existing document. Empty means the file has no handle."""
	filters: dict[str, Any] = {}
	for key in ("customer", "supplier", "bill_no", "po_no"):
		value = header.get(key)
		if value not in (None, ""):
			filters[key] = value
	return filters


def header_updates(header: dict[str, Any]) -> dict[str, Any]:
	"""Scalar header fields safe to write onto a draft."""
	updates: dict[str, Any] = {}
	for key, value in _header_rows(header).items():
		if isinstance(value, (dict, list)):
			continue
		updates[key] = value
	return updates


def draft_only_error(docstatus: int | None) -> str | None:
	if int(docstatus or 0) != 0:
		return "idp.submitted"
	return None


def matches_from_rows(rows: list[dict[str, Any]], route: str | None) -> list[dict[str, Any]]:
	found: list[dict[str, Any]] = []
	for row in rows:
		name = row.get("name")
		if not name:
			continue
		found.append(
			{
				"name": str(name),
				"label": str(name),
				"route": f"{route}/{name}" if route else None,
			}
		)
	return found


def diffs_from_compare(differences: list[dict[str, Any]]) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for row in differences:
		field = str(row.get("fieldname") or "")
		if not field or "." in field:
			continue
		rows.append(
			{
				"label_key": label_key_for(field),
				"before": "" if row.get("actual") is None else str(row.get("actual")),
				"after": "" if row.get("expected") is None else str(row.get("expected")),
				"status": str(row.get("status") or ""),
			}
		)
	return rows


def diffs_from_update(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	found: list[dict[str, Any]] = []
	for row in rows:
		if not row.get("changed"):
			continue
		field = str(row.get("fieldname") or "")
		if "." in field:
			field = field.rsplit(".", 1)[-1]
		found.append(
			{
				"label_key": label_key_for(field),
				"before": "" if row.get("before") is None else str(row.get("before")),
				"after": "" if row.get("after") is None else str(row.get("after")),
				"status": "mismatch",
			}
		)
	return found


def resolve_ocr_language(detected: str | None, known: set[str]) -> str:
	"""Turn a detector result into a PaddleOCR code. ``auto`` is not one."""
	code = (detected or "").strip().lower().split("-", 1)[0]
	if code in known:
		return code
	return "en"


def file_read_error(*, found: bool, allowed: bool) -> str | None:
	"""Refuse a file the user cannot read. Path shape is checked separately."""
	if not found or not allowed:
		return "idp.file"
	return None


def label_key_for(field: str) -> str:
	return FIELD_LABELS.get(field, f"idp.field.{field}")


# OCR noise that must not crowd the review panel (bank rails, raw aliases).
_REVIEW_NOISE: frozenset[str] = frozenset(
	{
		"iban",
		"iban_number",
		"account_number",
		"swift",
		"swift_code",
		"bank_name",
		"account_name",
		"beneficiary",
		"beneficiary_name",
		"hsn_code",
		"hsn",
		"requisition_number",
		"requisition_no",
		"bill_to",
		"bill_from",
		"sold_to",
		"sold_by",
		"vendor",
		"seller",
		"buyer",
		"client",
		"from",
		"billing_address",
		"supplier_address",
		"customer_address",
		"invoice_number",
		"invoice_no",
		"bill_number",
		"inv_no",
		"date",
		"invoice_date",
		"bill_date",
		"total",
		"total_amount",
		"amount_due",
		"total_due",
		"subtotal",
		"sub_total",
		"net_amount",
		"seller_address",
		"address_line1",
		"address_line_1",
		"address_line2",
		"city",
		"state",
		"place",
		"place_of_supply",
		"tax_invoice",
		"payment_status",
		"phone",
		"email",
		"email_id",
		"company_address",
		"po_box",
		"country",
	}
)


def _header_rows(header: dict[str, Any]) -> dict[str, Any]:
	"""Show ERPNext-shaped fields first; hide raw OCR aliases and bank rails."""
	rows: dict[str, Any] = {}
	# Prefer known document fields so the panel reads like a draft, not a dump.
	for key in [*FIELD_LABELS, "currency", "tax_id", "remarks", "terms"]:
		value = header.get(key)
		if value in (None, "") or key in BLOCKED_HEADER:
			continue
		rows[str(key)] = value
	for key, value in header.items():
		norm = str(key).strip().lower().replace(" ", "_")
		if key in BLOCKED_HEADER or norm in _REVIEW_NOISE or value in (None, ""):
			continue
		if str(key) in rows:
			continue
		# Skip duplicate aliases already promoted onto FIELD_LABELS keys.
		if norm in {k.lower() for k in rows}:
			continue
		rows[str(key)] = value
	return rows


# Required by ERPNext, filled when the draft is saved. Not shown as scan gaps.
_SYSTEM_GAPS: frozenset[str] = frozenset(
	{
		"selling_price_list",
		"buying_price_list",
		"price_list",
		"base_net_total",
		"base_total",
		"base_grand_total",
		"base_rounded_total",
		"conversion_rate",
		"plc_conversion_rate",
		"price_list_currency",
		"party_account_currency",
	}
)

# ERPNext fills these on insert. An item row must not be blocked because
# IDP also scored it as a tax, payment, or sales-team row.
_ERP_FILLED: frozenset[str] = _SYSTEM_GAPS | frozenset(
	{
		"uom",
		"stock_uom",
		"conversion_factor",
		"stock_qty",
		"received_qty",
		"qty",
		"rate",
		"amount",
		"net_rate",
		"net_amount",
		"income_account",
		"expense_account",
		"base_rate",
		"base_amount",
		"base_net_amount",
		"base_net_total",
		"net_total",
		"grand_total",
		"total",
		"posting_time",
		"charge_type",
		"account_head",
		"item_row",
		"tax_row",
		"mode_of_payment",
		"payment_amount",
		"sales_person",
		"description",
	}
)

# The clerk can type these when the file does not carry them.
# Currency and place of supply block the draft until filled. Submit stays off unless they ask.
_WRITABLE: tuple[str, ...] = ("currency", "due_date", "cost_center", "vat_emirate")
_SALES_EMIRATE: frozenset[str] = frozenset({"Sales Invoice", "Sales Order"})
EMIRATES: tuple[str, ...] = (
	"Abu Dhabi",
	"Ajman",
	"Dubai",
	"Fujairah",
	"Ras Al Khaimah",
	"Sharjah",
	"Umm Al Quwain",
)
# AED first for UAE TaxMate; rest match masters._CURRENCY_CODES.
CURRENCIES: tuple[str, ...] = (
	"AED",
	"USD",
	"EUR",
	"GBP",
	"SAR",
	"INR",
	"QAR",
	"OMR",
	"BHD",
	"KWD",
	"CNY",
	"JPY",
	"CHF",
	"AUD",
	"CAD",
)


def gaps_from_validation(validation: dict[str, Any]) -> list[str]:
	"""Plain labels for what the clerk still has to fix. System defaults stay off the list."""
	keys: list[str] = []
	seen: set[str] = set()

	def add(key: str) -> None:
		if key not in seen:
			seen.add(key)
			keys.append(key)

	for row in (validation.get("errors") or []) + (validation.get("warnings") or []):
		field = ""
		message = ""
		if isinstance(row, dict):
			field = str(row.get("field") or "")
			message = str(row.get("message") or "")
		elif isinstance(row, str):
			message = row
		if field in _ERP_FILLED or field in _WRITABLE:
			continue
		if "line item" in message.lower():
			add("idp.gap.items")
			continue
		if field and "required field" in message.lower() and field in FIELD_LABELS:
			add(label_key_for(field))
	return keys


def writes_from_extract(
	header: dict[str, Any],
	validation: dict[str, Any],
	doctype: str | None = None,
) -> list[dict[str, Any]]:
	"""Fields the file left empty. The clerk can type them before save or submit."""
	missing = {
		str(row.get("field") or "") for row in (validation.get("errors") or []) if isinstance(row, dict)
	}
	rows: list[dict[str, Any]] = []
	for field in _WRITABLE:
		if field == "vat_emirate" and doctype not in _SALES_EMIRATE:
			continue
		if header.get(field) and field not in missing:
			continue
		raw = header.get(field)
		row: dict[str, Any] = {
			"field": field,
			"label_key": label_key_for(field),
			"value": "" if raw in (None, "") else str(raw).strip().upper() if field == "currency" else str(raw),
		}
		if field == "vat_emirate":
			row["options"] = list(EMIRATES)
		elif field == "currency":
			row["options"] = list(CURRENCIES)
		rows.append(row)
	return rows


def _unexplained(validation: dict[str, Any]) -> bool:
	"""True when a schema error is neither a labeled gap nor a field the clerk can type."""
	for row in validation.get("errors") or []:
		field = ""
		message = ""
		if isinstance(row, dict):
			field = str(row.get("field") or "")
			message = str(row.get("message") or "")
		elif isinstance(row, str):
			message = row
		if field in _ERP_FILLED or field in _WRITABLE:
			continue
		if "line item" in message.lower():
			continue
		if field and "required field" in message.lower() and field in FIELD_LABELS:
			continue
		return True
	return False


def apply_writes(
	header: dict[str, Any],
	items: list[Any],
	fills: dict[str, Any] | None,
	default_cost_center: str = "",
) -> tuple[dict[str, Any], list[Any]]:
	"""Copy only the fields the clerk typed. A number is not a tax template."""
	import re

	out = dict(header)
	clean_items = [dict(row) if isinstance(row, dict) else row for row in items]
	for field in _WRITABLE:
		text = str((fills or {}).get(field) or "").strip()
		if text:
			out[field] = text.strip().upper()[:3] if field == "currency" else text[:140]
	tax = str(out.get("taxes_and_charges") or "").strip()
	if tax and re.fullmatch(r"[\d,.]+", tax):
		out.pop("taxes_and_charges", None)
	cost = str(out.get("cost_center") or default_cost_center or "").strip()
	if cost:
		out["cost_center"] = cost
		for row in clean_items:
			if isinstance(row, dict) and not row.get("cost_center"):
				row["cost_center"] = cost
	return out, clean_items


def finish_draft(
	header: dict[str, Any],
	items: list[Any],
	fills: dict[str, Any] | None,
	defaults: dict[str, Any],
) -> tuple[dict[str, Any], list[Any]]:
	"""Apply what the clerk typed, then the company defaults ERPNext expects."""
	out, rows = apply_writes(
		header,
		items,
		fills,
		default_cost_center=str(defaults.get("cost_center") or ""),
	)
	typed = str(out.get("vat_emirate") or "").strip()
	fallback = str(defaults.get("vat_emirate") or "").strip()
	emirate = typed if typed in EMIRATES else fallback
	if emirate in EMIRATES:
		out["vat_emirate"] = emirate
	else:
		out.pop("vat_emirate", None)
	if not out.get("company") and defaults.get("company"):
		out["company"] = str(defaults["company"])
	if not out.get("currency"):
		fallback_currency = str(defaults.get("currency") or "").strip().upper()
		if fallback_currency in CURRENCIES:
			out["currency"] = fallback_currency
	if not out.get("selling_price_list") and defaults.get("selling_price_list"):
		out["selling_price_list"] = str(defaults["selling_price_list"])
	income = str(defaults.get("income_account") or "")
	uoms = defaults.get("item_uom") or {}
	for row in rows:
		if not isinstance(row, dict):
			continue
		code = str(row.get("item_code") or "")
		if not row.get("uom") and uoms.get(code):
			row["uom"] = uoms[code]
		if income and not row.get("income_account"):
			row["income_account"] = income
	expense = str(defaults.get("expense_account") or "")
	for row in rows:
		if isinstance(row, dict) and expense and not row.get("expense_account"):
			row["expense_account"] = expense
	if not out.get("buying_price_list") and defaults.get("buying_price_list"):
		out["buying_price_list"] = str(defaults["buying_price_list"])
	return out, rows


def attach_item_codes(items: list[Any], lookup: Callable[[str], str | None]) -> None:
	"""Fill an item code from an existing item when the file only named it."""
	for row in items:
		if not isinstance(row, dict) or row.get("item_code"):
			continue
		name = str(row.get("item_name") or row.get("description") or "").strip()
		if not name:
			continue
		code = lookup(name)
		if code:
			row["item_code"] = code


def submit_requested(flag: str | None) -> bool:
	"""Submit only when the clerk asks. Anything else stays a draft."""
	return str(flag or "").strip().lower() in {"1", "true", "yes"}


def review_from_extract(extracted: dict[str, Any], *, route: str | None) -> dict[str, Any]:
	"""Turn an IDP extract payload into the panel review. Draft save stays off until the map is valid."""
	from taxmate.idp.masters import (
		build_proposals,
		release_address_links,
		release_currency_company,
		scope_extract_to_company,
		split_missing,
	)

	if not extracted.get("success"):
		# Hint is a separate key so the SPA shows one clear line (not a duplicate).
		# Callers: idp_desk.run → review_from_extract. User: foolproof Scan errors.
		return {
			"ok": False,
			"step": "review",
			"error_key": "idp.readFailed",
			"detail_key": "idp.readHint",
			"can_save": False,
		}
	release_currency_company(extracted)
	release_address_links(extracted)
	scope_extract_to_company(extracted)
	data = extracted.get("extracted_data") or {}
	header = _header_rows(data.get("header") or {})
	lines = [{"label_key": label_key_for(key), "value": str(value)} for key, value in header.items()]
	items = []
	for row in data.get("items") or []:
		if not isinstance(row, dict):
			continue
		code = str(row.get("item_code") or "").strip()
		name = str(row.get("item_name") or row.get("description") or "").strip()
		if code and name and code.lower() != name.lower():
			label = f"{code} — {name}"
		else:
			label = name or code
		if label:
			items.append({"label": label})
	validation = extracted.get("validation") or {}
	missing = validation.get("missing_masters") or []
	_creatable, blocked = split_missing(missing)
	proposals = build_proposals(extracted) if not blocked else []
	raw_header = data.get("header") or {}
	# Gaps and typed fields stay available when the only missing Links are creatable.
	gaps = gaps_from_validation(validation) if not blocked else []
	writes = writes_from_extract(raw_header, validation, doctype=data.get("doctype")) if not blocked else []
	has_blockers = bool(blocked)
	can_save = not has_blockers and bool(header) and not gaps and not _unexplained(validation)
	error_key = None
	detail = None
	if has_blockers:
		error_key = "idp.notice.masters"
		can_save = False
		# Name the record. A generic sentence does not tell the clerk what stopped the draft.
		named = []
		for row in blocked:
			kind = str(row.get("doctype") or "").strip()
			name = str(row.get("name") or "").strip()
			if kind and name:
				named.append(f"{kind}: {name}")
			elif kind or name:
				named.append(kind or name)
		detail = "; ".join(named) or None
	elif proposals:
		error_key = "idp.notice.propose"
	elif not can_save:
		error_key = None if gaps else "idp.invalid"
	stage_log = [{"key": row["key"], "label_key": row["label_key"], "status": "done"} for row in READ_STAGES]
	return {
		"ok": True,
		"step": "review",
		"doctype": data.get("doctype"),
		"route": route,
		"lines": lines,
		"items": items,
		"gaps": gaps,
		"writes": writes,
		"proposals": proposals,
		"field_confidence": extracted.get("field_confidence") or {},
		"stage_log": stage_log,
		"can_save": can_save,
		"can_submit": can_save and not proposals,
		"error_key": error_key,
		"detail": detail,
	}


def draft_instructions(
	extracted: dict[str, Any], *, proposals: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
	"""The insert payload. Submit is never set. Unconfirmed proposals block the draft."""
	from taxmate.idp.masters import proposals_complete, split_missing

	review = review_from_extract(extracted, route=None)
	pending = proposals if proposals is not None else review.get("proposals") or []
	_creatable, blocked = split_missing((extracted.get("validation") or {}).get("missing_masters"))
	if blocked:
		named = []
		for row in blocked:
			kind = str(row.get("doctype") or "").strip()
			name = str(row.get("name") or "").strip()
			named.append(f"{kind}: {name}" if kind and name else (kind or name))
		return {
			"ok": False,
			"error_key": "idp.notice.masters",
			"detail": "; ".join(n for n in named if n) or None,
		}
	confirmed = bool(pending) and proposals_complete(pending)
	if pending and not confirmed:
		return {"ok": False, "error_key": "idp.propose.needConsent"}
	# Confirmed create cards already stamped Links. Schema noise (base_rate,
	# conversion_factor, …) must not soft-block with a vague idp.invalid.
	if not review.get("can_save") and not confirmed:
		gaps = review.get("gaps") or []
		return {
			"ok": False,
			"error_key": "idp.blocked.gaps" if gaps else (review.get("error_key") or "idp.invalid"),
			"detail": ", ".join(str(g) for g in gaps) if gaps else review.get("detail"),
		}
	data = extracted.get("extracted_data") or {}
	header = _header_rows(data.get("header") or {})
	if not header:
		return {"ok": False, "error_key": "idp.invalid", "detail": "header"}
	return {
		"ok": True,
		"doctype": data.get("doctype"),
		"header": header,
		"items": data.get("items") or [],
		"submit": False,
		"user_confirmed": True,
	}


def get_surface() -> dict[str, Any]:
	"""Live surface for the signed-in user. Does not return the API key."""
	import frappe

	def can(doctype: str, permission: str) -> bool:
		return bool(frappe.has_permission(doctype, permission))

	llm_ready = False
	if frappe.db.exists("DocType", "IDP Settings"):
		settings = frappe.get_single("IDP Settings")
		provider = (settings.get("llm_provider") or "") if hasattr(settings, "get") else ""
		if provider == "ollama":
			llm_ready = True
		else:
			try:
				llm_ready = bool(settings.get_password("llm_api_key", raise_exception=False))
			except Exception:
				llm_ready = False

	return build_surface(can=can, llm_ready=llm_ready)
