"""Scheduled status poll — fallback for missed ASP webhooks."""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

# Complyance does not webhook sales documents. Poll after a short wait.
STALE_AFTER_MINUTES = 5
BATCH_SIZE = 50


def poll_submitted_e_invoices():
	"""Advance logs stuck in Submitted when their webhook was missed."""
	if not frappe.db.exists("DocType", "UAE E-Invoice Log"):
		return

	from taxmate.uae_e_invoicing.utils.e_invoice import sync_status_from_asp

	stale_before = add_to_date(now_datetime(), minutes=-STALE_AFTER_MINUTES)
	pending = frappe.get_all(
		"UAE E-Invoice Log",
		filters={
			"status": "Submitted",
			"asp_document_id": ("is", "set"),
			"submitted_on": ("<", stale_before),
		},
		pluck="name",
		order_by="submitted_on asc",
		limit=BATCH_SIZE,
	)

	for log_name in pending:
		try:
			sync_status_from_asp(log_name)
			# Commit per row so one failure does not roll back the batch
			frappe.db.commit()  # nosemgrep
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"UAE e-invoice status poll failed for {log_name}",
				message=frappe.get_traceback(),
			)
