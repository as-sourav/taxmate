"""Purchase Receipt mappers for the TaxMate SPA.

Wraps ERPNext PR → Purchase Invoice. Result is unsaved; insert then submit.
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
def make_purchase_invoice(source_name: str) -> dict[str, Any]:
	"""Map a submitted Purchase Receipt to an unsaved Purchase Invoice."""
	require_login()
	name = _require_name(source_name, "Purchase Receipt")
	assert_allowed_doctype("Purchase Receipt")
	assert_allowed_doctype("Purchase Invoice")

	doc = frappe.get_doc("Purchase Receipt", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Purchase Receipt before creating a Purchase Invoice."))
	# Desk's button on the receipt: not a return, not Closed, and not fully billed.
	# Completed and Return Issued stay selectable from the receipt itself.
	if cint(doc.is_return) or doc.status == "Closed":
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Purchase Invoice")),
			title=_("Already Complete"),
		)
	if not frappe.has_permission("Purchase Invoice", "create"):
		frappe.throw(
			_("Not permitted to create {0}").format(_("Purchase Invoice")),
			frappe.PermissionError,
		)
	if flt(doc.get("per_billed")) >= 100:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Purchase Invoice")),
			title=_("Already Complete"),
		)

	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_purchase_invoice as erp_make_purchase_invoice,
	)

	return _as_data(erp_make_purchase_invoice(name, target_doc=None, args=None))


@frappe.whitelist(methods=["POST"])
def make_return(source_name: str) -> dict:
	"""Map a submitted Purchase Receipt to an unsaved Purchase Return (negative PR)."""
	require_login()
	name = _require_name(source_name, "Purchase Receipt")
	assert_allowed_doctype("Purchase Receipt")

	doc = frappe.get_doc("Purchase Receipt", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Purchase Receipt before creating a return."))
	if cint(doc.get("is_return")):
		frappe.throw(_("{0} is already a return document.").format(name))
	if doc.status == "Closed":
		frappe.throw(_("Purchase Receipt {0} is {1}.").format(name, _("Closed")))
	if not frappe.has_permission("Purchase Receipt", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Purchase Receipt")), frappe.PermissionError)

	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_purchase_return as erp_make_purchase_return,
	)

	return _as_data(erp_make_purchase_return(name))


@frappe.whitelist(methods=["POST"])
def make_stock_entry(source_name: str) -> dict[str, Any]:
	"""Map a submitted Purchase Receipt to an unsaved Stock Entry."""
	require_login()
	name = _require_name(source_name, "Purchase Receipt")
	assert_allowed_doctype("Purchase Receipt")
	assert_allowed_doctype("Stock Entry")
	doc = frappe.get_doc("Purchase Receipt", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1 or cint(doc.is_return) or doc.status == "Closed":
		frappe.throw(_("Nothing left on {0} to put on a {1}.").format(name, _("Stock Entry")))
	if not frappe.has_permission("Stock Entry", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Stock Entry")), frappe.PermissionError)
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_stock_entry as erp_make,
	)

	return _as_data(erp_make(name))


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str) -> dict[str, str]:
	"""Close or re-open a Purchase Receipt. Desk passes Closed or Submitted."""
	require_login()
	pr_name = _require_name(name, "Purchase Receipt")
	assert_allowed_doctype("Purchase Receipt")
	if status not in ("Closed", "Submitted"):
		frappe.throw(_("That status is not used on a Purchase Receipt."))

	doc = frappe.get_doc("Purchase Receipt", pr_name)
	doc.check_permission("submit")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Purchase Receipt first."))
	if status == "Closed":
		if cint(doc.is_return) or doc.status == "Closed":
			frappe.throw(_("Purchase Receipt {0} is {1}.").format(pr_name, _(doc.status)))
	elif doc.status != "Closed":
		frappe.throw(_("Purchase Receipt {0} is {1}.").format(pr_name, _(doc.status)))

	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		update_purchase_receipt_status,
	)

	update_purchase_receipt_status(pr_name, status)
	return {"name": pr_name, "status": frappe.db.get_value("Purchase Receipt", pr_name, "status")}
