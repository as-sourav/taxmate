"""Daily VAT 201 filing reminders (ToDo, same pattern as ESR)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, get_url_to_form, getdate, nowdate
from frappe.utils.user import get_users_with_role


def send_vat_201_reminders() -> None:
	if not frappe.db.exists("DocType", "UAE VAT 201 Filing Log"):
		return

	from taxmate.uae_vat.utils.vat_201 import filing_deadline_status, reminder_lead_days

	lead_days = reminder_lead_days()
	today = getdate(nowdate())
	for draft in frappe.get_all(
		"UAE VAT 201 Filing Log",
		filters={"docstatus": 0},
		fields=["name", "filing_due_date"],
	):
		status = filing_deadline_status(draft.filing_due_date, 0, today=today, lead_days=lead_days)
		frappe.db.set_value(
			"UAE VAT 201 Filing Log", draft.name, "deadline_status", status, update_modified=False
		)

	for log in frappe.get_all(
		"UAE VAT 201 Filing Log",
		filters={"docstatus": 0},
		fields=["name", "company", "filing_due_date", "period_end"],
	):
		if not log.filing_due_date:
			continue
		due = getdate(log.filing_due_date)
		if today < add_days(due, -lead_days):
			continue
		_raise_todo_once(
			log.name,
			vat_201_reminder_text(log.company, log.period_end, log.filing_due_date, today=today),
		)


def vat_201_reminder_text(company, period_end, due, today=None) -> str:
	"""VAT 201 reminder in the current user's language. Company names stay as stored."""
	today = getdate(today or nowdate())
	due_date = getdate(due)
	state = _("Overdue") if today > due_date else _("Due")
	return _(
		"VAT 201 for {0} (period ending {1}) is {2}. Due {3}. "
		"Prepare the accountant pack and file in EmaraTax; submitting the log does not e-file."
	).format(company, period_end, state, due)


def _raise_todo_once(name: str, description: str) -> None:
	if frappe.db.exists(
		"ToDo",
		{"reference_type": "UAE VAT 201 Filing Log", "reference_name": name, "status": "Open"},
	):
		return
	recipients = get_users_with_role("Accounts Manager") or get_users_with_role("System Manager")
	if not recipients:
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"reference_type": "UAE VAT 201 Filing Log",
			"reference_name": name,
			"allocated_to": recipients[0],
			"description": f"{description}\n\n{get_url_to_form('UAE VAT 201 Filing Log', name)}",
			"priority": "High",
		}
	).insert(ignore_permissions=True)
	if len(recipients) > 1:
		frappe.sendmail(
			recipients=recipients,
			subject=_("[TaxMate] VAT 201: {0}").format(name),
			message=description,
		)
