"""Daily scheduled jobs for the UAE Compliance module.

Keeps computed statuses fresh (they're only recomputed in ``validate()``,
so a record nobody has opened since creation would otherwise show a stale
status forever) and raises a ToDo -- Frappe's own reminder primitive,
reused rather than building a bespoke notification engine -- for anything
approaching or past a deadline. One open ToDo per record is kept; existing
open ToDos are left alone so this doesn't spam a new reminder every day.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_url_to_form
from frappe.utils.user import get_users_with_role

# UAE ESR Filing is submittable: once Submitted (docstatus 1) it is locked
# in as the audit record on purpose (see uae_esr_filing.py::before_submit),
# so only Draft filings need their date-driven status refreshed daily.
# UAE UBO Register is not submittable and always has docstatus 0.
_REFRESH_TARGETS = (
	("UAE UBO Register", {}),
	("UAE ESR Filing", {"docstatus": 0}),
)


def refresh_all_statuses() -> None:
	"""Re-run validate()/save() on every open compliance record so date-driven
	statuses (Overdue, ... Due) reflect today's date, not just the date the
	record was last edited by a person."""
	for doctype, filters in _REFRESH_TARGETS:
		for name in frappe.get_all(doctype, filters=filters, pluck="name"):
			try:
				doc = frappe.get_doc(doctype, name)
				doc.save(ignore_permissions=True)
			except Exception:
				frappe.log_error(
					title=f"TaxMate UAE Compliance status refresh failed for {doctype} {name}",
					message=frappe.get_traceback(),
				)
	frappe.db.commit()


def send_deadline_reminders() -> None:
	settings = frappe.get_single("UAE Compliance Settings")
	if settings.enable_ubo_reminders:
		_remind_ubo_changes()
	if settings.enable_esr_reminders:
		_remind_esr_filings()


def _remind_ubo_changes() -> None:
	registers = frappe.get_all(
		"UAE UBO Register",
		filters={"status": ["in", ["Update Reporting Due", "Overdue"]]},
		fields=["name", "company", "status"],
	)
	for register in registers:
		_raise_todo_once(
			reference_doctype="UAE UBO Register",
			reference_name=register.name,
			description=ubo_reminder_text(register.status, register.company),
		)


def _remind_esr_filings() -> None:
	filings = frappe.get_all(
		"UAE ESR Filing",
		filters={"status": ["in", ["Notification Due", "Report Due", "Overdue"]]},
		fields=["name", "company", "status", "financial_year_end"],
	)
	for filing in filings:
		_raise_todo_once(
			reference_doctype="UAE ESR Filing",
			reference_name=filing.name,
			description=esr_reminder_text(filing.company, filing.financial_year_end, filing.status),
		)


def ubo_reminder_text(status, company) -> str:
	return _(
		"UBO change reporting is {0} for {1}. Review the Change Log and report to your "
		"licensing authority."
	).format(_(status), company)


def esr_reminder_text(company, financial_year_end, status) -> str:
	return _("ESR filing for {0} (financial year ending {1}) is {2}.").format(
		company, financial_year_end, _(status)
	)


def _raise_todo_once(reference_doctype: str, reference_name: str, description: str) -> None:
	existing = frappe.db.exists(
		"ToDo",
		{
			"reference_type": reference_doctype,
			"reference_name": reference_name,
			"status": "Open",
		},
	)
	if existing:
		return

	recipients = get_users_with_role("Accounts Manager") or get_users_with_role("System Manager")
	if not recipients:
		return

	todo = frappe.get_doc(
		{
			"doctype": "ToDo",
			"reference_type": reference_doctype,
			"reference_name": reference_name,
			"allocated_to": recipients[0],
			"description": f"{description}\n\n{get_url_to_form(reference_doctype, reference_name)}",
			"priority": "High",
		}
	)
	todo.insert(ignore_permissions=True)

	if len(recipients) > 1:
		frappe.sendmail(
			recipients=recipients,
			subject=_("[TaxMate] {0}: {1}").format(reference_doctype, reference_name),
			message=description,
		)
