"""Arabic print keeps bilingual labels and the AED mark.

Run: bench --site taxmate.site run-tests --app taxmate --module taxmate.tests.test_print_language
"""

from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.jinja import get_jenv


def _render(path: str, doc, **extra) -> str:
	frappe.local.lang = "ar"
	return get_jenv().get_template(path).render({"doc": doc, **extra})


class TestArabicPrint(FrappeTestCase):
	def test_payment_receipt_is_bilingual_and_shows_aed(self):
		name = "ACC-PAY-2026-00020"
		if not frappe.db.exists("Payment Entry", name):
			raise unittest.SkipTest(f"{name} is not on this site")
		doc = frappe.get_doc("Payment Entry", name)
		html = _render("templates/print_formats/uae_bilingual_payment.html", doc)
		self.assertIn("سند صرف", html)
		self.assertIn("Payment Voucher", html)
		self.assertIn("Amount / المبلغ", html)
		self.assertIn("Narration / البيان", html)
		self.assertIn("AED", html)
		self.assertIn("د.إ", html)
		self.assertIn("10,920.00", html)
		self.assertIn("Emirates Gold Trading LLC", html)
		self.assertIn("Debit / مدين", html)
		self.assertIn("Total (credit) / إجمالي الدائن", html)
		self.assertNotIn(">10920.0<", html)
		self.assertNotIn(">None<", html)

	def test_payment_print_shows_letterhead_draft_and_deduction(self):
		name = "ACC-PAY-2026-00020"
		if not frappe.db.exists("Payment Entry", name):
			raise unittest.SkipTest(f"{name} is not on this site")
		doc = frappe.get_doc("Payment Entry", name)
		doc.docstatus = 0
		doc.payment_type = "Receive"
		doc.append("deductions", {"account": "Cash - ANJ", "amount": 15, "description": "Bank charge"})
		html = _render(
			"templates/print_formats/uae_bilingual_payment.html",
			doc,
			letter_head="<div>COMPANY LETTERHEAD</div>",
			footer="<div>COMPANY FOOTER</div>",
			no_letterhead=0,
		)
		self.assertIn("سند قبض", html)
		self.assertIn("DRAFT / مسودة", html)
		self.assertIn("COMPANY LETTERHEAD", html)
		self.assertIn("COMPANY FOOTER", html)
		self.assertIn("Deduction / الخصم", html)
		self.assertIn("Bank charge", html)
		self.assertIn("AED 15.00", html)
		hidden = _render(
			"templates/print_formats/uae_bilingual_payment.html",
			doc,
			letter_head="<div>COMPANY LETTERHEAD</div>",
			no_letterhead=1,
		)
		self.assertNotIn("COMPANY LETTERHEAD", hidden)

	def test_tax_invoice_keeps_both_languages_in_arabic_mode(self):
		name = frappe.db.get_value("Sales Invoice", {"docstatus": 1}, "name")
		if not name:
			raise unittest.SkipTest("No submitted Sales Invoice")
		doc = frappe.get_doc("Sales Invoice", name)
		html = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc)
		self.assertIn("Invoice No. / رقم الفاتورة", html)
		self.assertIn("Grand Total / الإجمالي شامل الضريبة", html)
		self.assertIn("AED", html)
		self.assertIn("د.إ", html)
		self.assertNotIn("التاريخ / التاريخ", html)
