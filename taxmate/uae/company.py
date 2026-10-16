"""Company document event handlers for UAE tenants."""

from __future__ import annotations

import frappe

from taxmate.uae.constants import UAE_COUNTRY
from taxmate.uae.setup import ensure_company_uae_ready
from taxmate.uae.validation import validate_company_trn
from taxmate.setup.company_owner import validate_company_owner


def after_insert(doc, method=None):
	"""Kept for hook compatibility; readiness runs on on_update (also fires after insert)."""
	return


def on_update(doc, method=None):
	_handle_company(doc)


def validate(doc, method=None):
	validate_company_trn(doc, method)
	validate_company_owner(doc)


def _handle_company(doc):
	if doc.country != UAE_COUNTRY:
		return
	try:
		ensure_company_uae_ready(doc.name)
	except Exception:
		frappe.log_error(
			title="TaxMate UAE company readiness failed",
			message=frappe.get_traceback(),
		)
