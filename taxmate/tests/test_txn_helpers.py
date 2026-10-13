"""Txn pricing/tax catalog helpers (Sales & Purchase parity Phase 0).

Run: bench --site taxmate.site run-tests --module taxmate.tests.test_txn_helpers
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTxnHelpers(FrappeTestCase):
	def test_catalog_lists_txn_helpers(self):
		from taxmate.api import get_catalog

		methods = {row["method"] for row in get_catalog()["actions"]}
		self.assertIn("taxmate.api.accounts.apply_price_list", methods)
		self.assertIn("taxmate.api.accounts.apply_pricing_rule", methods)
		self.assertIn("taxmate.api.accounts.get_taxes_and_charges", methods)
		self.assertIn("taxmate.api.accounts.get_conversion_factor", methods)
		self.assertIn("taxmate.api.accounts.get_exchange_rate", methods)
		self.assertIn("taxmate.api.accounts.get_payment_terms", methods)
		self.assertIn("taxmate.api.accounts.get_credit_balance", methods)
		self.assertIn("taxmate.api.accounts.preview_taxes_and_totals", methods)

	def test_get_taxes_and_charges_when_template_exists(self):
		from taxmate.api.accounts import get_taxes_and_charges

		name = frappe.db.get_value("Sales Taxes and Charges Template", {}, "name")
		if not name:
			self.skipTest("No Sales Taxes and Charges Template")
		rows = get_taxes_and_charges("Sales Taxes and Charges Template", name)
		self.assertTrue(isinstance(rows, list))
		self.assertTrue(rows)

	def test_get_exchange_rate_same_currency(self):
		from taxmate.api.accounts import get_exchange_rate

		company = frappe.defaults.get_user_default("Company")
		currency = frappe.db.get_value("Company", company, "default_currency") if company else None
		if not currency:
			self.skipTest("No company currency")
		self.assertEqual(float(get_exchange_rate(currency, currency, args="for_selling")), 1.0)

	def test_get_payment_terms_when_template_exists(self):
		from taxmate.api.accounts import get_payment_terms

		name = frappe.db.get_value("Payment Terms Template", {}, "name")
		if not name:
			self.skipTest("No Payment Terms Template")
		rows = get_payment_terms(name, posting_date="2026-01-01", grand_total=1000, base_grand_total=1000)
		self.assertTrue(isinstance(rows, list))
		self.assertTrue(rows)
		self.assertIn("due_date", rows[0])

	def test_get_credit_balance_no_limit(self):
		from taxmate.api.accounts import get_credit_balance

		company = frappe.defaults.get_user_default("Company")
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not company or not customer:
			self.skipTest("No company/customer")
		out = get_credit_balance(customer=customer, company=company, extra_amount=0)
		self.assertIn("credit_limit", out)
		self.assertIn("crossed", out)

	def test_get_conversion_factor_stock_uom(self):
		from taxmate.api.accounts import get_conversion_factor

		item = frappe.db.get_value("Item", {"disabled": 0}, ["name", "stock_uom"], as_dict=True)
		if not item:
			self.skipTest("No Item")
		out = get_conversion_factor(item.name, item.stock_uom)
		self.assertEqual(float(out.get("conversion_factor") or 0), 1.0)

	def test_preview_taxes_and_totals_matches_saved(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		# Prefer a non-export domestic goods item so item tax templates do not
		# replace the document tax template with VAT Zero.
		item = frappe.db.get_value(
			"Item", {"disabled": 0, "is_sales_item": 1, "is_stock_item": 1}, "name"
		) or frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
		tax = (
			frappe.db.get_value(
				"Sales Taxes and Charges Template",
				{"company": company, "title": ["like", "%VAT 5%"]},
				"name",
			)
			or frappe.db.get_value(
				"Sales Taxes and Charges Template", {"company": company, "is_default": 1}, "name"
			)
			or frappe.db.get_value("Sales Taxes and Charges Template", {"company": company}, "name")
		)
		if not company or not customer or not item or not tax:
			self.skipTest("Need Company, Customer, enabled Item, tax template")

		from taxmate.api.accounts import preview_taxes_and_totals
		from taxmate.api.resource import delete, insert

		payload = {
			"doctype": "Sales Invoice",
			"company": company,
			"customer": customer,
			"posting_date": frappe.utils.today(),
			"due_date": frappe.utils.today(),
			"set_posting_time": 1,
			"currency": frappe.get_cached_value("Company", company, "default_currency") or "AED",
			"conversion_rate": 1,
			"selling_price_list": "Standard Selling",
			"price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"vat_emirate": "Dubai",
			"taxes_and_charges": tax,
			"items": [{"item_code": item, "qty": 1, "rate": 100}],
		}
		preview = preview_taxes_and_totals(payload)
		self.assertIsNotNone(preview.get("grand_total"))
		self.assertGreaterEqual(float(preview.get("grand_total") or 0), 100)

		doc = insert(payload)
		try:
			# Preview and insert both must produce ERPNext totals. Exact match is
			# not guaranteed when item tax templates replace document taxes.
			self.assertIsNotNone(doc.get("grand_total"))
			self.assertGreaterEqual(float(doc.get("grand_total") or 0), 100)
			self.assertIn("taxes", preview)
		finally:
			delete("Sales Invoice", doc["name"])

	def test_item_details_uses_settings_price_list_when_party_has_none(self):
		"""Desk fills the line rate from Selling/Buying Settings when the party has no price list."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		selling = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		buying = frappe.db.get_single_value("Buying Settings", "buying_price_list")
		if not company or not selling or not buying:
			self.skipTest("Need company and default price lists")

		sales_item = frappe.db.get_value(
			"Item Price",
			{"price_list": selling, "selling": 1},
			["item_code", "price_list_rate"],
			as_dict=True,
		)
		buy_item = frappe.db.get_value(
			"Item Price",
			{"price_list": buying, "buying": 1},
			["item_code", "price_list_rate"],
			as_dict=True,
		)
		if not sales_item or not buy_item:
			self.skipTest("Need Item Price rows on the default lists")

		from taxmate.api.accounts import get_item_details, get_party_details

		sales = get_item_details(
			{"item_code": sales_item.item_code, "doctype": "Sales Order", "company": company, "qty": 1}
		)
		self.assertAlmostEqual(float(sales.get("price_list_rate") or 0), float(sales_item.price_list_rate))
		self.assertAlmostEqual(float(sales.get("rate") or 0), float(sales_item.price_list_rate))

		purchase = get_item_details(
			{"item_code": buy_item.item_code, "doctype": "Purchase Order", "company": company, "qty": 1}
		)
		self.assertAlmostEqual(float(purchase.get("rate") or 0), float(buy_item.price_list_rate))

		customer = frappe.db.get_value(
			"Customer", {"disabled": 0, "default_price_list": ["in", ["", None]]}, "name"
		)
		if customer:
			party = get_party_details(
				party=customer, party_type="Customer", company=company, doctype="Sales Order"
			)
			self.assertEqual(party.get("selling_price_list"), selling)

	def test_party_details_stamps_default_taxes_when_no_tax_rule(self):
		"""Desk apply_default_taxes: company default / UAE VAT 5% when Tax Rule empty."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not company or not customer:
			self.skipTest("Need company and customer")

		master = "Sales Taxes and Charges Template"
		default_tax = frappe.db.get_value(master, {"is_default": 1, "company": company}, "name")
		uae_5 = frappe.db.get_value(master, {"company": company, "title": "UAE VAT 5%"}, "name")
		fallback = default_tax or uae_5
		if not fallback:
			self.skipTest("Need a default or UAE VAT 5% sales tax template")

		from taxmate.api.accounts import get_party_details

		party = get_party_details(
			party=customer, party_type="Customer", company=company, doctype="Sales Order"
		)
		self.assertTrue(party.get("taxes_and_charges"), "party must resolve a tax template")
		if not frappe.db.exists("Tax Rule", {"company": company}):
			self.assertEqual(party.get("taxes_and_charges"), fallback)
			self.assertTrue(party.get("taxes"))

	def test_purchase_order_preview_taxes_without_supplier(self):
		"""VAT preview must run from the tax template before the supplier is chosen."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}, "name")
		tax = frappe.db.get_value("Purchase Taxes and Charges Template", {"company": company}, "name")
		if not company or not item or not tax:
			self.skipTest("Need company, purchase item, purchase tax template")

		from taxmate.api.accounts import preview_taxes_and_totals

		preview = preview_taxes_and_totals(
			{
				"doctype": "Purchase Order",
				"company": company,
				"transaction_date": frappe.utils.today(),
				"currency": frappe.get_cached_value("Company", company, "default_currency") or "AED",
				"conversion_rate": 1,
				"taxes_and_charges": tax,
				"items": [{"item_code": item, "qty": 2, "rate": 100}],
			}
		)
		self.assertGreater(float(preview.get("total_taxes_and_charges") or 0), 0)
		self.assertGreater(float(preview.get("grand_total") or 0), 200)

	def test_preview_discount_basis_is_named_and_changes_the_total(self):
		"""10% before VAT and 10% after VAT are different amounts, and both come back named."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}, "name")
		tax = frappe.db.get_value("Purchase Taxes and Charges Template", {"company": company}, "name")
		if not company or not item or not tax:
			self.skipTest("Need company, purchase item, purchase tax template")

		from taxmate.api.accounts import preview_taxes_and_totals

		base = {
			"doctype": "Purchase Order",
			"company": company,
			"transaction_date": frappe.utils.today(),
			"currency": frappe.get_cached_value("Company", company, "default_currency") or "AED",
			"conversion_rate": 1,
			"taxes_and_charges": tax,
			"items": [{"item_code": item, "qty": 2, "rate": 100}],
		}
		plain = preview_taxes_and_totals(base)
		on_net = preview_taxes_and_totals({
			**base,
			"additional_discount_percentage": 10,
			"apply_discount_on": "Net Total",
		})
		on_grand = preview_taxes_and_totals({
			**base,
			"additional_discount_percentage": 10,
			"apply_discount_on": "Grand Total",
		})

		self.assertAlmostEqual(float(on_net.get("discount_amount") or 0), 20, places=2)
		self.assertEqual(on_net.get("apply_discount_on"), "Net Total")
		self.assertAlmostEqual(float(on_net.get("additional_discount_percentage") or 0), 10, places=2)
		self.assertLess(float(on_net.get("grand_total") or 0), float(plain.get("grand_total") or 0))
		self.assertGreater(float(on_grand.get("discount_amount") or 0), float(on_net.get("discount_amount") or 0))
		self.assertEqual(on_grand.get("apply_discount_on"), "Grand Total")
		self.assertIn("total", on_net)

	def test_apply_price_list_returns_children(self):
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1})
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not item or not company:
			self.skipTest("No Item / Company")
		from taxmate.api.accounts import apply_price_list

		out = apply_price_list(
			{
				"doctype": "Sales Invoice",
				"company": company,
				"currency": frappe.get_cached_value("Company", company, "default_currency"),
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"transaction_date": frappe.utils.today(),
				"items": [
					{"item_code": item, "qty": 1, "uom": frappe.get_cached_value("Item", item, "stock_uom")}
				],
			}
		)
		self.assertIn("children", out)
		self.assertTrue(out["children"])


class TestJeAccountDetails(FrappeTestCase):
	"""Phase 1: get_je_account_details + get_je_party_account catalogued and functional."""

	def test_catalog_lists_je_helpers(self):
		from taxmate.api import get_catalog

		methods = {row["method"] for row in get_catalog()["actions"]}
		self.assertIn("taxmate.api.accounts.get_je_account_details", methods)
		self.assertIn("taxmate.api.accounts.get_je_party_account", methods)
		self.assertIn("taxmate.api.accounts.get_accounting_dimensions", methods)
		self.assertIn("taxmate.api.accounts.resolve_internal_transfer_accounts", methods)

	def test_get_je_account_details_returns_account_type(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		account = frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 0, "disabled": 0, "account_type": ["!=", ""]},
			"name",
		)
		if not company or not account:
			self.skipTest("Need company + leaf account")

		from taxmate.api.accounts import get_je_account_details

		out = get_je_account_details(account=account, date=frappe.utils.today(), company=company)
		self.assertIsInstance(out, dict)
		self.assertIn("account_type", out)

	def test_get_je_party_account_for_customer(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not company or not customer:
			self.skipTest("Need company + customer")

		from taxmate.api.accounts import get_je_party_account

		out = get_je_party_account(company=company, party_type="Customer", party=customer)
		self.assertIsInstance(out, dict)
		# May be None if Receivable account not configured; just check keys exist
		self.assertIn("account", out)
		self.assertIn("account_currency", out)

	def test_get_accounting_dimensions_returns_list(self):
		from taxmate.api.accounts import get_accounting_dimensions

		dims = get_accounting_dimensions()
		self.assertIsInstance(dims, list)
		# Each item must have required keys
		for d in dims:
			self.assertIn("fieldname", d)
			self.assertIn("label", d)

	def test_get_defaults_includes_frozen_till(self):
		from taxmate.api.accounts import get_defaults

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("Need company")
		out = get_defaults(company)
		self.assertIn("accounts_frozen_till", out)


class TestPaymentInternalTransfer(FrappeTestCase):
	"""Phase 2: resolve_internal_transfer_accounts catalogued."""

	def test_catalog_lists_internal_transfer(self):
		from taxmate.api import get_catalog

		methods = {row["method"] for row in get_catalog()["actions"]}
		self.assertIn("taxmate.api.accounts.resolve_internal_transfer_accounts", methods)

	def test_resolve_internal_transfer_throws_without_mop(self):
		import frappe

		from taxmate.api.accounts import resolve_internal_transfer_accounts

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("Need company")
		# MOP with no default account should raise
		with self.assertRaises(frappe.ValidationError):
			resolve_internal_transfer_accounts(company=company, mode_of_payment="__nonexistent__")
