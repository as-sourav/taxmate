"""Purchase Order mappers for the TaxMate SPA.

Wrap ERPNext PO → Purchase Receipt / Purchase Invoice mappers. The result is
unsaved; insert with taxmate.api.resource.insert, then submit.
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


def _load_submitted(source_name: str, target_doctype: str):
	"""Submitted order Desk will still create from. Held and closed orders are refused."""
	name = _require_name(source_name, "Purchase Order")
	assert_allowed_doctype("Purchase Order")
	assert_allowed_doctype(target_doctype)

	doc = frappe.get_doc("Purchase Order", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Purchase Order before creating a downstream document."))
	if doc.status in ("Closed", "On Hold"):
		frappe.throw(_("Purchase Order {0} is {1}.").format(name, _(doc.status)))
	if not frappe.has_permission(target_doctype, "create"):
		frappe.throw(
			_("Not permitted to create {0}").format(_(target_doctype)),
			frappe.PermissionError,
		)
	return doc


def _qty_left_to_receive(doc) -> bool:
	"""Desk shows Purchase Receipt when a line the supplier does not deliver is still short."""
	for row in doc.items or []:
		if cint(row.delivered_by_supplier):
			continue
		if flt(row.received_qty) < flt(row.qty):
			return True
	return False


@frappe.whitelist(methods=["POST"])
def make_purchase_receipt(source_name: str) -> dict[str, Any]:
	"""Map a submitted Purchase Order to an unsaved Purchase Receipt."""
	require_login()
	doc = _load_submitted(source_name, "Purchase Receipt")
	name = doc.name
	if not _qty_left_to_receive(doc):
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Purchase Receipt")),
			title=_("Already Complete"),
		)
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_receipt as erp_make_purchase_receipt,
	)

	return _as_data(erp_make_purchase_receipt(name, target_doc=None))


@frappe.whitelist(methods=["POST"])
def make_purchase_invoice(source_name: str) -> dict[str, Any]:
	"""Map a submitted Purchase Order to an unsaved Purchase Invoice."""
	require_login()
	doc = _load_submitted(source_name, "Purchase Invoice")
	name = doc.name
	if flt(doc.per_billed) >= 100:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Purchase Invoice")),
			title=_("Already Complete"),
		)
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_invoice as erp_make_purchase_invoice,
	)

	return _as_data(erp_make_purchase_invoice(name, target_doc=None))


# Desk passes these four values to erpnext.buying.doctype.purchase_order.purchase_order.update_status.
_STATUS = ("On Hold", "Draft", "Closed", "Submitted")


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str, reason: str | None = None) -> dict[str, str]:
	"""Hold, resume, close, or re-open a Purchase Order the way Desk does.

	``Draft`` resumes a held order. ``Submitted`` re-opens a closed or delivered
	one. ERPNext then recalculates the real status from received and billed qty.
	"""
	require_login()
	po_name = _require_name(name, "Purchase Order")
	assert_allowed_doctype("Purchase Order")
	if status not in _STATUS:
		frappe.throw(_("That status is not used on a Purchase Order."))

	doc = frappe.get_doc("Purchase Order", po_name)
	doc.check_permission("submit")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Purchase Order first."))

	still_open = flt(doc.per_received) < 100 or flt(doc.per_billed) < 100
	if status in ("On Hold", "Draft", "Closed"):
		if doc.status in ("Closed", "Delivered") or not still_open:
			frappe.throw(_("Purchase Order {0} is {1}.").format(po_name, _(doc.status)))
		if status == "On Hold":
			if doc.status == "On Hold":
				frappe.throw(_("Purchase Order {0} is {1}.").format(po_name, _("On Hold")))
			note = reason.strip() if isinstance(reason, str) else ""
			if not note:
				frappe.throw(_("Reason for Hold"))
			from frappe.desk.form.utils import add_comment

			add_comment(
				"Purchase Order",
				po_name,
				_("Reason for hold: {0}").format(note),
				frappe.session.user,
				frappe.utils.get_fullname(frappe.session.user),
			)
		elif status == "Draft" and doc.status != "On Hold":
			frappe.throw(_("Purchase Order {0} is {1}.").format(po_name, _(doc.status)))
	elif doc.status not in ("Closed", "Delivered"):
		frappe.throw(_("Purchase Order {0} is {1}.").format(po_name, _(doc.status)))

	from erpnext.buying.doctype.purchase_order.purchase_order import update_status

	update_status(status, po_name)
	return {"name": po_name, "status": frappe.db.get_value("Purchase Order", po_name, "status")}


@frappe.whitelist(methods=["POST"])
def update_dropship_received_qty(name: str, items) -> dict[str, str]:
	"""Set delivered quantity on drop-ship lines, as Desk's dialog does."""
	require_login()
	po_name = _require_name(name, "Purchase Order")
	assert_allowed_doctype("Purchase Order")
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list) or not items:
		frappe.throw(_("Please select at least one item to update delivered quantity."))
	doc = frappe.get_doc("Purchase Order", po_name)
	doc.check_permission("write")
	if cint(doc.docstatus) != 1 or doc.status in ("Closed", "Delivered", "Completed"):
		frappe.throw(_("Purchase Order {0} is {1}.").format(po_name, _(doc.status or "")))
	doc.update_dropship_received_qty(items)
	return {"name": po_name, "status": frappe.db.get_value("Purchase Order", po_name, "status")}
