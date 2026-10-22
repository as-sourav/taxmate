"""Daily Corporate Tax filing reminders (ToDo, same pattern as VAT 201)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, get_url_to_form, getdate, nowdate
from frappe.utils.user import get_users_with_role

from taxmate.uae_corporate_tax.utils.corporate_tax import filing_deadline_status, get_ct_settings


def send_ct_reminders() -> None:
	if not frappe.db.exists("DocType", "UAE CT Filing Log"):
		return

	today = getdate(nowdate())
	for draft in frappe.get_all(
		"UAE CT Filing Log",
		filters={"docstatus": 0},
		fields=["name", "company", "filing_due_date", "period_end"],
	):
		settings = get_ct_settings(draft.company)
		lead_days = int(settings.get("reminder_days") or 30)
		status = filing_deadline_status(draft.filing_due_date, 0, today=today, lead_days=lead_days)
		frappe.db.set_value("UAE CT Filing Log", draft.name, "deadline_status", status, update_modified=False)
		if not draft.filing_due_date:
			continue
		due = getdate(draft.filing_due_date)
		if today < add_days(due, -lead_days):
			continue
		_raise_todo_once(
			draft.name,
			corporate_tax_reminder_text(
				draft.company, draft.period_end, draft.filing_due_date, today=today
			),
		)


def corporate_tax_reminder_text(company, period_end, due, today=None) -> str:
	today = getdate(today or nowdate())
	due_date = getdate(due)
	state = _("Overdue") if today > due_date else _("Due")
	return _(
		"Corporate Tax for {0} (period ending {1}) is {2}. Due {3}. "
		"Prepare the accountant pack and file on the FTA portal; submitting the log does not e-file."
	).format(company, period_end, state, due)


def _raise_todo_once(name: str, description: str) -> None:
	if frappe.db.exists(
		"ToDo",
		{"reference_type": "UAE CT Filing Log", "reference_name": name, "status": "Open"},
	):
		return
	recipients = get_users_with_role("Accounts Manager") or get_users_with_role("System Manager")
	if not recipients:
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"reference_type": "UAE CT Filing Log",
			"reference_name": name,
			"allocated_to": recipients[0],
			"description": f"{description}\n\n{get_url_to_form('UAE CT Filing Log', name)}",
			"priority": "High",
		}
	).insert(ignore_permissions=True)
	if len(recipients) > 1:
		frappe.sendmail(
			recipients=recipients,
			subject=_("[TaxMate] Corporate Tax: {0}").format(name),
			message=description,
		)
