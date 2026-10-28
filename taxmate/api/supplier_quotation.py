"""Supplier Quotation helpers (Phase 16).

Maps a submitted Supplier Quotation to a draft Purchase Order.
Catalogued in taxmate.api.get_catalog() as make_supplier_quotation_po.
"""

from __future__ import annotations

import frappe
from frappe import _

from taxmate.api.resource import require_login


@frappe.whitelist()
def make_purchase_order(source_name: str) -> dict:
	"""Map a submitted Supplier Quotation to a draft Purchase Order."""
	require_login()
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Supplier Quotation")))
	source_name = source_name.strip()
	quote = frappe.get_doc("Supplier Quotation", source_name)
	quote.check_permission("read")
	# Desk shows Purchase Order on every submitted quotation, including Expired and Stopped.
	from frappe.utils import cint

	if cint(quote.docstatus) != 1:
		frappe.throw(_("Submit the Supplier Quotation before creating a Purchase Order."))
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Purchase Order")), frappe.PermissionError)

	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order as _make_po

	po = _make_po(source_name)
	return po.as_dict()


@frappe.whitelist(methods=["POST"])
def make_quotation(source_name: str) -> dict:
	"""Map a submitted Supplier Quotation to an unsaved sales Quotation."""
	require_login()
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Supplier Quotation")))
	source_name = source_name.strip()
	from taxmate.api.resource import assert_allowed_doctype

	assert_allowed_doctype("Supplier Quotation")
	assert_allowed_doctype("Quotation")
	quote = frappe.get_doc("Supplier Quotation", source_name)
	quote.check_permission("read")
	from frappe.utils import cint

	if cint(quote.docstatus) != 1:
		frappe.throw(_("Submit the Supplier Quotation before creating a Quotation."))
	if not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Quotation")), frappe.PermissionError)
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import (
		make_quotation as erp_make,
	)

	return erp_make(source_name).as_dict()
