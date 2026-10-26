"""Arabic print language for TaxMate formats.

Run: bench --site taxmate.site run-tests --app taxmate --module taxmate.tests.test_print_language
"""

from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import fmt_money
from frappe.utils.jinja import get_jenv


def _render(path: str, doc, lang: str = "ar", **extra) -> str:
	frappe.local.lang = lang
	# frappe.lang is copied into the Jinja sandbox when the env is built.
	frappe.local.jenv = None
	return get_jenv().get_template(path).render({"doc": doc, **extra})


def _invoice_title_ar(doc) -> str:
	is_return = doc.is_return
	base_total = doc.base_grand_total or doc.grand_total or 0
	buyer_trn = doc.tax_id if doc.doctype == "Sales Invoice" else doc.company_trn
	if doc.doctype == "Purchase Invoice":
		buyer_trn = doc.company_trn
	simplified = (not buyer_trn) and abs(base_total) <= 10000
	if is_return:
		return "إشعار دائن"
	if simplified:
		return "فاتورة ضريبية مبسطة"
	return "فاتورة ضريبية"


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
		self.assertIn("مسودة", html)
		self.assertNotIn("DRAFT", html)
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

	def test_sales_invoice_arabic_print_keeps_the_total(self):
		name = frappe.db.get_value("Sales Invoice", {"docstatus": 1}, "name", order_by="modified desc")
		if not name:
			raise unittest.SkipTest("No submitted Sales Invoice")
		doc = frappe.get_doc("Sales Invoice", name)
		english = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="en")
		arabic = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		figure = fmt_money(doc.grand_total or 0)
		self.assertIn(_invoice_title_ar(doc), arabic)
		self.assertIn('dir="rtl"', arabic)
		self.assertIn("الإجمالي شامل الضريبة", arabic)
		self.assertNotIn("Invoice No.", arabic)
		self.assertNotIn("Grand Total", arabic)
		self.assertIn(doc.name, arabic)
		self.assertIn(doc.name, english)
		self.assertIn(figure, arabic)
		self.assertIn(figure, english)
		self.assertIn("Invoice No. / رقم الفاتورة", english)
		if doc.company_trn:
			self.assertIn(doc.company_trn, arabic)
			self.assertIn(doc.company_trn, english)

		doc.customer_name_in_arabic = "عميل الاختبار"
		named = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("عميل الاختبار", named)

		doc.customer_name_in_arabic = ""
		doc.customer_name = "English Customer LLC"
		fallback = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("English Customer LLC", fallback)

		if doc.items:
			doc.items[0].item_name = "وصف عربي للصنف"
			described = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
			self.assertIn("وصف عربي للصنف", described)
			doc.items[0].item_name = "Cream Biscuits"
			doc.items[0].description = "بسكويت بالقشطة"
			arabic_desc = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
			self.assertIn("بسكويت بالقشطة", arabic_desc)
			doc.items[0].item_name = "Cream Biscuits"
			doc.items[0].description = "Cream Biscuits"
			english_item = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
			self.assertIn("Cream Biscuits", english_item)

		if doc.items:
			doc.items[0].hs_code = "01012100"
			coded = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
			self.assertIn("الرمز المنسق", coded)
			self.assertIn("01012100", coded)
			self.assertNotIn("HS:", coded)
			self.assertNotIn("HS /", coded)

		doc.customer_name_in_arabic = "   "
		doc.customer_name = "English Customer LLC"
		blank_arabic = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("English Customer LLC", blank_arabic)

		doc.is_return = 1
		doc.uae_e_invoice_status = "Accepted"
		doc.uae_credit_note_reason = "GOODS_OR_SERVICES_RETURNED"
		credit = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("إشعار دائن", credit)
		self.assertIn("هذا إشعار دائن", credit)
		self.assertIn(figure, credit)
		self.assertIn("إعادة السلع أو الخدمات", credit)
		self.assertIn("مقبول", credit)
		self.assertNotIn("Credit Note", credit)
		self.assertNotIn("هذه فاتورة ضريبية صادرة", credit)
		self.assertNotIn("GOODS_OR_SERVICES_RETURNED", credit)
		credit_en = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="en")
		self.assertIn("This is a credit note", credit_en)
		self.assertIn("Goods or services returned", credit_en)

	def test_printview_uses_the_arabic_sales_invoice_format(self):
		name = frappe.db.get_value("Sales Invoice", {"docstatus": 1}, "name", order_by="modified desc")
		if not name or not frappe.db.exists("Print Format", "UAE Bilingual Tax Invoice"):
			raise unittest.SkipTest("Sales invoice print format is not on this site")
		frappe.local.lang = "ar"
		frappe.form_dict._lang = "ar"
		html = frappe.get_print(
			"Sales Invoice",
			name,
			"UAE Bilingual Tax Invoice",
			as_pdf=False,
			no_letterhead=1,
		)
		doc = frappe.get_doc("Sales Invoice", name)
		self.assertIn(_invoice_title_ar(doc), html)
		self.assertIn(fmt_money(doc.grand_total or 0), html)
		self.assertIn(doc.name, html)
		self.assertIn('dir="rtl"', html)
		self.assertNotIn("Invoice No.", html)

	def test_purchase_invoice_arabic_print_keeps_the_total(self):
		name = frappe.db.get_value("Purchase Invoice", {"docstatus": 1}, "name", order_by="modified desc")
		if not name:
			raise unittest.SkipTest("No submitted Purchase Invoice")
		doc = frappe.get_doc("Purchase Invoice", name)
		english = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="en")
		arabic = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		figure = fmt_money(doc.grand_total or 0)
		self.assertIn(_invoice_title_ar(doc), arabic)
		self.assertIn('dir="rtl"', arabic)
		self.assertIn("المورد", arabic)
		self.assertNotIn("Invoice No.", arabic)
		self.assertIn(figure, arabic)
		self.assertIn(figure, english)
		self.assertIn(doc.name, arabic)
		doc.supplier_name_in_arabic = "مورد الاختبار"
		named = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("مورد الاختبار", named)
		doc.supplier_name_in_arabic = ""
		doc.supplier_name = "English Supplier LLC"
		fallback = _render("templates/print_formats/uae_bilingual_tax_invoice.html", doc, lang="ar")
		self.assertIn("English Supplier LLC", fallback)

	def test_worksheets_arabic_headings_keep_the_figures(self):
		vat = frappe._dict(
			company="Al Noor Jewellers LLC",
			company_trn="100000000000003",
			period_start="2026-01-01",
			period_end="2026-03-31",
			filing_due_date="2026-04-28",
			boxes=[
				frappe._dict(box_no="1a", legend="Standard rated supplies in Abu Dhabi", amount=46200, vat_amount=2310),
			],
		)
		vat.get_formatted = lambda field: getattr(vat, field)
		vat_en = _render("templates/print_formats/uae_vat_201_worksheet.html", vat, lang="en")
		vat_ar = _render("templates/print_formats/uae_vat_201_worksheet.html", vat, lang="ar")
		self.assertIn("إقرار ضريبة القيمة المضافة", vat_ar)
		self.assertIn('dir="rtl"', vat_ar)
		self.assertNotIn("Worksheet", vat_ar)
		self.assertNotIn("Company /", vat_ar)
		self.assertIn("1a", vat_ar)
		self.assertIn("100000000000003", vat_ar)
		self.assertIn("100000000000003", vat_en)
		self.assertIn(fmt_money(46200), vat_ar)
		self.assertIn(fmt_money(46200), vat_en)
		self.assertIn(fmt_money(2310), vat_ar)

		ct = frappe._dict(
			company="Al Noor Jewellers LLC",
			company_trn="100000000000003",
			period_start="2026-01-01",
			period_end="2026-12-31",
			filing_due_date="2027-09-30",
			regime="Standard",
			revenue=100000,
			expenses=40000,
			accounting_profit=60000,
			taxable_profit=60000,
			tax_payable=5400,
			elect_qfzp=0,
			adjustments=[],
		)
		ct.get_formatted = lambda field: getattr(ct, field)
		ct_en = _render("templates/print_formats/uae_ct_worksheet.html", ct, lang="en")
		ct_ar = _render("templates/print_formats/uae_ct_worksheet.html", ct, lang="ar")
		self.assertIn("ورقة عمل ضريبة الشركات", ct_ar)
		self.assertNotIn("Revenue", ct_ar)
		self.assertNotIn("Tax Payable", ct_ar)
		self.assertIn("100000000000003", ct_ar)
		self.assertIn(fmt_money(5400), ct_ar)
		self.assertIn(fmt_money(5400), ct_en)
		self.assertIn(fmt_money(100000), ct_ar)
		self.assertIn(fmt_money(100000), ct_en)
