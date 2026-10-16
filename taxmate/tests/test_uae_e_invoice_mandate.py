"""Phase 3 e-invoicing mandate helpers (pure + light site tests)."""

from __future__ import annotations

import unittest

from taxmate.uae_e_invoicing.utils.mandate import is_b2c_party, sla_due_date, sla_status, vat_group_tin


class TestVatGroupTin(unittest.TestCase):
	def test_first_ten_digits(self):
		self.assertEqual(vat_group_tin("100000000000003"), "1000000000")

	def test_strips_spaces(self):
		self.assertEqual(vat_group_tin("100 000000000003"), "1000000000")

	def test_short_returns_none(self):
		self.assertIsNone(vat_group_tin("123"))


class TestB2C(unittest.TestCase):
	def test_no_trn_is_b2c(self):
		self.assertTrue(is_b2c_party(None))
		self.assertTrue(is_b2c_party(""))

	def test_valid_trn_is_b2b(self):
		self.assertFalse(is_b2c_party("100000000000003"))


class TestSla(unittest.TestCase):
	def test_due_is_issued_plus_14(self):
		self.assertEqual(str(sla_due_date("2026-01-01", sla_days=14)), "2026-01-15")

	def test_custom_window(self):
		self.assertEqual(str(sla_due_date("2026-01-01", sla_days=7)), "2026-01-08")

	def test_met_when_accepted_on_time(self):
		self.assertEqual(sla_status("2026-01-01", "2026-01-10", today="2026-02-01", sla_days=14), "Met")

	def test_late_when_accepted_after_due(self):
		self.assertEqual(sla_status("2026-01-01", "2026-01-20", today="2026-02-01", sla_days=14), "Late")

	def test_breached_when_still_open(self):
		self.assertEqual(sla_status("2026-01-01", None, today="2026-01-20", sla_days=14), "Breached")

	def test_open_inside_window(self):
		self.assertEqual(sla_status("2026-01-01", None, today="2026-01-10", sla_days=14), "Open")


class TestContingencyDue(unittest.TestCase):
	def test_report_due_is_start_plus_two(self):
		from frappe.utils import add_days, getdate

		from taxmate.uae_e_invoicing.constants import CONTINGENCY_REPORT_DAYS

		self.assertEqual(CONTINGENCY_REPORT_DAYS, 2)
		self.assertEqual(str(add_days(getdate("2026-01-01"), CONTINGENCY_REPORT_DAYS)), "2026-01-03")


class TestBox1Filter(unittest.TestCase):
	def test_emirate_boxes_only(self):
		from taxmate.uae_e_invoicing.report.uae_e_invoice_vat_201_reconciliation.uae_e_invoice_vat_201_reconciliation import (
			_is_box1,
		)

		self.assertTrue(_is_box1("1a"))
		self.assertTrue(_is_box1("1g"))
		self.assertFalse(_is_box1("10"))
		self.assertFalse(_is_box1("11"))
		self.assertFalse(_is_box1("2"))


class TestAspContract(unittest.TestCase):
	def test_providers_override_base_contract(self):
		from taxmate.uae_e_invoicing.api_classes.base import BaseAPI
		from taxmate.uae_e_invoicing.api_classes.complyance import ComplyanceAPI

		for cls in (ComplyanceAPI,):
			for method in ("submit_invoice", "get_document_status", "get_document_xml", "get_document_pdf"):
				self.assertIsNot(getattr(cls, method), getattr(BaseAPI, method))


class TestInboundCompany(unittest.TestCase):
	def test_unmatched_buyer_trn_is_not_default_company(self):
		import frappe

		if not getattr(frappe.local, "site", None):
			self.skipTest("needs a site")

		from taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice import _resolve_company

		self.assertIsNone(
			_resolve_company(
				{"AccountingCustomerParty": {"Party": {"PartyTaxScheme": {"CompanyID": "199999999999999"}}}}
			)
		)

	def test_missing_buyer_trn_is_not_default_company(self):
		import frappe

		if not getattr(frappe.local, "site", None):
			self.skipTest("needs a site")

		from taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice import _resolve_company

		self.assertIsNone(_resolve_company({}))
		self.assertIsNone(_resolve_company({"AccountingCustomerParty": {"Party": {}}}))


class TestIssuedOn(unittest.TestCase):
	def test_uses_invoice_posting_date(self):
		from frappe.utils import getdate

		from taxmate.uae_e_invoicing.utils.e_invoice import _invoice_issued_on

		class _Doc:
			def get(self, key, default=None):
				return "2026-01-01" if key == "posting_date" else default

		issued = _invoice_issued_on(_Doc())
		self.assertEqual(str(getdate(issued)), "2026-01-01")


class TestPayloadHasGroupTin(unittest.TestCase):
	def test_party_identification_from_trn(self):
		from taxmate.tests.test_uae_e_invoicing import golden_transaction_data
		from taxmate.uae_e_invoicing.utils.pint_ae import build_payload_from_data

		_uuid, payload = build_payload_from_data(golden_transaction_data())
		ids = payload["AccountingSupplierParty"]["Party"].get("PartyIdentification") or []
		self.assertEqual(ids[0]["ID"]["value"], "1000000000")
		self.assertEqual(
			payload["AccountingSupplierParty"]["Party"]["PartyTaxScheme"]["CompanyID"],
			"100000000000003",
		)
