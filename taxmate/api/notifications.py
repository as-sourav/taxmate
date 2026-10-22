"""Inbox for the signed-in user: unread Notification Logs and open ToDos."""

from __future__ import annotations

import re
from typing import Any
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_datetime, get_system_timezone, strip_html

from taxmate.api.resource import require_login
from taxmate.api.spa_routes import doc_route
from taxmate.utils.company import get_default_company, owning_company_field

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_SPACE = re.compile(r"\s+")
_PAGE = 20


def _title(raw: str | None) -> str:
	text = _SPACE.sub(" ", _URL.sub("", strip_html(cstr(raw)))).strip()
	if len(text) > 180:
		return text[:179] + "…"
	return text


def _created(value: Any) -> str:
	dt = get_datetime(value)
	if not dt:
		return ""
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=ZoneInfo(get_system_timezone() or "UTC"))
	return dt.isoformat(timespec="seconds")


def _pair(doctype: str | None, name: str | None) -> tuple[str | None, str | None]:
	doctype = cstr(doctype).strip() or None
	name = cstr(name).strip() or None
	if not doctype or not name:
		return None, None
	return doctype, name


def _visible(doctype: str, names: list[str]) -> set[str]:
	if not names or not frappe.db.exists("DocType", doctype):
		return set()
	unique = list(dict.fromkeys(names))
	filters: dict[str, Any] = {"name": ["in", unique]}
	company = get_default_company()
	field = owning_company_field(doctype)
	if company and field and field[1]:
		filters[field[0]] = company
	try:
		found = frappe.get_list(doctype, filters=filters, pluck="name", limit=len(unique))
	except frappe.PermissionError:
		return set()
	return set(found)


def _keep(rows: list[dict], type_key: str, name_key: str) -> list[dict]:
	grouped: dict[str, list[str]] = {}
	for row in rows:
		doctype, name = _pair(row.get(type_key), row.get(name_key))
		if doctype and name:
			grouped.setdefault(doctype, []).append(name)
	allowed = {doctype: _visible(doctype, names) for doctype, names in grouped.items()}
	kept: list[dict] = []
	for row in rows:
		doctype, name = _pair(row.get(type_key), row.get(name_key))
		if doctype and name and name not in allowed.get(doctype, set()):
			continue
		kept.append(row)
	return kept


def _logs() -> list[dict]:
	return frappe.get_all(
		"Notification Log",
		filters={"for_user": frappe.session.user, "read": 0},
		fields=["name", "subject", "creation", "document_type", "document_name"],
		order_by="creation desc",
		limit=0,
	)


def _todos() -> list[dict]:
	return frappe.get_all(
		"ToDo",
		filters={"allocated_to": frappe.session.user, "status": "Open"},
		fields=["name", "description", "creation", "reference_type", "reference_name"],
		order_by="creation desc",
		limit=0,
	)


def _log_item(row: dict) -> dict:
	doctype, name = _pair(row.get("document_type"), row.get("document_name"))
	return {
		"id": f"log:{row.name}",
		"kind": "log",
		"name": row.name,
		"title": _title(row.get("subject")),
		"created": _created(row.creation),
		"document_type": doctype,
		"document_name": name,
		"route": doc_route(doctype, name),
		"can_mark_read": True,
	}


def _wants_arabic() -> bool:
	lang = cstr(getattr(frappe.local, "lang", "") or "").lower()
	return lang == "ar" or lang.startswith("ar_")


def _localized_todo(doctype: str | None, name: str | None) -> str | None:
	"""Rebuild a compliance reminder in Arabic. English keeps the stored text."""
	if not doctype or not name or not _wants_arabic():
		return None
	try:
		return _reminder_text(doctype, name)
	except Exception:
		return None


def _reminder_text(doctype: str, name: str) -> str | None:
	if doctype == "UAE VAT 201 Filing Log":
		row = frappe.db.get_value(
			doctype, name, ["company", "period_end", "filing_due_date"], as_dict=True
		)
		if not row or not row.filing_due_date:
			return None
		from taxmate.uae_vat.notifications import vat_201_reminder_text

		return vat_201_reminder_text(row.company, row.period_end, row.filing_due_date)
	if doctype == "UAE CT Filing Log":
		row = frappe.db.get_value(
			doctype, name, ["company", "period_end", "filing_due_date"], as_dict=True
		)
		if not row or not row.filing_due_date:
			return None
		from taxmate.uae_corporate_tax.notifications import corporate_tax_reminder_text

		return corporate_tax_reminder_text(row.company, row.period_end, row.filing_due_date)
	if doctype == "UAE ESR Filing":
		row = frappe.db.get_value(
			doctype, name, ["company", "financial_year_end", "status"], as_dict=True
		)
		if not row:
			return None
		from taxmate.uae_compliance.notifications import esr_reminder_text

		return esr_reminder_text(row.company, row.financial_year_end, row.status)
	if doctype == "UAE UBO Register":
		row = frappe.db.get_value(doctype, name, ["company", "status"], as_dict=True)
		if not row:
			return None
		from taxmate.uae_compliance.notifications import ubo_reminder_text

		return ubo_reminder_text(row.status, row.company)
	if doctype == "Company":
		from taxmate.uae_e_invoicing.notifications import company_einvoice_reminder_text

		return company_einvoice_reminder_text(name)
	if doctype == "UAE E-Invoice Log":
		row = frappe.db.get_value(
			doctype, name, ["reference_name", "company", "sla_due"], as_dict=True
		)
		if not row:
			return None
		from taxmate.uae_e_invoicing.notifications import e_invoice_sla_reminder_text
		from taxmate.uae_e_invoicing.utils.mandate import get_sla_days

		return e_invoice_sla_reminder_text(row.reference_name, row.company, get_sla_days(), row.sla_due)
	if doctype == "UAE E-Invoice Contingency":
		row = frappe.db.get_value(doctype, name, ["company", "report_due"], as_dict=True)
		if not row:
			return None
		from taxmate.uae_e_invoicing.notifications import e_invoice_contingency_reminder_text

		return e_invoice_contingency_reminder_text(row.company, row.report_due)
	return None


def _todo_item(row: dict) -> dict:
	doctype, name = _pair(row.get("reference_type"), row.get("reference_name"))
	return {
		"id": f"todo:{row.name}",
		"kind": "todo",
		"name": row.name,
		"title": _title(_localized_todo(doctype, name) or row.get("description")),
		"created": _created(row.creation),
		"document_type": doctype,
		"document_name": name,
		"route": doc_route(doctype, name),
		"can_mark_read": False,
	}


def _items() -> list[dict]:
	rows = [_log_item(row) for row in _keep(_logs(), "document_type", "document_name")]
	rows.extend(_todo_item(row) for row in _keep(_todos(), "reference_type", "reference_name"))
	rows.sort(key=lambda row: row["created"], reverse=True)
	return rows


def _own_log(name: str) -> dict:
	row = frappe.db.get_value(
		"Notification Log",
		cstr(name).strip(),
		["name", "for_user", "read", "document_type", "document_name"],
		as_dict=True,
	)
	if not row or row.for_user != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	doctype, docname = _pair(row.document_type, row.document_name)
	if doctype and docname and docname not in _visible(doctype, [docname]):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return row


@frappe.whitelist()
def list_inbox() -> dict[str, Any]:
	require_login()
	rows = _items()
	return {"unread": len(rows), "has_more": len(rows) > _PAGE, "items": rows[:_PAGE]}


@frappe.whitelist()
def mark_read(name: str) -> dict[str, Any]:
	require_login()
	row = _own_log(name)
	if not cint(row.read):
		frappe.db.set_value("Notification Log", row.name, "read", 1, update_modified=False)
	return {"name": row.name, "read": 1}


@frappe.whitelist()
def mark_all_read() -> dict[str, int]:
	require_login()
	names = [row.name for row in _keep(_logs(), "document_type", "document_name")]
	if names:
		frappe.db.set_value("Notification Log", {"name": ["in", names]}, "read", 1, update_modified=False)
	return {"marked": len(names)}
