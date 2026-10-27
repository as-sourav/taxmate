"""Quotation→Sales Order mapper for the TaxMate SPA."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from taxmate.api.resource import assert_allowed_doctype, require_login

# Match SalesOrderCreate's default promise window when Quotation has no date.
_DEFAULT_DELIVERY_DAYS = 21


@frappe.whitelist()
def make_sales_order(source_name: str, delivery_date: str | None = None) -> dict[str, Any]:
	"""Return an unsaved Sales Order mapped from the given Quotation.

	Sales Order requires ``delivery_date``; Quotation does not carry one.
	Stamp a date on the mapped doc (and item rows) so SPA insert / form
	prefill do not fail with a mandatory-field error on a submitted Quotation
	the operator cannot edit.
	"""
	require_login()
	assert_allowed_doctype("Quotation")
	assert_allowed_doctype("Sales Order")
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Quotation")))
	source_name = source_name.strip()
	doc = frappe.get_doc("Quotation", source_name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Quotation before creating a Sales Order."))
	if doc.status in ("Lost", "Ordered"):
		frappe.throw(_("Quotation {0} is {1}.").format(source_name, _(doc.status)))
	if not frappe.has_permission("Sales Order", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Sales Order")), frappe.PermissionError)
	from erpnext.selling.doctype.quotation.quotation import make_sales_order as _make

	doc = _make(source_name)
	_stamp_delivery_date(doc, delivery_date)
	return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def declare_lost(name: str, lost_reason: str, detailed_reason: str | None = None) -> dict[str, str]:
	"""Mark a submitted quotation Lost. Desk requires one lost reason."""
	require_login()
	assert_allowed_doctype("Quotation")
	if not isinstance(name, str) or not name.strip():
		frappe.throw(_("{0} is required").format(_("Quotation")))
	if not isinstance(lost_reason, str) or not lost_reason.strip():
		frappe.throw(_("{0} is required").format(_("Quotation Lost Reason")))
	name = name.strip()
	doc = frappe.get_doc("Quotation", name)
	doc.check_permission("write")
	if cint(doc.docstatus) != 1 or doc.status in ("Lost", "Ordered"):
		frappe.throw(_("Quotation {0} is {1}.").format(name, _(doc.status or "")))
	doc.declare_enquiry_lost([{"lost_reason": lost_reason.strip()}], [], detailed_reason)
	return {"name": name, "status": frappe.db.get_value("Quotation", name, "status")}


@frappe.whitelist()
def sales_order_allowed(name: str) -> dict[str, int]:
	"""Whether Desk would show Sales Order on this quotation.

	Uses the site date and Selling Settings, the same check ERPNext's mapper runs.
	"""
	require_login()
	assert_allowed_doctype("Quotation")
	if not isinstance(name, str) or not name.strip():
		frappe.throw(_("{0} is required").format(_("Quotation")))
	name = name.strip()
	doc = frappe.get_doc("Quotation", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1 or doc.status in ("Lost", "Ordered"):
		return {"allowed": 0}
	if not frappe.has_permission("Sales Order", "create"):
		return {"allowed": 0}
	from frappe.utils import getdate, nowdate

	if not frappe.db.get_singles_value(
		"Selling Settings", "allow_sales_order_creation_for_expired_quotation"
	):
		valid_till = getdate(doc.valid_till) if doc.valid_till else None
		if valid_till and (
			valid_till < getdate(doc.transaction_date) or valid_till < getdate(nowdate())
		):
			return {"allowed": 0}
	return {"allowed": 1}


@frappe.whitelist(methods=["POST"])
def make_from_customer(source_name: str) -> dict[str, Any]:
	"""Map a Customer to an unsaved Quotation, as Desk's Create button does."""
	require_login()
	assert_allowed_doctype("Customer")
	assert_allowed_doctype("Quotation")
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Customer")))
	source_name = source_name.strip()
	customer = frappe.get_doc("Customer", source_name)
	customer.check_permission("read")
	if not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Quotation")), frappe.PermissionError)
	from erpnext.selling.doctype.customer.customer import make_quotation

	return make_quotation(source_name).as_dict()


def _stamp_delivery_date(doc, delivery_date: str | None) -> None:
	"""Mirror ERPNext SO.validate_delivery_date: parent + item dates required.

	Desk leaves the field blank after open_mapped_doc; the SPA stamps a default
	so insert does not hit ``Please enter Delivery Date`` (sales_order.py:424).
	"""
	if doc.get("delivery_date"):
		resolved = getdate(doc.delivery_date)
	elif delivery_date:
		resolved = getdate(delivery_date)
	else:
		base = doc.get("transaction_date")
		resolved = add_days(getdate(base) if base else getdate(), _DEFAULT_DELIVERY_DAYS)
	doc.delivery_date = resolved
	for row in doc.get("items") or []:
		if not row.get("delivery_date"):
			row.delivery_date = resolved
