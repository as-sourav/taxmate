"""Map Desk create-buttons onto unsaved drafts for the SPA.

Callers: taxmate.api.get_catalog(); screens that open Opportunity, Request for
Quotation, Shipment, Installation Note, Delivery Trip, Payment Request,
Subcontracting Order, and Subcontracting Inward Order.

Each method checks the name is a string before it loads a document, then
calls the ERPNext mapper. The SPA inserts the draft. Nothing here posts to
Desk /app/.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from taxmate.api.resource import assert_allowed_doctype, require_login
from taxmate.utils.company import get_default_company

_PAYMENT_REQUEST_SOURCES = ("Sales Order", "Purchase Order", "Sales Invoice", "Purchase Invoice")


def _required_name(value: object, label: str) -> str:
	if not isinstance(value, str) or not value.strip():
		frappe.throw(_("{0} is required").format(label))
	return value.strip()


def _require_create(doctype: str) -> None:
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("Not permitted to create {0}").format(_(doctype)), frappe.PermissionError)


def _load(doctype: str, name: str):
	assert_allowed_doctype(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc


def _payload(result, doctype: str) -> dict:
	if hasattr(result, "as_dict"):
		data = result.as_dict()
		name = result.name
	elif isinstance(result, dict):
		data = dict(result)
		name = data.get("name")
	else:
		frappe.throw(_("Could not map {0}").format(_(doctype)))
	data = dict(data)
	data["_already_saved"] = 1 if name and frappe.db.exists(doctype, name) else 0
	return data


@frappe.whitelist(methods=["POST"])
def make_opportunity_from_customer(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Customer"))
	_load("Customer", source_name)
	assert_allowed_doctype("Opportunity")
	_require_create("Opportunity")
	from erpnext.selling.doctype.customer.customer import make_opportunity

	return _payload(make_opportunity(source_name), "Opportunity")


@frappe.whitelist(methods=["POST"])
def make_opportunity_from_lead(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Lead"))
	lead = _load("Lead", source_name)
	if frappe.db.get_value("Customer", {"lead_name": lead.name}):
		frappe.throw(_("Lead {0} is already a customer.").format(source_name))
	assert_allowed_doctype("Opportunity")
	_require_create("Opportunity")
	from erpnext.crm.doctype.lead.lead import make_opportunity

	return _payload(make_opportunity(source_name), "Opportunity")


@frappe.whitelist(methods=["POST"])
def make_quotation_from_opportunity(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Opportunity"))
	doc = _load("Opportunity", source_name)
	if doc.status == "Lost":
		frappe.throw(_("Opportunity is lost"))
	assert_allowed_doctype("Quotation")
	_require_create("Quotation")
	from erpnext.crm.doctype.opportunity.opportunity import make_quotation

	return _payload(make_quotation(source_name), "Quotation")


@frappe.whitelist(methods=["POST"])
def make_supplier_quotation_from_opportunity(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Opportunity"))
	doc = _load("Opportunity", source_name)
	if doc.status == "Lost":
		frappe.throw(_("Opportunity is lost"))
	if not doc.get("items"):
		frappe.throw(_("Add items before creating a supplier quotation"))
	assert_allowed_doctype("Supplier Quotation")
	_require_create("Supplier Quotation")
	from erpnext.crm.doctype.opportunity.opportunity import make_supplier_quotation

	return _payload(make_supplier_quotation(source_name), "Supplier Quotation")


@frappe.whitelist(methods=["POST"])
def make_rfq_from_opportunity(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Opportunity"))
	doc = _load("Opportunity", source_name)
	if doc.status == "Lost":
		frappe.throw(_("Opportunity is lost"))
	if not doc.get("items"):
		frappe.throw(_("Add items before creating a request for quotation"))
	assert_allowed_doctype("Request for Quotation")
	_require_create("Request for Quotation")
	from erpnext.crm.doctype.opportunity.opportunity import make_request_for_quotation

	return _payload(make_request_for_quotation(source_name), "Request for Quotation")


@frappe.whitelist(methods=["POST"])
def make_rfq_from_material_request(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Material Request"))
	doc = _load("Material Request", source_name)
	if doc.docstatus != 1 or doc.status == "Stopped" or doc.material_request_type != "Purchase":
		frappe.throw(_("Request for Quotation is only available on an open purchase material request"))
	if flt(doc.per_ordered) >= 100:
		frappe.throw(_("Material Request is fully ordered"))
	assert_allowed_doctype("Request for Quotation")
	_require_create("Request for Quotation")
	from erpnext.stock.doctype.material_request.material_request import make_request_for_quotation

	return _payload(make_request_for_quotation(source_name), "Request for Quotation")


@frappe.whitelist(methods=["POST"])
def make_supplier_rfq(supplier: str) -> dict:
	"""Blank Request for Quotation with the supplier on the first row.

	Desk does this in the form, not through a mapper.
	"""
	require_login()
	supplier = _required_name(supplier, _("Supplier"))
	_load("Supplier", supplier)
	assert_allowed_doctype("Request for Quotation")
	_require_create("Request for Quotation")
	doc = frappe.new_doc("Request for Quotation")
	company = get_default_company()
	if company:
		doc.company = company
	# Desk fills contact and email from the supplier when the row is added.
	row = {"supplier": supplier}
	if company:
		from erpnext.accounts.party import get_party_details

		try:
			details = get_party_details(party=supplier, party_type="Supplier", company=company) or {}
		except frappe.ValidationError:
			details = {}
		if details.get("contact_person"):
			row["contact"] = details.get("contact_person")
		if details.get("contact_email"):
			row["email_id"] = details.get("contact_email")
	doc.append("suppliers", row)
	return _payload(doc, "Request for Quotation")


@frappe.whitelist(methods=["POST"])
def make_supplier_quotation_from_rfq(source_name: str, for_supplier: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Request for Quotation"))
	for_supplier = _required_name(for_supplier, _("Supplier"))
	doc = _load("Request for Quotation", source_name)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the Request for Quotation first"))
	suppliers = {row.supplier for row in doc.get("suppliers") or []}
	if for_supplier not in suppliers:
		frappe.throw(_("Supplier is not on this Request for Quotation"))
	assert_allowed_doctype("Supplier Quotation")
	_require_create("Supplier Quotation")
	from erpnext.buying.doctype.request_for_quotation.request_for_quotation import (
		make_supplier_quotation_from_rfq as erp_make,
	)

	return _payload(erp_make(source_name, for_supplier=for_supplier), "Supplier Quotation")


def shipment_delivery_row(source_name: str, value_of_goods: object, row_totals: list) -> dict:
	"""One Shipment Delivery Note row for the source delivery note.

	ERPNext maps each delivery-note item onto this child table. The child
	table stores the delivery note, not the item, and delivery_note is required.
	"""
	total = flt(value_of_goods) or sum(flt(value) for value in row_totals)
	return {"delivery_note": source_name, "grand_total": total}


def _open_delivery_note(source_name: str):
	doc = _load("Delivery Note", source_name)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the Delivery Note first"))
	if doc.is_return:
		frappe.throw(_("A return cannot start this document"))
	if doc.status == "Closed":
		frappe.throw(_("Delivery Note is closed"))
	return doc


@frappe.whitelist(methods=["POST"])
def make_shipment_from_delivery_note(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Delivery Note"))
	_open_delivery_note(source_name)
	assert_allowed_doctype("Shipment")
	_require_create("Shipment")
	from erpnext.stock.doctype.delivery_note.delivery_note import make_shipment

	shipment = make_shipment(source_name)
	row = shipment_delivery_row(
		source_name,
		shipment.value_of_goods,
		[entry.grand_total for entry in (shipment.get("shipment_delivery_note") or [])],
	)
	shipment.set("shipment_delivery_note", [])
	shipment.append("shipment_delivery_note", row)
	return _payload(shipment, "Shipment")


@frappe.whitelist(methods=["POST"])
def make_installation_note_from_delivery_note(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Delivery Note"))
	doc = _open_delivery_note(source_name)
	if flt(doc.per_installed) >= 100:
		frappe.throw(_("Delivery Note is fully installed"))
	assert_allowed_doctype("Installation Note")
	_require_create("Installation Note")
	from erpnext.stock.doctype.delivery_note.delivery_note import make_installation_note

	return _payload(make_installation_note(source_name), "Installation Note")


@frappe.whitelist(methods=["POST"])
def make_delivery_trip_from_delivery_note(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Delivery Note"))
	doc = _open_delivery_note(source_name)
	if doc.status == "Completed":
		frappe.throw(_("Delivery Note is completed"))
	assert_allowed_doctype("Delivery Trip")
	_require_create("Delivery Trip")
	from erpnext.stock.doctype.delivery_note.delivery_note import make_delivery_trip

	return _payload(make_delivery_trip(source_name), "Delivery Trip")


@frappe.whitelist(methods=["POST"])
def make_payment_request(reference_doctype: str, reference_name: str) -> dict:
	require_login()
	if not isinstance(reference_doctype, str) or reference_doctype not in _PAYMENT_REQUEST_SOURCES:
		frappe.throw(_("Payment Requests cannot be created against this document"))
	reference_name = _required_name(reference_name, _(reference_doctype))
	doc = _load(reference_doctype, reference_name)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the document first"))
	if reference_doctype == "Sales Invoice":
		if doc.is_return or flt(doc.outstanding_amount) <= 0:
			frappe.throw(_("Payment Request is not available on this invoice"))
	elif reference_doctype == "Purchase Invoice":
		if doc.is_return or doc.on_hold or flt(doc.outstanding_amount) <= 0:
			frappe.throw(_("Payment Request is not available on this invoice"))
	elif reference_doctype == "Sales Order":
		# Desk shows this while On Hold. The cutoff includes Accounts Settings
		# over-billing allowance, same as sales_order.js.
		allowance = flt(frappe.db.get_single_value("Accounts Settings", "over_billing_allowance"))
		if doc.status == "Closed" or flt(doc.per_billed) >= 100 + allowance:
			frappe.throw(_("Payment Request is not available on this sales order"))
	elif reference_doctype == "Purchase Order":
		if doc.status in ("Closed", "On Hold") or flt(doc.per_billed) >= 100:
			frappe.throw(_("Payment Request is not available on this purchase order"))
	assert_allowed_doctype("Payment Request")
	_require_create("Payment Request")
	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request as erp_make

	return _payload(erp_make(dt=reference_doctype, dn=reference_name), "Payment Request")


@frappe.whitelist(methods=["POST"])
def make_payment_entry_from_request(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Payment Request"))
	doc = _load("Payment Request", source_name)
	if doc.payment_request_type != "Outward" or doc.status not in ("Initiated", "Partially Paid"):
		frappe.throw(_("Payment Entry is not available on this payment request"))
	assert_allowed_doctype("Payment Entry")
	_require_create("Payment Entry")
	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_entry

	return _payload(make_payment_entry(source_name), "Payment Entry")


def _subcontract_rows_open(doc) -> bool:
	rows = doc.get("items") or []
	return any(flt(row.qty) != flt(row.subcontracted_qty) for row in rows)


@frappe.whitelist(methods=["POST"])
def make_subcontracting_order_from_purchase_order(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Purchase Order"))
	doc = _load("Purchase Order", source_name)
	if doc.docstatus != 1 or doc.status in ("Closed", "On Hold"):
		frappe.throw(_("Subcontracting Order is not available on this purchase order"))
	if not doc.is_subcontracted or doc.is_old_subcontracting_flow:
		frappe.throw(_("Purchase Order is not a subcontracting order"))
	pending_receipt = any(
		not row.delivered_by_supplier and flt(row.received_qty) < flt(row.qty) for row in (doc.items or [])
	)
	if not pending_receipt or not _subcontract_rows_open(doc):
		frappe.throw(_("Purchase Order has no quantity left to subcontract"))
	assert_allowed_doctype("Subcontracting Order")
	_require_create("Subcontracting Order")
	from erpnext.buying.doctype.purchase_order.purchase_order import make_subcontracting_order

	return _payload(make_subcontracting_order(source_name, save=False, submit=False), "Subcontracting Order")


@frappe.whitelist(methods=["POST"])
def make_subcontracting_inward_from_sales_order(source_name: str) -> dict:
	require_login()
	source_name = _required_name(source_name, _("Sales Order"))
	doc = _load("Sales Order", source_name)
	if doc.docstatus != 1 or doc.status in ("Closed", "On Hold"):
		frappe.throw(_("Subcontracting Inward Order is not available on this sales order"))
	if not doc.is_subcontracted or not _subcontract_rows_open(doc):
		frappe.throw(_("Sales Order has no quantity left to subcontract"))
	assert_allowed_doctype("Subcontracting Inward Order")
	_require_create("Subcontracting Inward Order")
	from erpnext.selling.doctype.sales_order.sales_order import make_subcontracting_inward_order

	return _payload(make_subcontracting_inward_order(source_name), "Subcontracting Inward Order")
