"""Phase 9 prove-it: fixture company, golden VAT 201, e-invoice matrix, migrate inventory.

Run: bench --site taxmate.site run-tests --module taxmate.tests.test_uae_prove
"""

from __future__ import annotations

import unittest
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from taxmate.tests.uae_prove_fixtures import (
	GOLDEN,
	PERIOD_END,
	PERIOD_START,
	PHASE_DOCTYPES,
	PHASE_REPORTS,
	SUBMITTABLE_AFTER_MIGRATE,
	attached_file_content,
	boxes_by_no,
	build_prove_set,
	parse_boxes_csv,
	require_prove_site,
)
from taxmate.uae_vat.constants.tenancy import TAX_MANAGER_ROLE


class TestRetryPolicy(unittest.TestCase):
	def test_rejected_is_not_blindly_resubmitted(self):
		from taxmate.uae_e_invoicing.background_jobs.retry import SKIP_RESUBMIT_STATUSES

		self.assertIn("Rejected", SKIP_RESUBMIT_STATUSES)
		self.assertIn("Submitted", SKIP_RESUBMIT_STATUSES)
		self.assertIn("Accepted", SKIP_RESUBMIT_STATUSES)
		self.assertNotIn("Failed", SKIP_RESUBMIT_STATUSES)


class TestUatMigrateInventory(FrappeTestCase):
	def test_phase_doctypes_exist_after_migrate(self):
		for doctype in PHASE_DOCTYPES:
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)
			meta = frappe.get_meta(doctype)
			self.assertTrue(meta.get("field_order") or meta.fields, doctype)

	def test_statutory_doctypes_are_submittable(self):
		for doctype in SUBMITTABLE_AFTER_MIGRATE:
			self.assertTrue(frappe.get_meta(doctype).is_submittable, doctype)

	def test_reports_and_tax_manager_role(self):
		self.assertTrue(frappe.db.exists("Role", TAX_MANAGER_ROLE))
		for report in PHASE_REPORTS:
			self.assertTrue(frappe.db.exists("Report", report), report)


class TestFixtureGoldenVat201(FrappeTestCase):
	def test_golden_vat_201_matches_accountant_pack(self):
		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))
		docs = build_prove_set(company)
		self.assertEqual(docs["standard"].items[0].is_zero_rated, 0)
		self.assertEqual(docs["zero"].items[0].is_zero_rated, 1)
		self.assertEqual(docs["exempt"].items[0].is_exempt, 1)
		self.assertGreater(flt(docs["tourist"].tourist_tax_return), 0)
		self.assertEqual(docs["credit"].is_return, 1)
		self.assertEqual(docs["credit"].return_against, docs["standard"].name)
		self.assertEqual(docs["rcm"].reverse_charge, "Y")
		self.assertEqual(docs["customs"].docstatus, 1)

		from unittest.mock import patch

		from taxmate.uae_vat.utils.vat_201 import (
			compute_vat_201,
			list_period_invoices,
			sum_customs_declarations,
		)
		from taxmate.uae_vat.utils.vat_201_export import export_accountant_pack

		customs = sum_customs_declarations(company, PERIOD_START, PERIOD_END)
		computed = compute_vat_201(
			company,
			PERIOD_START,
			PERIOD_END,
			box_6_amount=customs["box_6_amount"],
			box_6_vat_amount=customs["box_6_vat_amount"],
			box_7_amount=customs["box_7_amount"],
			box_7_vat_amount=customs["box_7_vat_amount"],
		)
		computed_boxes = boxes_by_no(computed)
		for box_no, expected in GOLDEN.items():
			for field, value in expected.items():
				self.assertEqual(computed_boxes[box_no][field], value, f"{box_no}.{field}")

		log = frappe.get_doc(
			{
				"doctype": "UAE VAT 201 Filing Log",
				"company": company,
				"period_start": PERIOD_START,
				"period_end": PERIOD_END,
			}
		).insert()
		log.generate()
		log.reload()
		filed_boxes = boxes_by_no(log)
		for box_no, expected in GOLDEN.items():
			for field, value in expected.items():
				self.assertEqual(filed_boxes[box_no][field], value, f"filing {box_no}.{field}")

		# Worksheet PDF uses wkhtmltopdf and can hang in this bench; CSV pack is the golden source.
		with patch("taxmate.uae_vat.utils.vat_201_export._attach_worksheet_pdf", return_value=False):
			export_accountant_pack(log)
		csv_boxes = parse_boxes_csv(attached_file_content(log.doctype, log.name, f"VAT201-boxes-{log.name}-"))
		for box_no, expected in GOLDEN.items():
			for field, value in expected.items():
				self.assertEqual(csv_boxes[box_no][field], value, f"pack {box_no}.{field}")

		invoices = list_period_invoices(company, PERIOD_START, PERIOD_END)
		names = {row["name"] for row in invoices}
		self.assertIn(docs["standard"].name, names)
		self.assertIn(docs["zero"].name, names)
		self.assertIn(docs["exempt"].name, names)
		self.assertIn(docs["tourist"].name, names)
		self.assertIn(docs["credit"].name, names)
		self.assertIn(docs["rcm"].name, names)
		credit_row = next(row for row in invoices if row["name"] == docs["credit"].name)
		self.assertEqual(credit_row["is_return"], 1)

		pack_invoices = attached_file_content(log.doctype, log.name, f"VAT201-invoices-{log.name}-")
		self.assertIn(docs["credit"].name, pack_invoices)
		pack_customs = attached_file_content(log.doctype, log.name, f"VAT201-customs-{log.name}-")
		self.assertIn(docs["customs"].declaration_number, pack_customs)
		self.assertIn(docs["customs"].name, pack_customs)


class TestEInvoiceMatrix(FrappeTestCase):
	def setUp(self):
		try:
			self.company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))
		if not frappe.db.exists("Customer", "E2E Test Customer LLC"):
			self.skipTest("B2B customer missing")

	def _dummy_invoice(self, status: str):
		return frappe._dict(
			doctype="Sales Invoice",
			name="TM-PROVE-EINV",
			company=self.company,
			customer="E2E Test Customer LLC",
			uae_e_invoice_status=status,
			uae_e_invoice_log=None,
		)

	def test_cancel_blocked_once_queued_or_reported(self):
		from taxmate.uae_e_invoicing.overrides.sales_invoice import before_cancel
		from taxmate.uae_e_invoicing.utils.e_invoice import is_e_invoice_applicable

		doc = self._dummy_invoice("Accepted")
		self.assertTrue(is_e_invoice_applicable(doc))
		for status in ("Queued", "Generated", "Submitted", "Accepted"):
			doc.uae_e_invoice_status = status
			with self.assertRaises(frappe.ValidationError):
				before_cancel(doc)

	def test_cancel_allowed_after_failed_or_rejected(self):
		from taxmate.uae_e_invoicing.overrides.sales_invoice import before_cancel

		for status in ("Failed", "Rejected", "Cancelled", None):
			before_cancel(self._dummy_invoice(status))

	def test_reject_retry_and_uuid_reuse(self):
		from taxmate.uae_e_invoicing.utils.e_invoice import _existing_log_uuid, apply_status_update

		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": "E2E Test Customer LLC",
				"posting_date": PERIOD_START,
				"due_date": "2026-12-15",
				"set_posting_time": 1,
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"vat_emirate": "Dubai",
				"taxes_and_charges": "UAE VAT 5% - TM",
				"items": [{"item_code": "DEMO-VAT-CONSULTING", "qty": 1, "rate": 10}],
			}
		).insert()
		asp_id = f"asp-{frappe.generate_hash(length=8)}"
		doc_uuid = str(uuid.uuid4())
		log = frappe.get_doc(
			{
				"doctype": "UAE E-Invoice Log",
				"company": self.company,
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"uuid": doc_uuid,
				"status": "Submitted",
				"asp_document_id": asp_id,
			}
		).insert()

		apply_status_update(asp_id, "rejected")
		log.reload()
		self.assertEqual(log.status, "Rejected")
		self.assertFalse(
			frappe.get_all(
				"UAE E-Invoice Log",
				filters={"status": "Failed", "retry_count": ("<", 5), "name": log.name},
			)
		)

		log.db_set("status", "Accepted", update_modified=False)
		apply_status_update(asp_id, "rejected")
		log.reload()
		self.assertEqual(log.status, "Accepted")

		si.uae_e_invoice_log = log.name
		self.assertEqual(_existing_log_uuid(si), doc_uuid)

	def test_credit_note_carries_billing_reference(self):
		docs = build_prove_set(self.company, period_start="2026-11-01")
		from taxmate.uae_e_invoicing.utils.transaction_data import UAETransactionData

		data = UAETransactionData(docs["credit"])
		self.assertEqual(data.get_document_type_code(), "381")
		credit = data._get_credit_note_details()
		self.assertEqual(credit["reference"]["id"], docs["standard"].name)
		self.assertEqual(credit["reason"], "GOODS_OR_SERVICES_RETURNED")
		self.assertEqual(str(credit["reference"]["issue_date"]), "2026-11-01")
