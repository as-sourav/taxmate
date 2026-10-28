"""Sales Order KPIs and document mappers for the TaxMate SPA."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from taxmate.api.resource import (
	_as_data,
	assert_allowed_doctype,
	assert_company_read,
	require_login,
)
from taxmate.utils.company import get_default_company

# Open = promised and not fully billed (excludes Draft / Completed / Cancelled / Closed).
_OPEN_STATUSES = (
	"To Deliver and Bill",
	"To Bill",
	"To Deliver",
	"To Pay",
	"On Hold",
)


@frappe.whitelist()
def fulfilment_summary(company: str | None = None) -> dict[str, Any]:
	"""Committed / delivered / billed value plus open and overdue counts.

	Used by the Sales Order list tiles and fulfilment bars.

	Two things this deliberately does:

	* Reads through ``frappe.get_list``, not ``get_all``. ``get_all`` sets
	  ``ignore_permissions=True``, so every user would see company-wide totals
	  regardless of their User Permissions. ``get_list`` applies them.
	* Sums ``base_grand_total`` (company currency), not ``grand_total``
	  (document currency). The two differ the moment anything is priced in a
	  currency other than the company's, and a sum across mixed currencies is
	  meaningless. The response carries the currency it is denominated in.

	Only open orders contribute to the value totals. A Completed or Closed
	order is no longer a commitment, so including it would permanently inflate
	``committed`` and flatten the delivered / billed bars against it.
	"""
	require_login()
	if not frappe.has_permission("Sales Order", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	company = company or get_default_company()
	assert_company_read(company)

	filters: dict[str, Any] = {"docstatus": 1, "status": ["in", _OPEN_STATUSES]}
	if company:
		filters["company"] = company

	rows = frappe.get_list(
		"Sales Order",
		filters=filters,
		fields=[
			"name",
			"status",
			"docstatus",
			"base_grand_total",
			"per_delivered",
			"per_billed",
			"delivery_date",
			"transaction_date",
		],
		limit_page_length=0,
	)

	committed = 0.0
	delivered_value = 0.0
	billed_value = 0.0
	open_count = 0
	overdue_count = 0
	today_date = getdate(today())

	for row in rows:
		total = flt(row.base_grand_total)
		per_d = flt(row.per_delivered)
		per_b = flt(row.per_billed)

		committed += total
		delivered_value += total * per_d / 100.0
		billed_value += total * per_b / 100.0

		open_count += 1
		if row.delivery_date and getdate(row.delivery_date) < today_date and per_d < 100:
			overdue_count += 1

	return {
		"company": company,
		"currency": _company_currency(company),
		"committed": committed,
		"delivered_value": delivered_value,
		"billed_value": billed_value,
		"unbilled_delivered": max(delivered_value - billed_value, 0.0),
		"open_count": cint(open_count),
		"overdue_count": cint(overdue_count),
	}


@frappe.whitelist()
def linked_documents(sales_order: str) -> dict[str, list[str]]:
	"""Delivery Notes and Sales Invoices raised against one Sales Order.

	The link lives on the child rows, but a child doctype cannot be listed
	directly: frappe's has_child_permission refuses a child table with no
	parent_doctype (frappe/permissions.py:837), so the SPA's old approach
	silently returned 403 and rendered an empty panel. Filtering the PARENT
	doctype by a child field is the supported shape and applies the parent's
	own permissions.
	"""
	require_login()
	name = _require_name(sales_order, "Sales Order")
	assert_allowed_doctype("Sales Order")
	doc = frappe.get_doc("Sales Order", name)
	doc.check_permission("read")

	return {
		"delivery_notes": _parents("Delivery Note", "Delivery Note Item", "against_sales_order", name),
		"sales_invoices": _parents("Sales Invoice", "Sales Invoice Item", "sales_order", name),
	}


def _parents(parent_doctype: str, child_doctype: str, fieldname: str, value: str) -> list[str]:
	if not frappe.has_permission(parent_doctype, "read"):
		return []
	# Deduplicated here rather than with distinct=True: on PostgreSQL frappe
	# drops the ORDER BY when distinct is set (frappe/database/query.py:320),
	# which would return an arbitrary 50 rows instead of the newest 50.
	rows = frappe.get_list(
		parent_doctype,
		filters=[
			[child_doctype, fieldname, "=", value],
			[parent_doctype, "docstatus", "<", 2],
		],
		fields=["name"],
		order_by="creation desc",
		limit_page_length=200,
	)
	seen: dict[str, None] = {}
	for row in rows:
		seen.setdefault(row.name, None)
	return list(seen)[:50]


def _require_name(value, doctype: str) -> str:
	"""Whitelisted arguments arrive from the wire — a name must be a string.

	``from __future__ import annotations`` turns every annotation into a string,
	which switches off frappe's own argument-type validation
	(frappe/utils/typing_validations.py:130). Without this, a JSON body could
	pass a dict where a document name belongs and frappe.get_doc would treat it
	as a filter expression.
	"""
	if not isinstance(value, str) or not value.strip():
		frappe.throw(_("{0} is required").format(_(doctype)))
	return value.strip()


def _company_currency(company: str | None) -> str:
	"""Currency the totals above are denominated in."""
	if company:
		currency = frappe.get_cached_value("Company", company, "default_currency")
		if currency:
			return currency
	return frappe.db.get_default("currency")


# ── Document mappers ─────────────────────────────────────────────────────
#
# ERPNext's own mappers are whitelisted, but their signatures accept
# ``target_doc`` and (for the invoice) ``ignore_permissions`` straight off the
# wire. Calling them from the browser hands the client those parameters. These
# wrappers take only the source name, check read permission on the real
# document, and fix the sensitive arguments server-side.
#
# Both return an UNSAVED document — the caller inserts it.


@frappe.whitelist(methods=["POST"])
def make_sales_invoice(source_name: str):
	"""Map a submitted Sales Order to a draft Sales Invoice."""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Sales Invoice")
	if doc.status in ("Closed", "On Hold"):
		frappe.throw(_("Sales Order {0} is {1}.").format(name, _(doc.status)))
	# A subcontracted order keeps the invoice button after it is fully billed.
	if flt(doc.per_billed) >= 100 and not cint(doc.is_subcontracted):
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Sales Invoice")),
			title=_("Already Complete"),
		)

	from erpnext.selling.doctype.sales_order.sales_order import (
		make_sales_invoice as erp_make_sales_invoice,
	)

	return _as_data(erp_make_sales_invoice(name, target_doc=None, ignore_permissions=False))


@frappe.whitelist(methods=["POST"])
def make_delivery_note(source_name: str, for_reserved_stock=1):
	"""Map a submitted Sales Order to a draft Delivery Note.

	``for_reserved_stock`` defaults to on, matching ERPNext's own Create ->
	Delivery Note button (sales_order.js:1049 passes true). With it off, the
	reserved-stock branch is skipped and the note is mapped from plain
	remaining quantity, which silently ignores Stock Reservation Entries and
	their serial / batch bundles. It is a plain flag here rather than a
	free-form kwargs dict so the wire cannot reach the rest of the mapper.
	"""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Delivery Note")
	if doc.status in ("Closed", "On Hold"):
		frappe.throw(_("Sales Order {0} is {1}.").format(name, _(doc.status)))
	if not _can_deliver(doc):
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Delivery Note")),
			title=_("Already Complete"),
		)

	from erpnext.selling.doctype.sales_order.sales_order import (
		make_delivery_note as erp_make_delivery_note,
	)

	return _as_data(
		erp_make_delivery_note(
			name,
			target_doc=None,
			kwargs={
				"for_reserved_stock": _as_bool(for_reserved_stock),
				"skip_item_mapping": False,
			},
		)
	)


def _as_bool(value) -> bool:
	"""Wire-safe flag. cint("true") is 0, and "true" is what JS sends."""
	if isinstance(value, str):
		return value.strip().lower() in ("1", "true", "yes", "on")
	return bool(cint(value))


def _load_submitted(source_name: str):
	"""Read the real Sales Order. Create permission is checked by the caller."""
	name = _require_name(source_name, "Sales Order")
	assert_allowed_doctype("Sales Order")
	doc = frappe.get_doc("Sales Order", name)
	doc.check_permission("read")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Sales Order before creating a downstream document."))
	return name, doc


def _require_create(target_doctype: str) -> None:
	assert_allowed_doctype(target_doctype)
	if not frappe.has_permission(target_doctype, "create"):
		frappe.throw(_("Not permitted to create {0}").format(_(target_doctype)), frappe.PermissionError)


def _can_deliver(doc) -> bool:
	"""Desk's Delivery Note button: not a maintenance order, not skipped, still short."""
	if doc.order_type == "Maintenance" or cint(doc.skip_delivery_note):
		return False
	if flt(doc.per_delivered) >= 100:
		return False
	if cint(doc.has_unit_price_items):
		return True
	for row in doc.items or []:
		if cint(row.delivered_by_supplier):
			continue
		if flt(row.qty) > flt(row.delivered_qty):
			return True
	return False


# Resume and Re-open both pass Draft. Hold and Close are the other two.
_STATUS = ("On Hold", "Draft", "Closed")


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str, reason: str | None = None) -> dict[str, str]:
	"""Hold, resume, close, or re-open a Sales Order the way Desk does.

	``Draft`` resumes a held order and also re-opens a closed one. ERPNext
	then recalculates the real status from delivered and billed quantity.
	"""
	require_login()
	so_name = _require_name(name, "Sales Order")
	assert_allowed_doctype("Sales Order")
	if status not in _STATUS:
		frappe.throw(_("That status is not used on a Sales Order."))

	doc = frappe.get_doc("Sales Order", so_name)
	doc.check_permission("submit")
	if cint(doc.docstatus) != 1:
		frappe.throw(_("Submit the Sales Order first."))

	still_open = flt(doc.per_delivered) < 100 or flt(doc.per_billed) < 100
	if status == "On Hold":
		if doc.status in ("Closed", "On Hold") or not still_open:
			frappe.throw(_("Sales Order {0} is {1}.").format(so_name, _(doc.status)))
		note = reason.strip() if isinstance(reason, str) else ""
		if not note:
			frappe.throw(_("Reason for Hold"))
		from frappe.desk.form.utils import add_comment

		add_comment(
			"Sales Order",
			so_name,
			_("Reason for hold: {0}").format(note),
			frappe.session.user,
			frappe.utils.get_fullname(frappe.session.user),
		)
	elif status == "Closed":
		if doc.status == "Closed" or not still_open:
			frappe.throw(_("Sales Order {0} is {1}.").format(so_name, _(doc.status)))
	elif doc.status not in ("On Hold", "Closed"):
		frappe.throw(_("Sales Order {0} is {1}.").format(so_name, _(doc.status)))

	from erpnext.selling.doctype.sales_order.sales_order import update_status

	update_status(status, so_name)
	return {"name": so_name, "status": frappe.db.get_value("Sales Order", so_name, "status")}


@frappe.whitelist(methods=["POST"])
def make_pick_list(source_name: str):
	"""Map a submitted Sales Order to an unsaved Pick List, as Desk's Create button does."""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Pick List")
	if doc.status in ("Closed", "On Hold") or cint(doc.is_subcontracted):
		frappe.throw(_("Sales Order {0} is {1}.").format(name, _(doc.status)))
	if flt(doc.per_picked) >= 100 or flt(doc.per_delivered) >= 100:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Pick List")),
			title=_("Already Complete"),
		)
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import has_reserved_stock

	if has_reserved_stock("Sales Order", name):
		frappe.throw(_("Sales Order {0} has reserved stock.").format(name))
	from erpnext.selling.doctype.sales_order.sales_order import create_pick_list

	return _as_data(create_pick_list(name))


@frappe.whitelist(methods=["POST"])
def make_material_request(source_name: str):
	"""Map a submitted Sales Order to an unsaved Material Request."""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Material Request")
	if doc.status in ("Closed", "On Hold") or cint(doc.is_subcontracted):
		frappe.throw(_("Sales Order {0} is {1}.").format(name, _(doc.status)))
	if doc.order_type == "Maintenance":
		frappe.throw(_("Sales Order {0} is {1}.").format(name, _(doc.order_type)))
	if doc.order_type and flt(doc.per_delivered) >= 100:
		frappe.throw(
			_("Nothing left on {0} to put on a {1}.").format(name, _("Material Request")),
			title=_("Already Complete"),
		)
	from erpnext.selling.doctype.sales_order.sales_order import (
		make_material_request as erp_make_material_request,
	)

	return _as_data(erp_make_material_request(name))


@frappe.whitelist(methods=["POST"])
def get_work_order_items(source_name: str) -> dict:
	"""Rows Desk shows in Select Items to Manufacture. Nothing is inserted."""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Work Order")
	if not _can_deliver(doc) or cint(doc.is_subcontracted):
		frappe.throw(_("Nothing left on {0} to manufacture.").format(name))
	from erpnext.selling.doctype.sales_order.sales_order import (
		get_work_order_items as erp_get,
	)

	return {"items": erp_get(name) or []}


@frappe.whitelist(methods=["POST"])
def make_work_orders(source_name: str, items) -> dict:
	"""Insert work orders for the BOM and quantity the operator confirmed."""
	require_login()
	name, doc = _load_submitted(source_name)
	_require_create("Work Order")
	if not _can_deliver(doc) or cint(doc.is_subcontracted):
		frappe.throw(_("Nothing left on {0} to manufacture.").format(name))
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if isinstance(items, dict):
		items = items.get("items")
	if not isinstance(items, list) or not items:
		frappe.throw(_("Please select atleast one item to continue"))
	for row in items:
		if not isinstance(row, dict) or not row.get("bom"):
			frappe.throw(_("Please select BOM against item {0}").format(row.get("item_code") if isinstance(row, dict) else ""))
		if not flt(row.get("pending_qty")):
			frappe.throw(_("Please select Qty against item {0}").format(row.get("item_code")))
	import json

	from erpnext.selling.doctype.sales_order.sales_order import make_work_orders as erp_make

	names = erp_make(json.dumps({"items": items}), name, doc.company, doc.get("project"))
	return {"names": names or []}
