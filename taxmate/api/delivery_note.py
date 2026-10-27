"""Delivery Note mappers for the TaxMate SPA.

ERPNext's DN → Sales Invoice mapper accepts ``target_doc`` and ``args`` off the
wire. This wrapper takes only the source name, checks permissions, and returns
an unsaved document for ``taxmate.api.resource.insert``.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from taxmate.api.resource import _as_data, assert_allowed_doctype, require_login


def _require_name(source_name: str, doctype: str) -> str:
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(doctype))
	return source_name.strip()


@frappe.whitelist(methods=["POST"])
def make_sales_invoice(source_name: str) -> dict[str, Any]:
	"""Map a submitted Delivery Note to an unsaved Sales Invoice."""
	require_login()
	name = _require_name(source_name, "Delivery Note")
	assert_allowed_doctype("Delivery Note")
	assert_allowed_doctype("Sales Invoice")

	doc = frappe.get_doc("Delivery Note", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Delivery Note before creating a Sales Invoice."))
	# Desk's button: not a return, not closed, not fully returned, not already billed,
	# and not a note that was raised from a sales invoice.
	from_invoice = any(row.get("against_sales_invoice") for row in (doc.items or []))
	if (
		cint(doc.is_return)
		or doc.status == "Closed"
		or flt(doc.per_returned) == 100
		or from_invoice
	):
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Sales Invoice")),
			title=_("Already Complete"),
		)
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Sales Invoice")), frappe.PermissionError)
	if flt(doc.get("per_billed")) >= 100:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Sales Invoice")),
			title=_("Already Complete"),
		)

	from erpnext.stock.doctype.delivery_note.delivery_note import (
		make_sales_invoice as erp_make_sales_invoice,
	)

	return _as_data(erp_make_sales_invoice(name, target_doc=None, args=None))


@frappe.whitelist(methods=["POST"])
def make_return(source_name: str) -> dict:
	"""Map a submitted Delivery Note to an unsaved Sales Return (negative DN)."""
	require_login()
	name = _require_name(source_name, "Delivery Note")
	assert_allowed_doctype("Delivery Note")

	doc = frappe.get_doc("Delivery Note", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Delivery Note before creating a return."))
	if cint(doc.get("is_return")):
		frappe.throw(_("{0} is already a return document.").format(name))
	if doc.status == "Closed":
		frappe.throw(_("Delivery Note {0} is {1}.").format(name, _("Closed")))
	if not frappe.has_permission("Delivery Note", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Delivery Note")), frappe.PermissionError)

	from erpnext.stock.doctype.delivery_note.delivery_note import (
		make_sales_return as erp_make_sales_return,
	)

	return _as_data(erp_make_sales_return(name))


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str) -> dict[str, str]:
	"""Close or re-open a Delivery Note. Desk passes Closed or Submitted."""
	require_login()
	dn_name = _require_name(name, "Delivery Note")
	assert_allowed_doctype("Delivery Note")
	if status not in ("Closed", "Submitted"):
		frappe.throw(_("That status is not used on a Delivery Note."))

	doc = frappe.get_doc("Delivery Note", dn_name)
	doc.check_permission("submit")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Delivery Note first."))
	if status == "Closed":
		if doc.status == "Closed":
			frappe.throw(_("Delivery Note {0} is {1}.").format(dn_name, _("Closed")))
	elif doc.status != "Closed":
		frappe.throw(_("Delivery Note {0} is {1}.").format(dn_name, _(doc.status)))

	from erpnext.stock.doctype.delivery_note.delivery_note import update_delivery_note_status

	update_delivery_note_status(dn_name, status)
	return {"name": dn_name, "status": frappe.db.get_value("Delivery Note", dn_name, "status")}


@frappe.whitelist(methods=["POST"])
def make_from_sales_invoice(source_name: str) -> dict[str, Any]:
	"""Map a submitted Sales Invoice to an unsaved Delivery Note, as Desk's button does."""
	require_login()
	name = _require_name(source_name, "Sales Invoice")
	assert_allowed_doctype("Sales Invoice")
	assert_allowed_doctype("Delivery Note")
	doc = frappe.get_doc("Sales Invoice", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Sales Invoice before creating a Delivery Note."))
	if cint(doc.is_return) or cint(doc.update_stock):
		frappe.throw(_("Nothing left on {0} to put on a {1}.").format(name, _("Delivery Note")))
	rows = doc.items or []
	if any(cint(row.get("is_delivered_by_supplier")) for row in rows):
		frappe.throw(_("Nothing left on {0} to put on a {1}.").format(name, _("Delivery Note")))
	pending = [
		row
		for row in rows
		if flt(row.qty) - flt(row.delivered_qty) > 0
		and not row.get("scio_detail")
		and not row.get("dn_detail")
		and not cint(row.get("delivered_by_supplier"))
	]
	if not pending:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Delivery Note")),
			title=_("Already Complete"),
		)
	if not frappe.has_permission("Delivery Note", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Delivery Note")), frappe.PermissionError)
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
		make_delivery_note as erp_make_delivery_note,
	)

	return _as_data(erp_make_delivery_note(name))
