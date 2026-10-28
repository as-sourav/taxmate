"""Lead helpers (Phase 21).

Converts a Lead to a Customer. Catalogued in taxmate.api.get_catalog().
"""

from __future__ import annotations

import frappe
from frappe import _

from taxmate.api.resource import require_login


@frappe.whitelist()
def convert_to_customer(lead_name: str) -> dict:
	"""Convert a Lead to a Customer (draft) and return the Customer doc."""
	require_login()
	if not frappe.has_permission("Lead", "write", lead_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.crm.doctype.lead.lead import _make_customer

	customer = _make_customer(lead_name, ignore_permissions=False)
	return customer.as_dict()


@frappe.whitelist(methods=["POST"])
def make_quotation(lead_name: str) -> dict:
	"""Map a Lead that is not already a customer to an unsaved Quotation."""
	require_login()
	if not isinstance(lead_name, str) or not lead_name.strip():
		frappe.throw(_("{0} is required").format(_("Lead")))
	lead_name = lead_name.strip()
	from taxmate.api.resource import assert_allowed_doctype

	assert_allowed_doctype("Lead")
	assert_allowed_doctype("Quotation")
	lead = frappe.get_doc("Lead", lead_name)
	lead.check_permission("read")
	if frappe.db.get_value("Customer", {"lead_name": lead.name}):
		frappe.throw(_("Lead {0} is already a customer.").format(lead_name))
	if not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Quotation")), frappe.PermissionError)
	from erpnext.crm.doctype.lead.lead import make_quotation as erp_make

	return erp_make(lead_name).as_dict()
