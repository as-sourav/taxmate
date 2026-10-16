"""UAE e-invoice orchestration: generate, submit to ASP, track status."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.file_manager import save_file

from taxmate.uae_e_invoicing.utils.pint_ae import build_pint_ae_payload, payload_to_json

# ASP status strings (lowercased) -> TaxMate status.
# Includes Complyance Unify ``data.state`` values for defense in depth when
# callers pass the raw state instead of the adapter's mapped ``status``.
ASP_STATUS_MAP = {
	"submitted": "Submitted",
	"validated": "Submitted",
	"processing": "Submitted",
	"delivery_success": "Submitted",
	"delivery_failed": "Submitted",
	"accepted": "Accepted",
	"delivered": "Accepted",
	"final_valid": "Accepted",
	"rejected": "Rejected",
	"final_invalid": "Rejected",
	"failed": "Failed",
}


def map_asp_status(asp_status: str | None) -> str | None:
	"""Map an ASP status or Complyance state onto a TaxMate e-invoice status."""
	key = str(asp_status or "").strip()
	if not key:
		return None
	# Adapter may already return TaxMate title-case.
	if key in ("Queued", "Submitted", "Accepted", "Rejected", "Failed"):
		return key
	return ASP_STATUS_MAP.get(key.lower())


def get_api():
	"""Complyance is the only ASP. Payloads stay PINT-AE, the UAE specification."""
	from taxmate.uae_e_invoicing.api_classes.complyance import ComplyanceAPI

	return ComplyanceAPI()


def is_e_invoice_applicable(doc) -> bool:
	if doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
		return False
	if not frappe.db.has_column("Company", "uae_e_invoice_enabled"):
		return False
	if not frappe.db.get_value("Company", doc.company, "uae_e_invoice_enabled"):
		return False
	if doc.doctype == "Purchase Invoice" and not doc.get("uae_submit_to_fta"):
		return False
	if doc.doctype == "Sales Invoice" and _exclude_b2c() and _is_b2c_sales_invoice(doc):
		return False
	return True


def _exclude_b2c() -> bool:
	from taxmate.uae_e_invoicing.utils.mandate import setting_on

	return setting_on("exclude_b2c_e_invoices", default=1)


def _is_b2c_sales_invoice(doc) -> bool:
	from taxmate.uae_e_invoicing.utils.mandate import is_b2c_party

	tax_id = None
	if doc.get("customer"):
		tax_id = frappe.db.get_value("Customer", doc.customer, "tax_id")
	return is_b2c_party(tax_id)


@frappe.whitelist()
def generate_e_invoice(docname: str, doctype: str = "Sales Invoice", throw: bool = True):
	"""Generate the PINT-AE payload, submit to the ASP, and log the result."""
	if doctype not in ("Sales Invoice", "Purchase Invoice"):
		frappe.throw(_("E-invoicing is only supported for Sales Invoice and Purchase Invoice."))
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("submit")

	if not is_e_invoice_applicable(doc):
		if doc.doctype == "Sales Invoice" and _exclude_b2c() and _is_b2c_sales_invoice(doc):
			msg = _("B2C sales invoices are excluded from UAE e-invoicing until the FTA requires them.")
		else:
			msg = _("UAE e-invoicing is not enabled for company {0}.").format(doc.company)
		if throw:
			frappe.throw(msg)
		frappe.msgprint(msg)
		return None

	if doc.docstatus != 1:
		frappe.throw(_("{0} must be submitted before generating an e-invoice.").format(doctype))

	if doc.get("uae_e_invoice_status") in ("Queued", "Generated", "Submitted", "Accepted"):
		frappe.throw(_("E-invoice already submitted for {0}.").format(doc.name))

	return generate_and_submit(doc)


def generate_and_submit(doc) -> str:
	"""Build payload, create/update the log, submit to the ASP."""
	from frappe.utils.synchronization import filelock

	# Serialize first UUID assignment per invoice (concurrent submit race)
	lock_name = f"uae_e_invoice_submit_{doc.doctype}_{doc.name}"
	with filelock(lock_name, timeout=60):
		reuse_uuid = _existing_log_uuid(doc)

		if doc.doctype == "Purchase Invoice":
			from taxmate.uae_e_invoicing.utils.purchase_transaction_data import (
				build_purchase_pint_ae_payload,
			)

			doc_uuid, payload = build_purchase_pint_ae_payload(doc, doc_uuid=reuse_uuid)
		else:
			doc_uuid, payload = build_pint_ae_payload(doc, doc_uuid=reuse_uuid)

		payload_json = payload_to_json(payload)
		log = _get_or_create_log(doc, doc_uuid, payload_json)

	_replace_attachment(
		("UAE E-Invoice Log", log.name),
		f"{doc.name}-uae-e-invoice.json",
		payload_json.encode("utf-8"),
	)

	try:
		api = get_api()
		result = api.submit_invoice(payload)
	except Exception as e:
		frappe.log_error(
			title=f"UAE e-invoice submission failed for {doc.name}",
			message=frappe.get_traceback(),
		)
		log.db_set(
			{
				"status": "Failed",
				"error_message": str(e)[:500],
			},
			update_modified=False,
		)
		_set_invoice_status(doc, "Failed", log.name)
		return log.name

	status = map_asp_status(result.get("status")) or "Submitted"
	updates = {
		"status": status,
		"asp_document_id": result.get("document_id"),
		"submitted_on": now_datetime(),
		"error_message": None,
		"response_json": frappe.as_json(result.get("raw") or result),
	}
	if status == "Accepted":
		updates["accepted_on"] = now_datetime()
	log.db_set(updates, update_modified=False)
	_set_invoice_status(doc, status, log.name)

	if status == "Accepted" and result.get("document_id"):
		_enqueue_fetch_documents(log.name)

	return log.name


@frappe.whitelist()
def sync_status_from_asp(log_name: str) -> str | None:
	"""Poll ASP for current status and apply locally.

	Returns the mapped TaxMate status string, or None if poll/mapping failed.
	"""
	log = frappe.get_doc("UAE E-Invoice Log", log_name)
	# Scheduler runs as Administrator; Desk calls need read on the log
	if frappe.session.user != "Administrator":
		log.check_permission("read")
	if not log.asp_document_id:
		return None

	api = get_api()
	try:
		result = api.get_document_status(log.asp_document_id) or {}
	except Exception:
		frappe.log_error(
			title=f"UAE e-invoice status poll failed for {log.reference_name}",
			message=frappe.get_traceback(),
		)
		return None

	asp_status = result.get("status") or result.get("document_status") or result.get("documentStatus") or ""
	mapped = map_asp_status(asp_status)
	if not mapped:
		return None

	apply_status_update(log.asp_document_id, mapped, response=result)
	return mapped


def apply_status_update(asp_document_id: str, asp_status: str, response: dict | None = None) -> str | None:
	"""Update log + invoice from an ASP status event (webhook / polling)."""
	log_name = frappe.db.get_value("UAE E-Invoice Log", {"asp_document_id": asp_document_id}, "name")
	if not log_name:
		return None

	status = map_asp_status(asp_status)
	if not status:
		return None

	log = frappe.get_doc("UAE E-Invoice Log", log_name)

	# Do not weaken a terminal Accepted status via webhook replay
	if log.status == "Accepted" and status in ("Rejected", "Failed", "Submitted", "Queued"):
		return log_name

	updates = {"status": status}
	if response:
		updates["response_json"] = frappe.as_json(response)
	log.db_set(updates, update_modified=False)

	if frappe.db.exists(log.reference_doctype, log.reference_name):
		frappe.db.set_value(
			log.reference_doctype,
			log.reference_name,
			"uae_e_invoice_status",
			status,
			update_modified=False,
		)

	if status == "Accepted":
		if not log.get("accepted_on"):
			log.db_set("accepted_on", now_datetime(), update_modified=False)
		_enqueue_fetch_documents(log_name)

	return log_name


@frappe.whitelist()
def fetch_asp_documents(log_name: str):
	"""Fetch signed XML + PDF from the ASP and attach to the invoice."""
	log = frappe.get_doc("UAE E-Invoice Log", log_name)
	if frappe.session.user == "Guest":
		frappe.only_for("System Manager")
	log.check_permission("read")
	if not log.asp_document_id:
		return

	api = get_api()
	reference = (log.reference_doctype, log.reference_name)

	try:
		xml_content = api.get_document_xml(log.asp_document_id)
		if xml_content:
			_replace_attachment(reference, f"{log.reference_name}-uae-e-invoice.xml", xml_content)
			_replace_attachment(
				("UAE E-Invoice Log", log.name), f"{log.reference_name}-uae-e-invoice.xml", xml_content
			)

		pdf_content = api.get_document_pdf(log.asp_document_id)
		if pdf_content:
			_replace_attachment(reference, f"{log.reference_name}-uae-e-invoice.pdf", pdf_content)
			_replace_attachment(
				("UAE E-Invoice Log", log.name), f"{log.reference_name}-uae-e-invoice.pdf", pdf_content
			)
	except Exception:
		frappe.log_error(
			title=f"UAE e-invoice document fetch failed for {log.name}",
			message=frappe.get_traceback(),
		)


@frappe.whitelist()
def bulk_generate_e_invoices(docnames: str | list, doctype: str = "Sales Invoice"):
	"""Submit e-invoices for multiple invoices from the list view."""
	if doctype not in ("Sales Invoice", "Purchase Invoice"):
		frappe.throw(_("E-invoicing is only supported for Sales Invoice and Purchase Invoice."))
	if isinstance(docnames, str):
		docnames = frappe.parse_json(docnames)
	if not isinstance(docnames, list):
		frappe.throw(_("docnames must be a list"))
	if len(docnames) > 50:
		frappe.throw(_("Bulk generate is limited to 50 documents at a time."))

	submitted, skipped, failed = [], [], []
	for docname in docnames:
		doc = frappe.get_doc(doctype, docname)
		if not frappe.has_permission(doctype, "submit", doc):
			skipped.append(docname)
			continue
		if (
			doc.docstatus != 1
			or not is_e_invoice_applicable(doc)
			or doc.get("uae_e_invoice_status") in ("Submitted", "Accepted", "Queued", "Generated")
		):
			skipped.append(docname)
			continue
		try:
			generate_and_submit(doc)
			submitted.append(docname)
		except Exception:
			failed.append(docname)
			frappe.log_error(
				title=f"UAE e-invoice bulk submit failed for {docname}",
				message=frappe.get_traceback(),
			)

	return {"submitted": submitted, "skipped": skipped, "failed": failed}


def enqueue_generate(docname: str, doctype: str = "Sales Invoice"):
	frappe.enqueue(
		"taxmate.uae_e_invoicing.utils.e_invoice.generate_e_invoice",
		queue="short",
		docname=docname,
		doctype=doctype,
		throw=False,
	)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _existing_log_uuid(doc) -> str | None:
	"""Reuse the fiscal UUID from an existing log on retry."""
	log_name = doc.get("uae_e_invoice_log")
	if not log_name:
		log_name = frappe.db.get_value(
			"UAE E-Invoice Log",
			{"reference_doctype": doc.doctype, "reference_name": doc.name},
			"name",
		)
	if not log_name:
		return None
	return frappe.db.get_value("UAE E-Invoice Log", log_name, "uuid")


def _get_or_create_log(doc, doc_uuid: str, payload_json: str):
	existing = doc.get("uae_e_invoice_log")
	if not existing:
		existing = frappe.db.get_value(
			"UAE E-Invoice Log",
			{"reference_doctype": doc.doctype, "reference_name": doc.name},
			"name",
		)
	if existing and frappe.db.exists("UAE E-Invoice Log", existing):
		log = frappe.get_doc("UAE E-Invoice Log", existing)
		updates = {"payload": payload_json, "status": "Generated"}
		# Never overwrite an existing fiscal UUID (ASP idempotency)
		if not log.uuid and doc_uuid:
			updates["uuid"] = doc_uuid
		if not log.get("issued_on"):
			from taxmate.uae_e_invoicing.utils.mandate import sla_due_date

			issued = _invoice_issued_on(doc)
			updates["issued_on"] = issued
			updates["sla_due"] = sla_due_date(issued)
		updates["taxable_amount"] = doc.get("base_net_total") or 0
		updates["vat_amount"] = _invoice_uae_vat_amount(doc)
		log.db_set(updates, update_modified=False)
		return log

	issued = _invoice_issued_on(doc)
	from taxmate.uae_e_invoicing.utils.mandate import sla_due_date

	log = frappe.get_doc(
		{
			"doctype": "UAE E-Invoice Log",
			"company": doc.company,
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"uuid": doc_uuid,
			"status": "Generated",
			"document_type_code": doc.get("uae_document_type_code") or "",
			"payload": payload_json,
			"issued_on": issued,
			"sla_due": sla_due_date(issued),
			"taxable_amount": doc.get("base_net_total") or 0,
			"vat_amount": _invoice_uae_vat_amount(doc),
		}
	)
	log.insert(ignore_permissions=True)
	return log


def _set_invoice_status(doc, status: str, log_name: str):
	frappe.db.set_value(
		doc.doctype,
		doc.name,
		{
			"uae_e_invoice_status": status,
			"uae_e_invoice_log": log_name,
		},
		update_modified=False,
	)


def _enqueue_fetch_documents(log_name: str):
	frappe.enqueue(
		"taxmate.uae_e_invoicing.utils.e_invoice.fetch_asp_documents",
		queue="short",
		user="Administrator",
		log_name=log_name,
	)


def _replace_attachment(reference: tuple[str, str], file_name: str, content: bytes):
	doctype, name = reference
	stale = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"file_name": file_name,
		},
		pluck="name",
	)
	for file_name_to_delete in stale:
		frappe.delete_doc("File", file_name_to_delete, force=1, ignore_permissions=True)

	save_file(file_name, content, doctype, name, is_private=1)


def _invoice_issued_on(doc):
	"""SLA clock starts on the invoice issue/posting date, not generate time."""
	from frappe.utils import get_datetime

	posting_date = doc.get("posting_date") if hasattr(doc, "get") else getattr(doc, "posting_date", None)
	if posting_date:
		return get_datetime(posting_date)
	return now_datetime()


def _invoice_uae_vat_amount(doc) -> float:
	"""VAT on the invoice from mapped UAE VAT accounts, else header tax."""
	from frappe.utils import flt

	fallback = flt(doc.get("base_total_taxes_and_charges"))
	if not frappe.db.exists("DocType", "UAE VAT Account"):
		return fallback
	accounts = frappe.get_all(
		"UAE VAT Account",
		filters={"parent": doc.company, "parenttype": "UAE VAT Settings"},
		pluck="account",
	)
	if not accounts:
		return fallback
	return flt(
		sum(
			flt(row.get("base_tax_amount"))
			for row in (doc.get("taxes") or [])
			if row.get("account_head") in accounts
		),
		2,
	)
