"""Daily SLA, contingency, and mandate-deadline reminders for UAE e-invoicing."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_url_to_form, getdate, nowdate
from frappe.utils.user import get_users_with_role

from taxmate.uae.constants import UAE_COUNTRY
from taxmate.uae_e_invoicing.constants import (
	EINVOICE_CLASSIFY_TODO_KEY,
	EINVOICE_MANDATE_REMINDER_WINDOW_DAYS,
)
from taxmate.uae_e_invoicing.utils.mandate import mandate_reminder_payload, mandate_status, sla_status


def send_e_invoice_reminders() -> None:
	_remind_sla_breaches()
	_remind_contingency()
	_remind_mandate_deadlines()


def _remind_sla_breaches() -> None:
	if not frappe.db.exists("DocType", "UAE E-Invoice Log"):
		return
	from taxmate.uae_e_invoicing.utils.mandate import get_sla_days

	today = nowdate()
	days = get_sla_days()
	log_filters = {
		"status": ["in", ["Queued", "Generated", "Submitted", "Rejected", "Failed"]],
	}
	if frappe.db.has_column("UAE E-Invoice Log", "sla_due"):
		log_filters["sla_due"] = ["<=", today]
	for log in frappe.get_all(
		"UAE E-Invoice Log",
		filters=log_filters,
		fields=["name", "company", "reference_name", "issued_on", "accepted_on", "sla_due"],
	):
		if sla_status(log.issued_on, log.accepted_on, today=today, sla_days=days) != "Breached":
			continue
		_raise_todo_once(
			"UAE E-Invoice Log",
			log.name,
			e_invoice_sla_reminder_text(log.reference_name, log.company, days, log.sla_due),
		)


def _remind_contingency() -> None:
	if not frappe.db.exists("DocType", "UAE E-Invoice Contingency"):
		return
	today = getdate(nowdate())
	for row in frappe.get_all(
		"UAE E-Invoice Contingency",
		filters={"status": "Open", "reported_to_fta": 0},
		fields=["name", "company", "report_due"],
	):
		if not row.report_due or getdate(row.report_due) > today:
			continue
		_raise_todo_once(
			"UAE E-Invoice Contingency",
			row.name,
			e_invoice_contingency_reminder_text(row.company, row.report_due),
		)


def _remind_mandate_deadlines() -> None:
	"""Nudge UAE companies that still need a cohort or an ASP before the MD 244 dates."""
	if not frappe.db.has_column("Company", "uae_e_invoice_enabled"):
		return
	companies = frappe.get_all(
		"Company",
		filters={"country": UAE_COUNTRY, "uae_e_invoice_enabled": 0},
		pluck="name",
	)
	for company in companies:
		try:
			status = mandate_status(company)
		except Exception:
			frappe.log_error(title=f"TaxMate mandate status failed for {company}")
			continue

		if status.get("cohort") != "Unclassified":
			_close_keyed_todos("Company", company, EINVOICE_CLASSIFY_TODO_KEY)
		payload = mandate_reminder_payload(status, EINVOICE_MANDATE_REMINDER_WINDOW_DAYS)
		if not payload:
			continue
		_raise_todo_once(
			"Company",
			company,
			_mandate_todo_message(payload),
			unique_key=payload["unique_key"],
		)


def company_einvoice_reminder_text(company: str) -> str | None:
	try:
		status = mandate_status(company)
	except Exception:
		return None
	payload = mandate_reminder_payload(status, EINVOICE_MANDATE_REMINDER_WINDOW_DAYS)
	if not payload:
		return None
	return _mandate_todo_message(payload)


def e_invoice_sla_reminder_text(reference_name, company, days, sla_due) -> str:
	return _("E-invoice {0} for {1} is past the {2}-day transmission SLA (due {3}).").format(
		reference_name, company, days, sla_due
	)


def e_invoice_contingency_reminder_text(company, report_due) -> str:
	return _("E-invoice downtime for {0} must be reported to the FTA (due {1}).").format(
		company, report_due
	)


def _mandate_todo_message(payload: dict) -> str:
	company = payload.get("company") or ""
	disclaimer = _(payload.get("disclaimer") or "")
	if payload.get("kind") == "classify":
		message = _(
			"{0} has no e-invoicing cohort yet. Enter last accounting-period "
			"financial-statement revenue (MD 244) or set a cohort override. "
			"TaxMate does not classify Large vs SME from the general ledger."
		).format(company)
		return f"{message}\n\n{disclaimer}"

	parts = []
	cohort = _(payload.get("cohort") or "")
	for reason in payload.get("reasons") or []:
		if reason == "asp_passed":
			parts.append(
				_(
					"{0}'s ASP-appointment deadline for the {1} e-invoicing cohort "
					"({2}) has passed and e-invoicing is not yet enabled."
				).format(company, cohort, payload.get("asp_appointment_deadline"))
			)
		elif reason == "asp_upcoming":
			parts.append(
				_(
					"{0} is in the {1} e-invoicing cohort — appoint an ASP before {2} ({3} day(s) left)."
				).format(
					company,
					cohort,
					payload.get("asp_appointment_deadline"),
					payload.get("days_to_asp_deadline"),
				)
			)
		elif reason == "go_live_now":
			parts.append(
				_(
					"Mandatory e-invoicing for the {0} cohort is live from {1} and "
					"e-invoicing is not yet enabled on {2}."
				).format(cohort, payload.get("go_live_date"), company)
			)
		elif reason == "go_live_upcoming":
			parts.append(
				_("Mandatory e-invoicing for the {0} cohort goes live on {1} ({2} day(s) left).").format(
					cohort, payload.get("go_live_date"), payload.get("days_to_go_live")
				)
			)
	return "{0}\n\n{1}".format(" ".join(parts), disclaimer)


def _close_keyed_todos(doctype: str, name: str, unique_key: str) -> None:
	for todo in frappe.get_all(
		"ToDo",
		filters={
			"reference_type": doctype,
			"reference_name": name,
			"status": "Open",
			"description": ["like", f"%[{unique_key}]%"],
		},
		pluck="name",
	):
		frappe.db.set_value("ToDo", todo, "status", "Closed")


def _raise_todo_once(doctype: str, name: str, description: str, unique_key: str | None = None) -> None:
	filters = {"reference_type": doctype, "reference_name": name, "status": "Open"}
	if unique_key:
		description = f"{description}\n[{unique_key}]"
		filters["description"] = ["like", f"%[{unique_key}]%"]
	if frappe.db.exists("ToDo", filters):
		return
	recipients = get_users_with_role("Accounts Manager") or get_users_with_role("System Manager")
	if not recipients:
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"reference_type": doctype,
			"reference_name": name,
			"allocated_to": recipients[0],
			"description": f"{description}\n\n{get_url_to_form(doctype, name)}",
			"priority": "High",
		}
	).insert(ignore_permissions=True)
