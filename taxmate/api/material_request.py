"""Material Request mappers for the TaxMate SPA."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from taxmate.api.resource import assert_allowed_doctype, require_login


@frappe.whitelist()
def make_purchase_order(source_name: str, supplier: str | None = None) -> dict[str, Any]:
	"""Return an unsaved Purchase Order mapped from the given Material Request.

	Supplier is optional. Desk leaves it blank when items share no default supplier.
	The purchase order form asks for it before save. Item rows keep the
	material request link.
	"""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Purchase Order")
	if not frappe.has_permission("Material Request", "read", source_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from frappe.utils import cint, flt

	request = frappe.get_doc("Material Request", source_name)
	if (
		cint(request.docstatus) != 1
		or request.material_request_type != "Purchase"
		or request.status == "Stopped"
		or flt(request.per_ordered) >= 100
	):
		frappe.throw(_("Material Request {0} is {1}.").format(source_name, _(request.status or "")))
	from erpnext.stock.doctype.material_request.material_request import make_purchase_order as _make

	args = {"supplier": supplier} if supplier else None
	doc = _make(source_name, args=args)
	return doc.as_dict()


@frappe.whitelist()
def get_item_default_suppliers(source_name: str) -> list[dict[str, Any]]:
	"""Pending material-request rows and each item's default supplier."""
	require_login()
	assert_allowed_doctype("Material Request")
	if not frappe.has_permission("Material Request", "read", source_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import (
		get_item_default_suppliers as _get,
	)

	return _get(source_name)


@frappe.whitelist()
def make_purchase_orders_by_supplier(source_name: str, item_suppliers=None) -> list[str]:
	"""Insert one draft Purchase Order per supplier. Returns the new names."""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Purchase Order")
	if not frappe.has_permission("Material Request", "read", source_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from frappe.utils import cint, flt

	request = frappe.get_doc("Material Request", source_name)
	if (
		cint(request.docstatus) != 1
		or request.material_request_type != "Purchase"
		or request.status == "Stopped"
		or flt(request.per_ordered) >= 100
	):
		frappe.throw(_("Material Request {0} is {1}.").format(source_name, _(request.status or "")))
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import (
		make_purchase_orders_by_supplier as _make,
	)

	return _make(source_name, item_suppliers)


@frappe.whitelist()
def make_stock_entry(source_name: str) -> dict[str, Any]:
	"""Return an unsaved Stock Entry mapped from the given Material Request."""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Stock Entry")
	if not frappe.has_permission("Material Request", "read", source_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import make_stock_entry as _make

	doc = _make(source_name)
	return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def make_supplier_quotation(source_name: str) -> dict[str, Any]:
	"""Map a submitted purchase Material Request to an unsaved Supplier Quotation."""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Supplier Quotation")
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Material Request")))
	source_name = source_name.strip()
	request = frappe.get_doc("Material Request", source_name)
	request.check_permission("read")
	from frappe.utils import cint, flt

	if (
		cint(request.docstatus) != 1
		or request.material_request_type != "Purchase"
		or request.status == "Stopped"
		or flt(request.per_ordered) >= 100
	):
		frappe.throw(_("Material Request {0} is {1}.").format(source_name, _(request.status or "")))
	if not frappe.has_permission("Supplier Quotation", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Supplier Quotation")), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import (
		make_supplier_quotation as erp_make,
	)

	return erp_make(source_name).as_dict()


@frappe.whitelist(methods=["POST"])
def make_pick_list(source_name: str) -> dict[str, Any]:
	"""Map a submitted transfer request to an unsaved Pick List."""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Pick List")
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Material Request")))
	source_name = source_name.strip()
	request = frappe.get_doc("Material Request", source_name)
	request.check_permission("read")
	from frappe.utils import cint, flt

	pending = any(
		flt(row.stock_qty) > flt(row.picked_qty) for row in (request.items or [])
	)
	if (
		cint(request.docstatus) != 1
		or request.material_request_type != "Material Transfer"
		or request.status == "Stopped"
		or flt(request.per_ordered) >= 100
		or not pending
	):
		frappe.throw(_("Material Request {0} is {1}.").format(source_name, _(request.status or "")))
	if not frappe.has_permission("Pick List", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Pick List")), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import (
		create_pick_list as erp_make,
	)

	return erp_make(source_name).as_dict()


@frappe.whitelist(methods=["POST"])
def raise_work_orders(source_name: str) -> dict:
	"""Create work orders for a submitted manufacture request, as Desk does."""
	require_login()
	assert_allowed_doctype("Material Request")
	assert_allowed_doctype("Work Order")
	if not isinstance(source_name, str) or not source_name.strip():
		frappe.throw(_("{0} is required").format(_("Material Request")))
	source_name = source_name.strip()
	request = frappe.get_doc("Material Request", source_name)
	request.check_permission("read")
	from frappe.utils import cint, flt

	if (
		cint(request.docstatus) != 1
		or request.material_request_type != "Manufacture"
		or request.status == "Stopped"
		or flt(request.per_ordered) >= 100
	):
		frappe.throw(_("Material Request {0} is {1}.").format(source_name, _(request.status or "")))
	if not frappe.has_permission("Work Order", "create"):
		frappe.throw(_("Not permitted to create {0}").format(_("Work Order")), frappe.PermissionError)
	from erpnext.stock.doctype.material_request.material_request import (
		raise_work_orders as erp_raise,
	)

	names = erp_raise(source_name, request.company)
	return {"names": names or []}


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str) -> dict[str, str]:
	"""Stop a submitted Material Request. Desk only offers Stopped."""
	require_login()
	assert_allowed_doctype("Material Request")
	if not isinstance(name, str) or not name.strip():
		frappe.throw(_("{0} is required").format(_("Material Request")))
	if status != "Stopped":
		frappe.throw(_("That status is not used on a Material Request."))
	name = name.strip()
	request = frappe.get_doc("Material Request", name)
	request.check_permission("write")
	from frappe.utils import cint, flt

	if cint(request.docstatus) != 1 or request.status == "Stopped" or flt(request.per_received) >= 100:
		frappe.throw(_("Material Request {0} is {1}.").format(name, _(request.status or "")))
	from erpnext.stock.doctype.material_request.material_request import (
		update_status as erp_update,
	)

	erp_update(name, status)
	return {"name": name, "status": frappe.db.get_value("Material Request", name, "status")}
