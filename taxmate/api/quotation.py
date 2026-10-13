"""Quotation→Sales Order mapper for the TaxMate SPA."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, getdate

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
	if not frappe.has_permission("Quotation", "read", source_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from erpnext.selling.doctype.quotation.quotation import make_sales_order as _make

	doc = _make(source_name)
	_stamp_delivery_date(doc, delivery_date)
	return doc.as_dict()


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
