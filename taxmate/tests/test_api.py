"""TaxMate accounts API: catalog, resource CRUD, reports, dashboard.

Run: bench --site taxmate.site run-tests --module taxmate.tests.test_api
"""

from __future__ import annotations

import unittest
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from taxmate.api import get_catalog, get_session
from taxmate.api.dashboard import get_home
from taxmate.api.reports import list_reports
from taxmate.api.resource import bulk_delete, delete, get, get_list, get_meta, get_versions, insert, is_allowed_doctype, save


class TestApiAllowlist(unittest.TestCase):
	def test_accounts_doctypes_allowed_hr_denied(self):
		self.assertTrue(is_allowed_doctype("Sales Invoice"))
		self.assertTrue(is_allowed_doctype("Customer"))
		self.assertTrue(is_allowed_doctype("Supplier"))
		self.assertTrue(is_allowed_doctype("Purchase Invoice"))
		self.assertTrue(is_allowed_doctype("Purchase Order"))
		self.assertTrue(is_allowed_doctype("Purchase Receipt"))
		self.assertTrue(is_allowed_doctype("UAE Incoming Invoice"))
		self.assertTrue(is_allowed_doctype("UAE CT Filing Log"))
		self.assertTrue(is_allowed_doctype("UAE ESR Filing"))
		self.assertTrue(is_allowed_doctype("UAE UBO Register"))
		self.assertTrue(is_allowed_doctype("UAE Late Filing Notice"))
		self.assertTrue(is_allowed_doctype("Journal Entry"))
		self.assertTrue(is_allowed_doctype("Account"))
		self.assertTrue(is_allowed_doctype("Warehouse"))
		self.assertTrue(is_allowed_doctype("Buying Settings"))
		self.assertTrue(is_allowed_doctype("ToDo"))
		self.assertFalse(is_allowed_doctype("Employee"))
		self.assertFalse(is_allowed_doctype(""))


class TestApiCatalog(FrappeTestCase):
	def test_catalog_lists_accounts_resources_and_actions(self):
		catalog = get_catalog()
		doctypes = {row["doctype"] for row in catalog["resources"]}
		self.assertIn("Sales Invoice", doctypes)
		self.assertIn("Purchase Invoice", doctypes)
		self.assertIn("Purchase Order", doctypes)
		self.assertIn("Purchase Receipt", doctypes)
		self.assertIn("Payment Entry", doctypes)
		self.assertIn("Journal Entry", doctypes)
		self.assertIn("Customer", doctypes)
		self.assertIn("Supplier", doctypes)
		self.assertIn("Buying Settings", doctypes)
		self.assertIn("Account", doctypes)
		self.assertIn("UAE VAT 201 Filing Log", doctypes)
		self.assertIn("UAE CT Filing Log", doctypes)
		self.assertIn("UAE ESR Filing", doctypes)
		self.assertIn("UAE UBO Register", doctypes)
		self.assertIn("UAE Late Filing Notice", doctypes)
		self.assertIn("UAE Incoming Invoice", doctypes)
		self.assertNotIn("Employee", doctypes)

		methods = {row["method"] for row in catalog["actions"]}
		self.assertIn("taxmate.api.resource.get_list", methods)
		self.assertIn("taxmate.api.resource.get_versions", methods)
		self.assertIn("taxmate.api.resource.bulk_delete", methods)
		self.assertIn("taxmate.api.workflow.submit", methods)
		self.assertIn("taxmate.api.accounts.get_party_details", methods)
		self.assertIn("taxmate.api.accounts.apply_price_list", methods)
		self.assertIn("taxmate.api.accounts.preview_taxes_and_totals", methods)
		self.assertIn("taxmate.api.sales_order.fulfilment_summary", methods)
		self.assertIn("taxmate.api.search.awesome", methods)
		self.assertIn("taxmate.uae_e_invoicing.utils.e_invoice.generate_e_invoice", methods)
		self.assertIn(
			"taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice.create_purchase_invoice",
			methods,
		)
		self.assertIn(
			"taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.get_or_create",
			methods,
		)
		self.assertIn(
			"taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log.generate_filing",
			methods,
		)
		self.assertIn("taxmate.api.accounts.resolve_payment_accounts", methods)
		self.assertIn("taxmate.api.sales_order.linked_documents", methods)
		self.assertIn("taxmate.api.sales_order.make_delivery_note", methods)
		self.assertIn("taxmate.api.sales_order.make_sales_invoice", methods)
		self.assertIn("taxmate.api.sales_order.set_status", methods)
		self.assertIn("taxmate.api.sales_order.make_pick_list", methods)
		self.assertIn("taxmate.api.sales_order.make_material_request", methods)
		self.assertIn("taxmate.api.sales_order.make_work_orders", methods)
		self.assertIn("taxmate.api.delivery_note.make_from_sales_invoice", methods)
		self.assertIn("taxmate.api.quotation.declare_lost", methods)
		self.assertIn("taxmate.api.quotation.make_from_customer", methods)
		self.assertIn("taxmate.api.lead.make_quotation", methods)
		self.assertIn("taxmate.api.supplier_quotation.make_quotation", methods)
		self.assertIn("taxmate.api.material_request.make_supplier_quotation", methods)
		self.assertIn("taxmate.api.accounts.update_items", methods)
		self.assertIn("taxmate.api.accounts.can_update_items", methods)
		self.assertIn("taxmate.api.sales_order.get_work_order_items", methods)
		self.assertIn("taxmate.api.quotation.sales_order_allowed", methods)
		self.assertIn("taxmate.api.purchase_order.update_dropship_received_qty", methods)
		self.assertIn("taxmate.api.purchase_receipt.make_stock_entry", methods)
		self.assertIn("taxmate.api.material_request.make_pick_list", methods)
		self.assertIn("taxmate.api.material_request.raise_work_orders", methods)
		self.assertIn("taxmate.api.material_request.set_status", methods)
		self.assertIn("Opportunity", doctypes)
		self.assertIn("Request for Quotation", doctypes)
		self.assertIn("Shipment", doctypes)
		self.assertIn("Installation Note", doctypes)
		self.assertIn("Delivery Trip", doctypes)
		self.assertIn("Payment Request", doctypes)
		self.assertIn("Subcontracting Order", doctypes)
		self.assertIn("Subcontracting Inward Order", doctypes)
		self.assertIn("taxmate.api.linked_docs.make_opportunity_from_customer", methods)
		self.assertIn("taxmate.api.linked_docs.make_opportunity_from_lead", methods)
		self.assertIn("taxmate.api.linked_docs.make_quotation_from_opportunity", methods)
		self.assertIn("taxmate.api.linked_docs.make_rfq_from_material_request", methods)
		self.assertIn("taxmate.api.linked_docs.make_supplier_rfq", methods)
		self.assertIn("taxmate.api.linked_docs.make_shipment_from_delivery_note", methods)
		self.assertIn("taxmate.api.linked_docs.make_installation_note_from_delivery_note", methods)
		self.assertIn("taxmate.api.linked_docs.make_delivery_trip_from_delivery_note", methods)
		self.assertIn("taxmate.api.linked_docs.make_payment_request", methods)
		self.assertIn("taxmate.api.linked_docs.make_subcontracting_order_from_purchase_order", methods)
		self.assertIn("taxmate.api.linked_docs.make_subcontracting_inward_from_sales_order", methods)
		self.assertIn("taxmate.api.delivery_note.set_status", methods)
		self.assertIn("taxmate.api.purchase_order.make_purchase_receipt", methods)
		self.assertIn("taxmate.api.purchase_order.make_purchase_invoice", methods)
		self.assertIn("taxmate.api.purchase_order.set_status", methods)
		self.assertIn("taxmate.api.purchase_receipt.set_status", methods)
		# Catalogued for SPA DN→SI / PR→PI / item on-hand (Phase 0-3).
		# User: Implement the plan as specified… complete all the to-dos.
		self.assertIn("taxmate.api.delivery_note.make_sales_invoice", methods)
		self.assertIn("taxmate.api.purchase_receipt.make_purchase_invoice", methods)
		self.assertIn("taxmate.api.stock.item_qty", methods)
		self.assertIn("taxmate.api.stock.stock_entry_item_details", methods)
		self.assertIn("taxmate.api.stock.reconciliation_balance", methods)
		self.assertIn("taxmate.api.resource.group_by_count", methods)
		# Phase 0: role-specific dashboard actions catalogued.
		self.assertIn("taxmate.api.owner_dashboard.get_owner_dashboard", methods)
		self.assertIn("taxmate.api.accountant_dashboard.get_accountant_dashboard", methods)
		self.assertIn("taxmate.api.clients_dashboard.get_clients_dashboard", methods)
		self.assertIn("taxmate.api.company.list_company_addresses", methods)
		self.assertIn("taxmate.api.company.upload_company_logo", methods)
		self.assertFalse(any("rest" in row for row in catalog["resources"]))
		self.assertFalse(is_allowed_doctype("User"))
		self.assertFalse(is_allowed_doctype("Data Import"))
		self.assertFalse(is_allowed_doctype("System Settings"))

		reports = {row["report"] for row in catalog["reports"]}
		self.assertIn("General Ledger", reports)
		self.assertIn("UAE VAT 201", reports)

	def test_session_returns_user(self):
		session = get_session()
		self.assertEqual(session["user"], frappe.session.user)
		self.assertIn("company", session)
		self.assertIn("roles", session)
		self.assertTrue(session["roles"])
		# Administrator is app provider and has no TaxMate SPA role.
		if session.get("is_app_provider"):
			self.assertIn(session.get("spa_role"), (None, "owner", "accountant", "clerk", "viewer"))
		else:
			self.assertIn(session.get("spa_role"), ("owner", "accountant", "clerk", "viewer"))
		self.assertIn("language", session)
		self.assertIn("desk_theme", session)
		self.assertIn("lang", session)
		self.assertIn("theme", session)

	def test_update_ui_preferences_maps_to_user(self):
		from taxmate.api.ui_prefs import update_ui_preferences

		user = frappe.session.user
		before = frappe.db.get_value("User", user, ["language", "desk_theme"], as_dict=True)
		try:
			out = update_ui_preferences(language="ar", theme="dark")
			self.assertEqual(out.get("lang"), "ar")
			self.assertEqual(out.get("theme"), "dark")
			self.assertEqual(frappe.db.get_value("User", user, "language"), "ar")
			self.assertEqual(frappe.db.get_value("User", user, "desk_theme"), "Dark")

			out = update_ui_preferences(language="en", theme="system")
			self.assertEqual(out.get("lang"), "en")
			self.assertEqual(out.get("theme"), "system")
			self.assertEqual(frappe.db.get_value("User", user, "desk_theme"), "Automatic")
		finally:
			frappe.db.set_value(
				"User",
				user,
				{
					"language": before.language,
					"desk_theme": before.desk_theme,
				},
				update_modified=False,
			)


class TestApiResource(FrappeTestCase):
	def test_todo_crud(self):
		description = f"tm-api-{uuid.uuid4().hex[:10]}"
		created = insert({"doctype": "ToDo", "description": description, "status": "Open"})
		self.assertTrue(created.get("name"))

		fetched = get("ToDo", created["name"])
		self.assertEqual(fetched["description"], description)

		rows = get_list("ToDo", filters={"name": created["name"]}, fields=["name", "description"])
		self.assertEqual(len(rows), 1)

		fetched["status"] = "Closed"
		saved = save(fetched)
		self.assertEqual(saved["status"], "Closed")

		delete("ToDo", created["name"])
		self.assertFalse(frappe.db.exists("ToDo", created["name"]))


	def test_draft_purchase_invoice_delete_and_bulk(self):
		from taxmate.api.workflow import submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}) or SERVICE_ITEM

		def make_draft(bill_no: str):
			return insert(
				{
					"doctype": "Purchase Invoice",
					"company": company,
					"supplier": supplier,
					"posting_date": "2026-11-20",
					"due_date": "2026-11-20",
					"set_posting_time": 1,
					"currency": "AED",
					"conversion_rate": 1,
					"vat_emirate": "Dubai",
					"update_stock": 0,
					"bill_no": bill_no,
					"bill_date": "2026-11-18",
					"items": [{"item_code": item, "qty": 1, "rate": 10}],
				}
			)

		a = make_draft(f"TM-DEL-{uuid.uuid4().hex[:6]}")
		b = make_draft(f"TM-DEL-{uuid.uuid4().hex[:6]}")
		self.assertEqual(a["docstatus"], 0)
		delete("Purchase Invoice", a["name"])
		self.assertFalse(frappe.db.exists("Purchase Invoice", a["name"]))

		result = bulk_delete("Purchase Invoice", [b["name"]])
		self.assertIn(b["name"], result["deleted"])
		self.assertEqual(result["failed"], [])
		self.assertFalse(frappe.db.exists("Purchase Invoice", b["name"]))

		submitted = make_draft(f"TM-DEL-{uuid.uuid4().hex[:6]}")
		submit({"doctype": "Purchase Invoice", "name": submitted["name"]})
		with self.assertRaises(frappe.ValidationError):
			delete("Purchase Invoice", submitted["name"])
		blocked = bulk_delete("Purchase Invoice", [submitted["name"]])
		self.assertEqual(blocked["deleted"], [])
		self.assertEqual(len(blocked["failed"]), 1)
		self.assertNotIn("Traceback", blocked["failed"][0]["error"])
		self.assertTrue(blocked["failed"][0]["error"])

	def test_bulk_delete_missing_name_uses_server_message(self):
		result = bulk_delete("Supplier", ["TM-NO-SUCH-DOC"])
		self.assertEqual(result["deleted"], [])
		self.assertEqual(len(result["failed"]), 1)
		text = result["failed"][0]["error"]
		self.assertNotIn("Traceback", text)
		self.assertNotIn("LinkExistsError", text)
		self.assertTrue(text)

	def test_denied_doctype_raises(self):
		with self.assertRaises(frappe.PermissionError):
			get_list("Employee")
		self.assertFalse(is_allowed_doctype("Sales Invoice Item"))
		with self.assertRaises(frappe.PermissionError):
			get_list("Sales Invoice Item", parent="Sales Invoice")

	def test_meta_includes_fields(self):
		meta = get_meta("Customer")
		self.assertEqual(meta["name"], "Customer")
		fieldnames = {row["fieldname"] for row in meta["fields"]}
		self.assertIn("customer_name", fieldnames)

	def test_meta_marks_submittable_vouchers(self):
		self.assertFalse(get_meta("ToDo")["is_submittable"])
		self.assertTrue(get_meta("Sales Invoice")["is_submittable"])

	def test_meta_nests_child_table_fields(self):
		meta = get_meta("Sales Invoice")
		items = next(row for row in meta["fields"] if row["fieldname"] == "items")
		self.assertEqual(items["fieldtype"], "Table")
		self.assertEqual(items["options"], "Sales Invoice Item")
		child_names = {row["fieldname"] for row in items["fields"]}
		self.assertIn("item_code", child_names)
		self.assertIn("qty", child_names)

	def test_guest_catalog_requires_login(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.AuthenticationError):
				get_catalog()
			with self.assertRaises(frappe.AuthenticationError):
				get_home()
			with self.assertRaises(frappe.AuthenticationError):
				list_reports()
			from taxmate.api.search import awesome

			with self.assertRaises(frappe.AuthenticationError):
				awesome(text="invoice")
			with self.assertRaises(frappe.AuthenticationError):
				get_list("ToDo")
		finally:
			frappe.set_user("Administrator")

	def test_group_by_count_and_or_filters_count(self):
		from taxmate.api.resource import get_count, group_by_count

		counts = group_by_count("ToDo", current_filters=[], field="status")
		self.assertIsInstance(counts, list)
		n = get_count("ToDo", filters={"status": "Open"}, or_filters=[["status", "=", "Closed"]])
		self.assertGreaterEqual(int(n or 0), 0)

	def test_restricted_user_cannot_list_invoices(self):
		email = f"tm-api-{uuid.uuid4().hex[:8]}@example.com"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "API Restricted",
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_list("Sales Invoice")
		finally:
			frappe.set_user("Administrator")


class TestApiReportsAndHome(FrappeTestCase):
	def test_list_reports_includes_core_books(self):
		reports = {row["report"] for row in list_reports()}
		self.assertIn("Balance Sheet", reports)
		self.assertIn("Trial Balance", reports)
		self.assertIn("Accounts Receivable", reports)
		self.assertIn("Accounts Payable", reports)

	def test_list_reports_labels_follow_language(self):
		"""Catalog labels go through frappe._ so Arabic uses the translation catalogs."""
		from frappe.translate import MERGED_TRANSLATION_KEY

		previous = frappe.local.lang
		try:
			frappe.cache.hdel(MERGED_TRANSLATION_KEY, ["en", "ar"])
			frappe.local.lang = "en"
			en_rows = {row["report"]: row["label"] for row in list_reports()}
			self.assertEqual(en_rows["Balance Sheet"], "Balance Sheet")
			self.assertEqual(en_rows["Profit and Loss Statement"], "Profit and Loss")

			frappe.cache.hdel(MERGED_TRANSLATION_KEY, "ar")
			frappe.local.lang = "ar"
			ar_rows = {row["report"]: row["label"] for row in list_reports()}
			self.assertEqual(ar_rows["Balance Sheet"], "المركز المالي")
			self.assertEqual(ar_rows["Profit and Loss Statement"], "الربح والخسارة")
			self.assertEqual(frappe._("Account"), "الحساب")
			self.assertEqual(frappe._("Currency"), "العملة")
			self.assertEqual(frappe._("Profit and Loss Statement"), "الأرباح والخسائر")
			if "UAE VAT 201" in ar_rows:
				self.assertEqual(ar_rows["UAE VAT 201"], "ضريبة القيمة المضافة 201")
		finally:
			frappe.local.lang = previous

	def test_ledger_label_translates_name_and_keeps_abbreviation(self):
		from frappe.translate import MERGED_TRANSLATION_KEY

		from taxmate.utils.localize import ledger_label, localize_report

		previous = frappe.local.lang
		try:
			frappe.cache.hdel(MERGED_TRANSLATION_KEY, "ar")
			frappe.local.lang = "ar"
			self.assertEqual(ledger_label("Revenue - XSm"), "الإيرادات - XSm")
			self.assertEqual(ledger_label("Main Safe"), "الخزنة الرئيسية")
			self.assertEqual(ledger_label("Sales of same region"), "مبيعات المنطقة نفسها")
			self.assertEqual(ledger_label("Petty Cash - Others"), "عهدة نثرية — أخرى")
			self.assertEqual(ledger_label("Accrued - Salaries"), "مستحق — الرواتب")
			self.assertEqual(ledger_label("1000 - Revenue"), "1000 - Revenue")
			self.assertEqual(ledger_label("Cost Of Goods Sold"), "تكلفة البضاعة المباعة")
			self.assertEqual(ledger_label("Inventory"), "المخزون")
			self.assertEqual(ledger_label("Stock in Hand"), "المخزون المتاح")
			self.assertEqual(ledger_label("Stock In Hand"), "المخزون المتاح")
			self.assertEqual(ledger_label("'إجمالي الإيرادات (دائن)'"), "إجمالي الإيرادات (دائن)")

			result = localize_report(
				"Profit and Loss Statement",
				{
					"columns": [{"label": "Account", "fieldname": "account"}],
					"result": [
						{
							"account": "Revenue - XSm",
							"acc_name": "Revenue",
							"account_name": "1000 - Revenue",
							"parent_account": "Income - XSm",
							"voucher_type": "Sales Invoice",
						},
						{
							"account": "Petty Cash - Others - XSm",
							"acc_name": "Petty Cash - Others",
						},
						{"account": "'إجمالي الإيرادات (دائن)'"},
					],
				},
			)
			row = result["result"][0]
			self.assertEqual(row["account"], "Revenue - XSm")
			self.assertEqual(row["parent_account"], "Income - XSm")
			self.assertEqual(row["voucher_type"], "Sales Invoice")
			self.assertEqual(row["account_name"], "1000 - Revenue")
			self.assertEqual(row["acc_name"], "الإيرادات")
			self.assertEqual(row["account_label"], "الإيرادات - XSm")
			self.assertEqual(result["result"][1]["account"], "Petty Cash - Others - XSm")
			self.assertEqual(result["result"][1]["acc_name"], "عهدة نثرية — أخرى")
			self.assertEqual(result["result"][1]["account_label"], "عهدة نثرية — أخرى - XSm")
			self.assertEqual(result["result"][2]["account"], "'إجمالي الإيرادات (دائن)'")
			self.assertEqual(result["result"][2]["account_label"], "إجمالي الإيرادات (دائن)")
			self.assertEqual(result["report_label"], "الأرباح والخسائر")
			self.assertEqual(result["columns"][0]["label"], "الحساب")
		finally:
			frappe.local.lang = previous

	def test_home_kpis_shape(self):
		home = get_home()
		self.assertIn("kpis", home)
		names = {row["name"] for row in home["kpis"]}
		self.assertIn("Draft Sales Invoices", names)
		for row in home["kpis"]:
			self.assertIsInstance(row["value"], int)

	def test_home_kpis_ignore_form_dict_company(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		frappe.form_dict.company = company
		try:
			home = get_home(company=company)
			self.assertIn("kpis", home)
			for row in home["kpis"]:
				self.assertIsInstance(row["value"], int)
		finally:
			frappe.form_dict.pop("company", None)

	def test_trial_balance_runs(self):
		from taxmate.api.reports import run_report

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")
		if not fiscal_year:
			self.skipTest("No Fiscal Year")
		result = run_report(
			"Trial Balance",
			{
				"company": company,
				"fiscal_year": fiscal_year,
				"from_date": "2026-01-01",
				"to_date": "2026-12-31",
			},
		)
		self.assertIn("result", result)

	def test_profit_and_loss_runs_with_date_range_filters(self):
		from taxmate.api.reports import run_report

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")
		if not fiscal_year:
			self.skipTest("No Fiscal Year")
		result = run_report(
			"Profit and Loss Statement",
			{
				"company": company,
				"filter_based_on": "Date Range",
				"periodicity": "Yearly",
				"from_fiscal_year": fiscal_year,
				"to_fiscal_year": fiscal_year,
				"period_start_date": "2026-01-01",
				"period_end_date": "2026-12-31",
				"accumulated_values": 0,
			},
		)
		self.assertIn("result", result)

	def test_balance_sheet_runs_monthly(self):
		from taxmate.api.reports import run_report

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		fiscal_year = frappe.db.get_value("Fiscal Year", {"disabled": 0}, "name")
		if not fiscal_year:
			self.skipTest("No Fiscal Year")
		result = run_report(
			"Balance Sheet",
			{
				"company": company,
				"filter_based_on": "Date Range",
				"periodicity": "Monthly",
				"from_fiscal_year": fiscal_year,
				"to_fiscal_year": fiscal_year,
				"period_start_date": "2026-01-01",
				"period_end_date": "2026-09-22",
				"accumulated_values": 1,
			},
		)
		self.assertIn("result", result)
		columns = {col.get("fieldname") for col in result.get("columns") or [] if isinstance(col, dict)}
		self.assertTrue(any("jan" in (name or "").lower() or "2026" in (name or "") for name in columns))

	def test_uae_late_filing_status_runs_with_object_filters(self):
		from taxmate.api.reports import run_report

		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		result = run_report("UAE Late Filing Status", {"company": company})
		self.assertIn("result", result)

	def test_run_report_rejects_list_filters(self):
		from taxmate.api.reports import run_report

		with self.assertRaises(frappe.ValidationError):
			run_report("Trial Balance", [["company", "=", "X"]])


class TestApiMastersHappyPath(FrappeTestCase):
	def test_customer_insert_and_party_details(self):
		group = frappe.db.get_single_value("Selling Settings", "customer_group") or frappe.db.get_value(
			"Customer Group", {"is_group": 0}
		)
		territory = frappe.db.get_single_value("Selling Settings", "territory") or frappe.db.get_value(
			"Territory", {"is_group": 0}
		)
		if not group or not territory:
			self.skipTest("Customer Group / Territory not set up")

		name = f"TM API {uuid.uuid4().hex[:8]}"
		created = insert(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Individual",
				"customer_group": group,
				"territory": territory,
			}
		)
		self.assertTrue(frappe.db.exists("Customer", created["name"]))

		from taxmate.api.accounts import get_defaults, get_party_details

		details = get_party_details(party=created["name"], party_type="Customer")
		self.assertTrue(details)
		defaults = get_defaults()
		self.assertIn("company", defaults)

		delete("Customer", created["name"])

	def test_supplier_insert_address_contact(self):
		group = frappe.db.get_single_value("Buying Settings", "supplier_group") or frappe.db.get_value(
			"Supplier Group", {"is_group": 0}
		)
		if not group:
			self.skipTest("Supplier Group not set up")

		name = f"TM SUP {uuid.uuid4().hex[:8]}"
		created = insert(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_type": "Company",
				"supplier_group": group,
			}
		)
		supp_name = created["name"]
		self.assertTrue(frappe.db.exists("Supplier", supp_name))

		addr = insert(
			{
				"doctype": "Address",
				"address_title": name,
				"address_type": "Billing",
				"address_line1": "Street 1",
				"city": "Dubai",
				"state": "Dubai",
				"emirate": "Dubai",
				"country": "United Arab Emirates",
				"links": [{"link_doctype": "Supplier", "link_name": supp_name}],
			}
		)
		addr_doc = frappe.get_doc("Address", addr["name"])
		self.assertTrue(
			any(row.link_doctype == "Supplier" and row.link_name == supp_name for row in addr_doc.links)
		)

		contact = insert(
			{
				"doctype": "Contact",
				"first_name": name,
				"links": [{"link_doctype": "Supplier", "link_name": supp_name}],
			}
		)
		contact_doc = frappe.get_doc("Contact", contact["name"])
		self.assertTrue(
			any(row.link_doctype == "Supplier" and row.link_name == supp_name for row in contact_doc.links)
		)

		fetched = get("Supplier", supp_name)
		fetched["supplier_primary_address"] = addr["name"]
		fetched["supplier_primary_contact"] = contact["name"]
		saved = save(fetched)
		self.assertEqual(saved["supplier_primary_address"], addr["name"])
		self.assertEqual(saved["supplier_primary_contact"], contact["name"])

		frappe.delete_doc("Supplier", supp_name, force=True, ignore_permissions=True)
		frappe.delete_doc("Contact", contact["name"], force=True, ignore_permissions=True)
		frappe.delete_doc("Address", addr["name"], force=True, ignore_permissions=True)

	def test_account_tree_when_company_exists(self):
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No Company")
		from taxmate.api.accounts import get_account_tree

		tree = get_account_tree(company=company)
		self.assertTrue(tree)

	def test_item_details_when_item_exists(self):
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1})
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not item or not company:
			self.skipTest("No Item / Company")
		from taxmate.api.accounts import get_item_details

		details = get_item_details(
			{
				"item_code": item,
				"company": company,
				"doctype": "Sales Invoice",
				"qty": 1,
			}
		)
		self.assertEqual(details.get("item_code") or item, item)
		item_doc = frappe.get_cached_doc("Item", item)
		for field in ("uae_item_type", "hs_code", "sac_code"):
			if item_doc.meta.has_field(field) and item_doc.get(field):
				self.assertEqual(details.get(field), item_doc.get(field))


class TestApiVoucherHappyPath(FrappeTestCase):
	def test_sales_invoice_submit_payment_and_cancel(self):
		from taxmate.tests.uae_prove_fixtures import (
			SERVICE_ITEM,
			WALK_IN,
			_ensure_walk_in,
			require_prove_site,
		)

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))
		_ensure_walk_in()

		from taxmate.api.accounts import get_outstanding_invoices, get_payment_entry
		from taxmate.api.workflow import cancel, submit

		doc = insert(
			{
				"doctype": "Sales Invoice",
				"company": company,
				"customer": WALK_IN,
				"posting_date": "2026-11-15",
				"due_date": "2026-11-15",
				"set_posting_time": 1,
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"vat_emirate": "Dubai",
				"taxes_and_charges": "UAE VAT 5% - TM",
				"items": [
					{
						"item_code": SERVICE_ITEM,
						"qty": 1,
						"rate": 100,
						"uae_item_type": "Service",
						"sac_code": "998311",
					}
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		items = doc.get("items") or []
		self.assertTrue(items)
		self.assertEqual(items[0].get("sac_code"), "998311")

		submitted = submit({"doctype": "Sales Invoice", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)

		from taxmate.api.accounts import make_sales_return

		credit = make_sales_return(doc["name"])
		self.assertTrue(credit.get("is_return"))
		self.assertEqual(credit.get("return_against"), doc["name"])
		self.assertEqual(credit.get("docstatus"), 0)

		outstanding = get_outstanding_invoices(company, "Customer", WALK_IN)
		self.assertTrue(outstanding is None or isinstance(outstanding, list))

		payment = get_payment_entry("Sales Invoice", doc["name"])
		self.assertEqual(payment.get("doctype"), "Payment Entry")
		refs = payment.get("references") or []
		self.assertTrue(refs)
		self.assertEqual(refs[0].get("reference_name"), doc["name"])

		cancelled = cancel("Sales Invoice", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

		if not frappe.get_meta("Sales Invoice").has_field("uae_e_invoice_status"):
			self.skipTest("uae_e_invoice_status custom field missing")
		frappe.db.set_value(
			"Sales Invoice",
			doc["name"],
			"uae_e_invoice_status",
			"Accepted",
			update_modified=False,
		)
		from taxmate.api.workflow import amend

		amended = amend("Sales Invoice", doc["name"])
		self.assertEqual(amended["docstatus"], 0)
		self.assertEqual(amended["amended_from"], doc["name"])
		self.assertFalse(amended.get("uae_e_invoice_status"))

	def test_purchase_invoice_insert_then_submit(self):
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}) or SERVICE_ITEM
		doc = insert(
			{
				"doctype": "Purchase Invoice",
				"company": company,
				"supplier": supplier,
				"posting_date": "2026-11-15",
				"due_date": "2026-11-15",
				"set_posting_time": 1,
				"currency": "AED",
				"conversion_rate": 1,
				"vat_emirate": "Dubai",
				"update_stock": 0,
				"bill_no": "TM-API-BILL",
				"bill_date": "2026-11-10",
				"items": [{"item_code": item, "qty": 1, "rate": 50}],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		self.assertEqual(str(doc.get("bill_date") or ""), "2026-11-10")
		self.assertEqual(doc.get("bill_no"), "TM-API-BILL")
		submitted = submit({"doctype": "Purchase Invoice", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)
		cancelled = cancel("Purchase Invoice", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

	def test_purchase_order_insert_submit_then_make_receipt(self):
		from taxmate.api.purchase_order import make_purchase_receipt
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		if not frappe.db.exists("Supplier", supplier):
			self.skipTest(f"Missing supplier {supplier}")
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}) or SERVICE_ITEM
		doc = insert(
			{
				"doctype": "Purchase Order",
				"company": company,
				"supplier": supplier,
				"transaction_date": "2026-11-15",
				"schedule_date": "2026-11-30",
				"currency": "AED",
				"conversion_rate": 1,
				"buying_price_list": "Standard Buying",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": 50,
						"schedule_date": "2026-11-30",
					}
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		submitted = submit({"doctype": "Purchase Order", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)

		mapped = make_purchase_receipt(submitted["name"])
		self.assertEqual(mapped.get("doctype"), "Purchase Receipt")
		self.assertEqual(int(mapped.get("docstatus") or 0), 0)
		self.assertTrue(mapped.get("items"))
		self.assertTrue(mapped.get("__islocal") or str(mapped.get("name") or "").startswith("new-"))

		from taxmate.api.purchase_order import set_status

		closed = set_status(submitted["name"], "Closed")
		self.assertEqual(closed["status"], "Closed")
		with self.assertRaises(frappe.ValidationError):
			make_purchase_receipt(submitted["name"])
		reopened = set_status(submitted["name"], "Submitted")
		self.assertNotIn(reopened["status"], ("Closed", "On Hold"))
		held = set_status(submitted["name"], "On Hold", reason="Waiting for the supplier")
		self.assertEqual(held["status"], "On Hold")
		with self.assertRaises(frappe.ValidationError):
			make_purchase_receipt(submitted["name"])

		cancelled = cancel("Purchase Order", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

	def test_journal_entry_insert_then_submit(self):
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		leaves = frappe.get_all(
			"Account",
			filters={
				"company": company,
				"is_group": 0,
				"disabled": 0,
				"account_type": ["not in", ["Receivable", "Payable"]],
			},
			pluck="name",
			limit=10,
		)
		if len(leaves) < 2:
			self.skipTest("need two non-party leaf accounts for the company")

		cost_center = frappe.db.get_value("Company", company, "cost_center")
		line = {"cost_center": cost_center} if cost_center else {}
		doc = insert(
			{
				"doctype": "Journal Entry",
				"company": company,
				"posting_date": "2026-11-15",
				"voucher_type": "Journal Entry",
				"user_remark": "TaxMate SPA journal entry write-path test",
				"accounts": [
					{
						**line,
						"account": leaves[0],
						"debit_in_account_currency": 25,
						"credit_in_account_currency": 0,
					},
					{
						**line,
						"account": leaves[1],
						"debit_in_account_currency": 0,
						"credit_in_account_currency": 25,
					},
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		if cost_center:
			for row in doc.get("accounts") or []:
				self.assertEqual(row.get("cost_center"), cost_center)
		submitted = submit({"doctype": "Journal Entry", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)
		cancelled = cancel("Journal Entry", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

	def test_purchase_receipt_insert_then_submit(self):
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		if not frappe.db.exists("Supplier", supplier):
			self.skipTest(f"Missing supplier {supplier}")
		item = frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1}) or SERVICE_ITEM
		warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
		if not warehouse:
			self.skipTest("need a leaf warehouse for the company")
		doc = insert(
			{
				"doctype": "Purchase Receipt",
				"company": company,
				"supplier": supplier,
				"posting_date": "2026-09-15",
				"set_posting_time": 1,
				"set_warehouse": warehouse,
				"currency": "AED",
				"conversion_rate": 1,
				"buying_price_list": "Standard Buying",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": 50,
						"warehouse": warehouse,
					}
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		submitted = submit({"doctype": "Purchase Receipt", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)
		cancelled = cancel("Purchase Receipt", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

	def test_delivery_note_insert_submit_then_make_sales_invoice(self):
		from frappe.utils import cint

		from taxmate.api.delivery_note import make_sales_invoice as make_dn_sales_invoice
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		customer = frappe.db.get_value("Customer", {"disabled": 0})
		if not customer:
			self.skipTest("need a customer")
		# Prefer non-stock so DN submit needs no Bin. User: Implement the plan… complete all the to-dos.
		item = (
			frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1, "is_stock_item": 0})
			or SERVICE_ITEM
		)
		warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
		if not warehouse:
			self.skipTest("need a leaf warehouse for the company")

		if cint(frappe.db.get_value("Item", item, "is_stock_item")):
			supplier = frappe.db.get_value("Supplier", {"disabled": 0})
			if not supplier:
				self.skipTest("need a supplier to seed stock")
			pr = insert(
				{
					"doctype": "Purchase Receipt",
					"company": company,
					"supplier": supplier,
					"posting_date": "2026-09-14",
					"set_posting_time": 1,
					"set_warehouse": warehouse,
					"currency": "AED",
					"conversion_rate": 1,
					"buying_price_list": "Standard Buying",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"items": [{"item_code": item, "qty": 2, "rate": 40, "warehouse": warehouse}],
				}
			)
			submit({"doctype": "Purchase Receipt", "name": pr["name"]})

		doc = insert(
			{
				"doctype": "Delivery Note",
				"company": company,
				"customer": customer,
				"posting_date": "2026-09-15",
				"set_posting_time": 1,
				"set_warehouse": warehouse,
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": 50,
						"warehouse": warehouse,
					}
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		submitted = submit({"doctype": "Delivery Note", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)

		mapped = make_dn_sales_invoice(submitted["name"])
		self.assertEqual(mapped.get("doctype"), "Sales Invoice")
		self.assertTrue(mapped.get("items"))

		si = insert({**mapped, "doctype": "Sales Invoice", "name": None})
		self.assertEqual(si["docstatus"], 0)
		si_sub = submit({"doctype": "Sales Invoice", "name": si["name"]})
		self.assertEqual(si_sub["docstatus"], 1)

		cancel("Sales Invoice", si["name"])
		cancel("Delivery Note", doc["name"])

	def test_purchase_receipt_submit_then_make_purchase_invoice(self):
		from taxmate.api.purchase_receipt import make_purchase_invoice as make_pr_pi
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		if not frappe.db.exists("Supplier", supplier):
			self.skipTest(f"Missing supplier {supplier}")
		item = (
			frappe.db.get_value("Item", {"disabled": 0, "is_purchase_item": 1, "is_stock_item": 1})
			or SERVICE_ITEM
		)
		warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
		if not warehouse:
			self.skipTest("need a leaf warehouse for the company")

		doc = insert(
			{
				"doctype": "Purchase Receipt",
				"company": company,
				"supplier": supplier,
				"posting_date": "2026-09-16",
				"set_posting_time": 1,
				"set_warehouse": warehouse,
				"currency": "AED",
				"conversion_rate": 1,
				"buying_price_list": "Standard Buying",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"items": [{"item_code": item, "qty": 1, "rate": 40, "warehouse": warehouse}],
			}
		)
		submitted = submit({"doctype": "Purchase Receipt", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)
		mapped = make_pr_pi(submitted["name"])
		self.assertEqual(mapped.get("doctype"), "Purchase Invoice")
		self.assertTrue(mapped.get("items"))
		cancel("Purchase Receipt", doc["name"])

	def test_draft_purchase_invoice_from_incoming(self):
		import json

		from taxmate.tests.uae_prove_fixtures import require_prove_site
		from taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice import (
			create_purchase_invoice,
		)

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		supplier = "Desert Supplies LLC"
		incoming = insert(
			{
				"doctype": "UAE Incoming Invoice",
				"company": company,
				"status": "Received",
				"asp_document_id": f"tm-in-{uuid.uuid4().hex[:12]}",
				"issue_date": "2026-11-15",
				"currency": "AED",
				"supplier_name": supplier,
				"total_amount": 105,
				"tax_amount": 5,
				"payload": json.dumps(
					{
						"ID": "SUP-BILL-1",
						"InvoiceLine": [
							{
								"Item": {"Name": "Received service"},
								"InvoicedQuantity": {"value": 1, "unitCode": "Nos"},
								"Price": {"PriceAmount": {"value": 100}},
								"LineExtensionAmount": {"value": 100},
							}
						],
						"TaxTotal": [{"TaxAmount": {"value": 5}}],
					}
				),
			}
		)
		invoice_name = create_purchase_invoice(incoming["name"])
		self.assertTrue(frappe.db.exists("Purchase Invoice", invoice_name))
		refreshed = get("UAE Incoming Invoice", incoming["name"])
		self.assertEqual(refreshed["status"], "Drafted")
		self.assertEqual(refreshed["purchase_invoice"], invoice_name)
		frappe.delete_doc("Purchase Invoice", invoice_name, force=True)
		frappe.delete_doc("UAE Incoming Invoice", incoming["name"], force=True)


class TestApiSearch(FrappeTestCase):
	def test_awesome_search_returns_wave1_pages(self):
		from taxmate.api.search import awesome

		result = awesome(text="invoice", limit=10)
		self.assertEqual(result["query"], "invoice")
		self.assertTrue(result["groups"])
		routes = [hit["route"] for group in result["groups"] for hit in group["results"]]
		self.assertTrue(any(route.startswith("/invoices") for route in routes))
		self.assertFalse(any(route.startswith("/app/") for route in routes))


class TestSalesOrderApi(FrappeTestCase):
	def test_fulfilment_summary_shape(self):
		from taxmate.api.sales_order import fulfilment_summary

		summary = fulfilment_summary()
		for key in (
			"committed",
			"delivered_value",
			"billed_value",
			"unbilled_delivered",
			"open_count",
			"overdue_count",
		):
			self.assertIn(key, summary)

	def test_sales_order_insert_then_submit_sets_status(self):
		from taxmate.tests.uae_prove_fixtures import (
			SERVICE_ITEM,
			WALK_IN,
			_ensure_walk_in,
			require_prove_site,
		)

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))
		_ensure_walk_in()

		from taxmate.api.workflow import cancel, submit

		doc = insert(
			{
				"doctype": "Sales Order",
				"company": company,
				"customer": WALK_IN,
				"order_type": "Sales",
				"transaction_date": "2026-11-15",
				"delivery_date": "2026-11-30",
				# Place of Supply: the Desk fetch_from does not fire on a
				# server-side insert, and the prove company has no Address to
				# resolve it from, so set it the way an operator would.
				"vat_emirate": "Dubai",
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"taxes_and_charges": "UAE VAT 5% - TM",
				"items": [
					{
						"item_code": SERVICE_ITEM,
						"qty": 1,
						"rate": 100,
						"delivery_date": "2026-11-30",
					}
				],
			}
		)
		self.assertEqual(doc["docstatus"], 0)
		self.assertEqual(doc["status"], "Draft")

		submitted = submit({"doctype": "Sales Order", "name": doc["name"]})
		self.assertEqual(submitted["docstatus"], 1)
		self.assertNotEqual(submitted["status"], "Draft")

		cancelled = cancel("Sales Order", doc["name"])
		self.assertEqual(cancelled["docstatus"], 2)

	def test_get_or_create_vat_201(self):
		from taxmate.tests.uae_prove_fixtures import require_prove_site
		from taxmate.uae_vat.doctype.uae_vat_201_filing_log.uae_vat_201_filing_log import get_or_create

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))

		period_start = "2097-04-01"
		period_end = "2097-06-30"
		try:
			name = get_or_create(company, period_start, period_end)
		except frappe.ValidationError as exc:
			self.skipTest(str(exc))

		self.assertTrue(name)
		fetched = get("UAE VAT 201 Filing Log", name)
		self.assertEqual(fetched["docstatus"], 0)
		self.assertEqual(str(fetched["period_start"]), period_start)
		self.assertEqual(get_or_create(company, period_start, period_end), name)


class TestPhase1BankingMasters(FrappeTestCase):
	"""Phase 1: Bank Account and Mode of Payment list/get via catalog resource API."""

	def test_mode_of_payment_list(self):
		"""get_list on Mode of Payment returns rows with expected fields."""
		rows = get_list("Mode of Payment", fields=["name", "type", "enabled"], limit_page_length=5)
		# Every ERPNext install has at least one MoP (Cash).
		if not rows:
			self.skipTest("No Mode of Payment fixtures on this site")
		for row in rows:
			self.assertIn("name", row)
			self.assertIn("type", row)

	def test_mode_of_payment_get(self):
		"""get on first Mode of Payment returns the expected fields."""
		rows = get_list("Mode of Payment", fields=["name"], limit_page_length=1)
		if not rows:
			self.skipTest("No Mode of Payment fixtures on this site")
		name = rows[0]["name"]
		doc = get("Mode of Payment", name)
		self.assertEqual(doc["name"], name)
		self.assertIn("type", doc)

	def test_bank_account_list_allowed(self):
		"""Bank Account is an allowed catalog doctype."""
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Bank Account"))

	def test_bank_account_insert_skiptest_if_no_company(self):
		"""Insert a Bank Account; skip if no company, bank, or GL account available."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company available for bank account test")

		# Bank Account autoname requires a bank record.
		bank = frappe.db.get_value("Bank", {}, "name")
		if not bank:
			self.skipTest("No Bank fixture on this site")

		# A GL account of type Bank not already linked to another Bank Account is needed.
		used_accounts = frappe.db.get_all("Bank Account", filters={"company": company}, pluck="account")
		gl_account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_type": "Bank",
				"is_group": 0,
				"name": ["not in", used_accounts or [""]],
			},
			"name",
		)
		if not gl_account:
			self.skipTest("No unused Bank-type GL account for company")

		uid = uuid.uuid4().hex[:8]
		doc = insert(
			{
				"doctype": "Bank Account",
				"account_name": f"TM Test Bank {uid}",
				"company": company,
				"bank": bank,
				"account": gl_account,
				"is_company_account": 1,
			}
		)
		self.assertTrue(doc.get("name"))
		self.assertEqual(doc.get("company"), company)

		fetched = get("Bank Account", doc["name"])
		self.assertEqual(fetched["account_name"], f"TM Test Bank {uid}")

		frappe.delete_doc("Bank Account", doc["name"], force=True)


class TestPhase2PaymentTermsTemplate(FrappeTestCase):
	"""Phase 2: Payment Terms Template insert with terms rows."""

	def test_payment_terms_template_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Payment Terms Template"))

	def test_payment_terms_template_insert_with_rows(self):
		"""Insert a PTT with two term rows; verify child rows saved.

		The `payment_term` column is a Link to the "Payment Term" master which
		must exist independently.  The terms child table only requires
		`invoice_portion` and `due_date_based_on` — the link is optional.
		"""
		uid = uuid.uuid4().hex[:8]
		# Reuse an existing Payment Term master if available, else leave blank.
		existing_pt = frappe.db.get_value("Payment Term", {}, "name")
		doc = insert(
			{
				"doctype": "Payment Terms Template",
				"template_name": f"TM Net 30 {uid}",
				"terms": [
					{
						"payment_term": existing_pt or "",
						"due_date_based_on": "Day(s) after invoice date",
						"invoice_portion": 30,
						"credit_days": 0,
					},
					{
						"payment_term": existing_pt or "",
						"due_date_based_on": "Day(s) after invoice date",
						"invoice_portion": 70,
						"credit_days": 30,
					},
				],
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Payment Terms Template", doc["name"])
		self.assertEqual(fetched["template_name"], f"TM Net 30 {uid}")
		terms = fetched.get("terms", [])
		self.assertEqual(len(terms), 2)
		total_portion = sum(float(r["invoice_portion"]) for r in terms)
		self.assertAlmostEqual(total_portion, 100.0)
		frappe.delete_doc("Payment Terms Template", doc["name"], force=True)


class TestPhase3PriceListAndItemPrice(FrappeTestCase):
	"""Phase 3: Price List insert; Item Price via catalog."""

	def test_price_list_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Price List"))

	def test_price_list_insert(self):
		"""Insert a selling price list and verify it is gettable."""
		uid = uuid.uuid4().hex[:8]
		doc = insert(
			{
				"doctype": "Price List",
				"price_list_name": f"TM Selling {uid}",
				"currency": "AED",
				"selling": 1,
				"buying": 0,
				"enabled": 1,
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Price List", doc["name"])
		self.assertEqual(fetched["currency"], "AED")
		self.assertEqual(fetched["selling"], 1)
		frappe.delete_doc("Price List", doc["name"], force=True)

	def test_item_price_insert_for_price_list(self):
		"""Insert an Item Price against the existing Standard Selling price list."""
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
		if not item:
			self.skipTest("No sales item available")
		pl = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
		if not pl:
			self.skipTest("No enabled selling price list")
		uuid.uuid4().hex[:8]
		doc = insert(
			{
				"doctype": "Item Price",
				"item_code": item,
				"price_list": pl,
				"price_list_rate": 99.5,
				"selling": 1,
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Item Price", doc["name"])
		self.assertAlmostEqual(float(fetched["price_list_rate"]), 99.5)
		frappe.delete_doc("Item Price", doc["name"], force=True)


class TestPhase4CreditLimits(FrappeTestCase):
	"""Phase 4: Customer credit_limits child table saved via insert/save."""

	def test_customer_credit_limit_insert(self):
		"""Insert a customer with a credit limit row and verify it persists."""
		company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
		if not company:
			self.skipTest("No company for credit limit test")
		uid = uuid.uuid4().hex[:8]
		doc = insert(
			{
				"doctype": "Customer",
				"customer_name": f"TM CL Test {uid}",
				"customer_type": "Company",
				"credit_limits": [
					{
						"company": company,
						"credit_limit": 50000,
						"bypass_credit_limit_check": 0,
					}
				],
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Customer", doc["name"])
		limits = fetched.get("credit_limits", [])
		self.assertTrue(len(limits) > 0, "credit_limits not saved")
		self.assertAlmostEqual(float(limits[0]["credit_limit"]), 50000)
		frappe.delete_doc("Customer", doc["name"], force=True)


class TestPhase5MultiUOM(FrappeTestCase):
	"""Phase 5: UOM conversion rows saved on Item."""

	def test_item_uom_conversion_insert(self):
		"""Insert a stock item with a UOM conversion row (Box = 12 Nos)."""
		uid = uuid.uuid4().hex[:8]
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		doc = insert(
			{
				"doctype": "Item",
				"item_code": f"TM-UOM-{uid}",
				"item_name": f"TM UOM Test {uid}",
				"item_group": group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"uoms": [
					{"uom": "Nos", "conversion_factor": 1},
					{"uom": "Box", "conversion_factor": 12},
				],
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Item", doc["name"])
		uom_rows = fetched.get("uoms", [])
		uom_names = [r["uom"] for r in uom_rows]
		self.assertIn("Box", uom_names)
		box_row = next((r for r in uom_rows if r["uom"] == "Box"), None)
		self.assertIsNotNone(box_row)
		self.assertAlmostEqual(float(box_row["conversion_factor"]), 12)
		frappe.delete_doc("Item", doc["name"], force=True)


class TestPhase6SerialBatchOnItem(FrappeTestCase):
	"""Phase 6: has_serial_no / has_batch_no flags saved on Item."""

	def test_item_serial_no_flag_insert(self):
		"""Insert a serialised stock item and verify has_serial_no=1."""
		uid = uuid.uuid4().hex[:8]
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		doc = insert(
			{
				"doctype": "Item",
				"item_code": f"TM-SN-{uid}",
				"item_name": f"TM Serial Test {uid}",
				"item_group": group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_serial_no": 1,
				"serial_no_series": f"SN-TM-{uid}-.####",
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Item", doc["name"])
		self.assertEqual(int(fetched.get("has_serial_no", 0)), 1)
		frappe.delete_doc("Item", doc["name"], force=True)

	def test_item_batch_flag_insert(self):
		"""Insert a batched stock item and verify has_batch_no=1."""
		uid = uuid.uuid4().hex[:8]
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		doc = insert(
			{
				"doctype": "Item",
				"item_code": f"TM-BN-{uid}",
				"item_name": f"TM Batch Test {uid}",
				"item_group": group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
				"create_new_batch": 1,
				"batch_number_series": f"BN-TM-{uid}-.####",
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Item", doc["name"])
		self.assertEqual(int(fetched.get("has_batch_no", 0)), 1)
		frappe.delete_doc("Item", doc["name"], force=True)


class TestPhase7SerialBatchMasters(FrappeTestCase):
	"""Phase 7: Serial No and Batch are catalogued and listable."""

	def test_serial_no_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Serial No"))

	def test_batch_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Batch"))

	def test_get_versions_requires_read_and_returns_shape(self):
		"""History API checks source-doc permission and returns a stable shape."""
		customer = frappe.get_all("Customer", pluck="name", limit=1)
		if not customer:
			self.skipTest("No Customer")
		name = customer[0]
		out = get_versions("Customer", name, limit=5)
		self.assertIn("track_changes", out)
		self.assertIn("versions", out)
		self.assertIn("created_by", out)
		self.assertIn("created_on", out)
		self.assertIsInstance(out["versions"], list)
		# Employee is outside the TaxMate catalog (see is_allowed_doctype).
		with self.assertRaises(frappe.PermissionError):
			get_versions("Employee", "x")

	def test_serial_no_get_list(self):
		rows = get_list("Serial No", fields=["name", "item_code"], limit_page_length=5, filters=[])
		self.assertIsInstance(rows, list)

	def test_batch_get_list(self):
		rows = get_list("Batch", fields=["name", "item"], limit_page_length=5, filters=[])
		self.assertIsInstance(rows, list)


class TestPhase8LandedCostVoucher(FrappeTestCase):
	"""Phase 8: Landed Cost Voucher is catalogued and insertable."""

	def test_lcv_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Landed Cost Voucher"))

	def test_lcv_get_list(self):
		# LCV has total_taxes_and_charges, not grand_total (SPA list uses this field).
		rows = get_list(
			"Landed Cost Voucher",
			fields=["name", "posting_date", "total_taxes_and_charges", "docstatus"],
			limit_page_length=5,
			filters=[],
		)
		self.assertIsInstance(rows, list)


class TestPhase9PricingRule(FrappeTestCase):
	"""Phase 9: Pricing Rule is catalogued and insertable."""

	def test_pricing_rule_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Pricing Rule"))

	def test_pricing_rule_get_list(self):
		rows = get_list(
			"Pricing Rule", fields=["name", "title", "apply_on", "disable"], limit_page_length=5, filters=[]
		)
		self.assertIsInstance(rows, list)

	def test_pricing_rule_insert(self):
		"""Insert a discount-on-item pricing rule and verify it is retrievable."""
		uid = uuid.uuid4().hex[:8]
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
		if not item:
			self.skipTest("No sales item available")
		doc = insert(
			{
				"doctype": "Pricing Rule",
				"title": f"TM PR Test {uid}",
				"apply_on": "Item Code",
				"price_or_product_discount": "Price",
				"selling": 1,
				"buying": 0,
				"rate_or_discount": "Discount Percentage",
				"discount_percentage": 10,
				"items": [{"item_code": item}],
				"min_qty": 0,
				"max_qty": 0,
				"priority": 1,
			}
		)
		self.assertTrue(doc.get("name"))
		fetched = get("Pricing Rule", doc["name"])
		self.assertAlmostEqual(float(fetched.get("discount_percentage", 0)), 10)
		frappe.delete_doc("Pricing Rule", doc["name"], force=True)


class TestPhase10PartyGeoMasters(FrappeTestCase):
	"""Phase 10: Customer Group, Supplier Group, Territory are catalogued."""

	def test_customer_group_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Customer Group"))

	def test_supplier_group_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Supplier Group"))

	def test_territory_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Territory"))

	def test_customer_group_get_list(self):
		rows = get_list(
			"Customer Group",
			fields=["name", "is_group", "parent_customer_group"],
			limit_page_length=20,
			filters=[],
		)
		self.assertIsInstance(rows, list)

	def test_supplier_group_get_list(self):
		rows = get_list(
			"Supplier Group",
			fields=["name", "is_group", "parent_supplier_group"],
			limit_page_length=20,
			filters=[],
		)
		self.assertIsInstance(rows, list)

	def test_territory_get_list(self):
		rows = get_list(
			"Territory", fields=["name", "is_group", "parent_territory"], limit_page_length=20, filters=[]
		)
		self.assertIsInstance(rows, list)


class TestPhase11BankReconciliation(FrappeTestCase):
	"""Phase 14: bank_reconciliation catalogued methods."""

	def test_get_uncleared_transactions_catalogued(self):
		from taxmate.api import get_catalog

		catalog = get_catalog()
		methods = {a["name"] for a in catalog.get("actions", [])}
		self.assertIn("get_uncleared_transactions", methods)

	def test_mark_cleared_catalogued(self):
		from taxmate.api import get_catalog

		catalog = get_catalog()
		methods = {a["name"] for a in catalog.get("actions", [])}
		self.assertIn("mark_cleared", methods)

	def test_get_uncleared_requires_valid_bank_account(self):
		"""Calling with a non-existent bank account returns empty list (no bank account found)."""
		from taxmate.api.bank_reconciliation import get_uncleared_transactions

		result = get_uncleared_transactions("__no_such_bank__")
		self.assertIsInstance(result, list)

	def test_uncleared_for_a_real_bank_does_not_query_the_line_clearance_date(self):
		"""Journal lines have no clearance_date. The parent Journal Entry does."""
		banks = frappe.get_all("Bank Account", pluck="name", limit=1)
		if not banks:
			return
		from taxmate.api.bank_reconciliation import get_uncleared_transactions

		rows = get_uncleared_transactions(banks[0], "2026-09-07", "2026-09-30")
		self.assertIsInstance(rows, list)
		for row in rows:
			self.assertIn(row["doctype"], ("Payment Entry", "Journal Entry"))

	def test_mark_cleared_rejects_unknown_doctype(self):
		import frappe

		from taxmate.api.bank_reconciliation import mark_cleared

		with self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
			mark_cleared("Unknown Doctype", "__name__", "2024-01-01")

	def test_tax_category_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Tax Category"))

	def test_item_tax_template_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Item Tax Template"))
		self.assertTrue(is_allowed_doctype("Item Attribute"))
		self.assertTrue(is_allowed_doctype("Location"))

	def test_fiscal_year_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Fiscal Year"))

	def test_terms_and_conditions_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Terms and Conditions"))


class TestPhase16SupplierQuotation(FrappeTestCase):
	"""Phase 16: Supplier Quotation catalogued and API."""

	def test_supplier_quotation_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("Supplier Quotation"))

	def test_supplier_quotation_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list(
			"Supplier Quotation", fields=["name", "supplier", "status"], limit_page_length=5, filters=[]
		)
		self.assertIsInstance(rows, list)

	def test_make_supplier_quotation_po_catalogued(self):
		from taxmate.api import get_catalog

		catalog = get_catalog()
		methods = {a["name"] for a in catalog.get("actions", [])}
		self.assertIn("make_supplier_quotation_po", methods)


class TestPhase18BomWorkOrder(FrappeTestCase):
	"""Phase 18: BOM and Work Order lifted from denied search."""

	def test_bom_not_denied(self):
		from taxmate.search import DENIED_SEARCH_DOCTYPES

		self.assertNotIn("BOM", DENIED_SEARCH_DOCTYPES)

	def test_work_order_not_denied(self):
		from taxmate.search import DENIED_SEARCH_DOCTYPES

		self.assertNotIn("Work Order", DENIED_SEARCH_DOCTYPES)

	def test_bom_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list("BOM", fields=["name", "item"], limit_page_length=5, filters=[])
		self.assertIsInstance(rows, list)

	def test_work_order_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list(
			"Work Order", fields=["name", "production_item", "status"], limit_page_length=5, filters=[]
		)
		self.assertIsInstance(rows, list)


class TestPhase21Lead(FrappeTestCase):
	"""Phase 21: Lead lifted from denied search; convert_to_customer catalogued."""

	def test_lead_not_denied(self):
		from taxmate.search import DENIED_SEARCH_DOCTYPES

		self.assertNotIn("Lead", DENIED_SEARCH_DOCTYPES)

	def test_lead_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list("Lead", fields=["name", "lead_name", "status"], limit_page_length=5, filters=[])
		self.assertIsInstance(rows, list)

	def test_convert_lead_to_customer_catalogued(self):
		from taxmate.api import get_catalog

		catalog = get_catalog()
		methods = {a["name"] for a in catalog.get("actions", [])}
		self.assertIn("convert_lead_to_customer", methods)


class TestPhase22UaeCompliance(FrappeTestCase):
	"""Phase 22: UAE compliance DocTypes catalogued and searchable."""

	def test_uae_related_party_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("UAE Related Party"))

	def test_uae_vat_group_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("UAE VAT Group"))

	def test_uae_bad_debt_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("UAE Bad Debt Relief"))

	def test_uae_customs_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("UAE Customs Declaration"))

	def test_uae_capital_goods_allowed(self):
		from taxmate.api.resource import is_allowed_doctype

		self.assertTrue(is_allowed_doctype("UAE Capital Goods Adjustment"))

	def test_uae_related_party_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list(
			"UAE Related Party", fields=["name", "company", "party"], limit_page_length=5, filters=[]
		)
		self.assertIsInstance(rows, list)

	def test_uae_vat_group_get_list(self):
		from taxmate.api.resource import get_list

		rows = get_list(
			"UAE VAT Group", fields=["name", "representative_company"], limit_page_length=5, filters=[]
		)
		self.assertIsInstance(rows, list)


class TestPosNextSeed(FrappeTestCase):
	"""POS Next needs a POS Profile with the session user on applicable_for_users."""

	def test_ensure_pos_next_creates_profile_for_sourav(self):
		from taxmate.setup.seed_books import COMPANY_NAME, POS_PROFILE_NAME, _ensure_pos_next

		company = COMPANY_NAME
		if not frappe.db.exists("Company", company):
			self.skipTest("Ascra Technology LLP not seeded on this site")
		abbr = frappe.db.get_value("Company", company, "abbr")
		name = _ensure_pos_next({"company": company, "abbr": abbr})
		self.assertEqual(name, POS_PROFILE_NAME)
		self.assertTrue(frappe.db.exists("POS Profile", POS_PROFILE_NAME))
		users = frappe.get_all(
			"POS Profile User",
			filters={"parent": POS_PROFILE_NAME},
			pluck="user",
		)
		self.assertIn("sourav@ascratech.com", users)
		payments = frappe.get_all(
			"POS Payment Method",
			filters={"parent": POS_PROFILE_NAME},
			pluck="mode_of_payment",
		)
		self.assertIn("Cash", payments)

	def test_new_sales_item_is_listed_on_pos(self):
		from taxmate.setup.seed_books import COMPANY_NAME, POS_PROFILE_NAME, _ensure_pos_next

		company = COMPANY_NAME
		if not frappe.db.exists("Company", company):
			self.skipTest("Ascra Technology LLP not seeded on this site")
		if not frappe.get_meta("Item").has_field("custom_company"):
			self.skipTest("POS Next Item.custom_company is not installed")
		abbr = frappe.db.get_value("Company", company, "abbr")
		_ensure_pos_next({"company": company, "abbr": abbr})
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		code = f"TM-POS-{uuid.uuid4().hex[:8]}"
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"stock_uom": "Nos",
				"is_sales_item": 1,
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Item", code, force=1, ignore_permissions=True))
		self.assertEqual(doc.custom_company, company)
		from pos_next.api.items import get_items

		rows = get_items(POS_PROFILE_NAME, search_term=code, limit=5)
		self.assertIn(code, [row["item_code"] for row in rows])

	def test_assign_company_prefers_item_default(self):
		from unittest.mock import patch

		from taxmate.uae_vat.overrides.item import assign_company

		if not frappe.get_meta("Item").has_field("custom_company"):
			self.skipTest("POS Next Item.custom_company is not installed")
		company = frappe.db.get_value("Company", {}, "name")
		self.assertTrue(company)
		doc = frappe._dict(
			meta=frappe.get_meta("Item"),
			custom_company=None,
			item_defaults=[frappe._dict(company=company)],
		)
		with patch("frappe.defaults.get_user_default", return_value="Missing Company"):
			assign_company(doc)
		self.assertEqual(doc.custom_company, company)


class TestCompanySettingsWrite(FrappeTestCase):
	"""SPA Company Settings uses resource.save with a full Company doc."""

	def test_company_save_updates_contact(self):
		company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
			"Company", {"country": "United Arab Emirates"}, "name"
		)
		self.assertTrue(company)
		doc = get("Company", company)
		phone = doc.get("phone_no") or ""
		new_phone = (phone + "1")[-20:] if phone else "+971500000001"
		doc["phone_no"] = new_phone
		saved = save(doc)
		self.assertEqual(saved.get("phone_no"), new_phone)

	def test_company_save_frozen_date_and_vat_frequency(self):
		from taxmate.api.company import list_company_addresses

		company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
			"Company", {"country": "United Arab Emirates"}, "name"
		)
		self.assertTrue(company)
		doc = get("Company", company)
		doc["accounts_frozen_till_date"] = "2026-01-15"
		if "taxmate_vat_filing_frequency" in (doc or {}) or frappe.get_meta("Company").has_field(
			"taxmate_vat_filing_frequency"
		):
			doc["taxmate_vat_filing_frequency"] = "Quarterly"
		saved = save(doc)
		self.assertEqual(str(saved.get("accounts_frozen_till_date") or ""), "2026-01-15")
		if frappe.get_meta("Company").has_field("taxmate_vat_filing_frequency"):
			self.assertEqual(saved.get("taxmate_vat_filing_frequency"), "Quarterly")
		addrs = list_company_addresses(company)
		self.assertIsInstance(addrs, list)

class TestUaeTaxSettingsApi(FrappeTestCase):
	"""SPA E-Invoice ASP page: get/save without leaking password values."""

	def test_catalog_lists_tax_settings_actions(self):
		from taxmate.api import get_catalog

		methods = {row["method"] for row in get_catalog()["actions"]}
		self.assertIn("taxmate.api.tax_settings.get_uae_tax_settings", methods)
		self.assertIn("taxmate.api.tax_settings.save_uae_tax_settings", methods)

	def test_get_and_save_public_fields_without_secrets(self):
		from taxmate.api.tax_settings import get_uae_tax_settings, save_uae_tax_settings

		if not frappe.db.exists("DocType", "UAE Tax Settings"):
			self.skipTest("UAE Tax Settings missing")
		before = get_uae_tax_settings()
		self.assertNotIn("client_secret", before)
		self.assertNotIn("auth_key", before)
		self.assertNotIn("webhook_secret", before)
		self.assertIn("has_client_secret", before)
		old_sla = before.get("sla_days") or 14
		new_sla = 13 if int(old_sla) == 14 else 14
		source = before.get("participant_id") or "taxmate:1.0"
		if ":" not in str(source):
			source = "taxmate:1.0"
		saved = save_uae_tax_settings(
			{"sla_days": new_sla, "participant_id": source, "asp_provider": "Complyance"}
		)
		self.assertEqual(int(saved.get("sla_days")), new_sla)
		self.assertEqual(saved.get("asp_provider"), "Complyance")
		save_uae_tax_settings(
			{"sla_days": old_sla, "participant_id": source, "asp_provider": "Complyance"}
		)

	def test_save_preserves_existing_secrets(self):
		from frappe.utils.password import get_decrypted_password, set_encrypted_password
		from taxmate.api.tax_settings import get_uae_tax_settings, save_uae_tax_settings

		if not frappe.db.exists("DocType", "UAE Tax Settings"):
			self.skipTest("UAE Tax Settings missing")
		marker = f"tm-asp-{frappe.generate_hash(length=8)}"
		set_encrypted_password("UAE Tax Settings", "UAE Tax Settings", marker, "auth_key")
		frappe.db.commit()
		before = get_uae_tax_settings()
		self.assertTrue(before.get("has_auth_key"))
		old_sla = before.get("sla_days") or 14
		new_sla = 13 if int(old_sla) == 14 else 14
		source = before.get("participant_id") or "taxmate:1.0"
		if ":" not in str(source):
			source = "taxmate:1.0"
		save_uae_tax_settings(
			{
				"sla_days": new_sla,
				"participant_id": source,
				"asp_provider": "Complyance",
				"archive_retention_years": before.get("archive_retention_years") or 5,
			}
		)
		stored = get_decrypted_password(
			"UAE Tax Settings", "UAE Tax Settings", "auth_key", raise_exception=False
		)
		self.assertEqual(stored, marker)
		after = get_uae_tax_settings()
		self.assertTrue(after.get("has_auth_key"))
		save_uae_tax_settings(
			{
				"sla_days": old_sla,
				"participant_id": source,
				"asp_provider": "Complyance",
				"archive_retention_years": before.get("archive_retention_years") or 5,
			}
		)


class TestDeskWriteGates(FrappeTestCase):
	"""Behavioral checks for the Desk actions the SPA now calls."""

	def test_gates_reject_blank_or_unknown_input(self):
		from taxmate.api.accounts import can_update_items, make_purchase_return, update_items
		from taxmate.api.material_request import set_status as stop_request
		from taxmate.api.quotation import declare_lost, sales_order_allowed
		from taxmate.api.sales_order import make_work_orders, set_status

		for value in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				make_purchase_return(value)
		with self.assertRaises(frappe.ValidationError):
			update_items("Note", "X", [{"item_code": "A", "qty": 1, "rate": 1}])
		with self.assertRaises(frappe.ValidationError):
			update_items("Sales Order", "SO-MISSING", [])
		with self.assertRaises(frappe.ValidationError):
			can_update_items("Sales Order", "")
		with self.assertRaises(frappe.ValidationError):
			set_status("SO-MISSING", "Banana")
		with self.assertRaises(frappe.ValidationError):
			make_work_orders("", [])
		with self.assertRaises(frappe.ValidationError):
			declare_lost("QTN-MISSING", "")
		with self.assertRaises(frappe.ValidationError):
			sales_order_allowed("")
		with self.assertRaises(frappe.ValidationError):
			stop_request("MR-MISSING", "Closed")
		from taxmate.api.linked_docs import (
			make_delivery_trip_from_delivery_note,
			make_opportunity_from_lead,
			make_payment_request,
			make_rfq_from_material_request,
			make_shipment_from_delivery_note,
			make_subcontracting_inward_from_sales_order,
			make_subcontracting_order_from_purchase_order,
			make_supplier_rfq,
		)

		for value in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				make_opportunity_from_lead(value)
			with self.assertRaises(frappe.ValidationError):
				make_shipment_from_delivery_note(value)
			with self.assertRaises(frappe.ValidationError):
				make_supplier_rfq(value)
		with self.assertRaises(frappe.ValidationError):
			make_payment_request("Note", "X")
		with self.assertRaises(frappe.ValidationError):
			make_payment_request("Sales Invoice", "")
		with self.assertRaises(frappe.ValidationError):
			make_rfq_from_material_request("")
		with self.assertRaises(frappe.ValidationError):
			make_delivery_trip_from_delivery_note("   ")
		with self.assertRaises(frappe.ValidationError):
			make_subcontracting_order_from_purchase_order("")
		with self.assertRaises(frappe.ValidationError):
			make_subcontracting_inward_from_sales_order(None)

	def test_shipment_row_names_the_delivery_note(self):
		from taxmate.api.linked_docs import shipment_delivery_row

		row = shipment_delivery_row("DN-1", 25, [10, 15])
		self.assertEqual(row["delivery_note"], "DN-1")
		self.assertEqual(row["grand_total"], 25)
		fallback = shipment_delivery_row("DN-1", 0, [10, 15])
		self.assertEqual(fallback["grand_total"], 25)

	def test_sales_order_hold_resume_and_update_qty(self):
		from taxmate.api.accounts import can_update_items, update_items
		from taxmate.api.sales_order import set_status
		from taxmate.api.workflow import cancel, submit
		from taxmate.tests.uae_prove_fixtures import SERVICE_ITEM, WALK_IN, _ensure_walk_in, require_prove_site

		try:
			company = require_prove_site()
		except frappe.DoesNotExistError as exc:
			self.skipTest(str(exc))
		_ensure_walk_in()
		doc = insert(
			{
				"doctype": "Sales Order",
				"company": company,
				"customer": WALK_IN,
				"order_type": "Sales",
				"transaction_date": "2026-11-15",
				"delivery_date": "2026-11-30",
				"vat_emirate": "Dubai",
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"taxes_and_charges": "UAE VAT 5% - TM",
				"items": [{"item_code": SERVICE_ITEM, "qty": 1, "rate": 100, "delivery_date": "2026-11-30"}],
			}
		)
		submitted = submit({"doctype": "Sales Order", "name": doc["name"]})
		self.assertEqual(can_update_items("Sales Order", doc["name"])["allowed"], 1)
		held = set_status(doc["name"], "On Hold", "waiting")
		self.assertEqual(held["status"], "On Hold")
		row = submitted["items"][0]
		update_items(
			"Sales Order",
			doc["name"],
			[{
				"docname": row["name"],
				"item_code": row["item_code"],
				"qty": 2,
				"rate": row["rate"],
				"uom": row.get("uom"),
				"conversion_factor": row.get("conversion_factor") or 1,
				"description": row.get("description"),
				"delivery_date": str(row.get("delivery_date") or "2026-11-30"),
				"warehouse": row.get("warehouse"),
				"fg_item": row.get("fg_item"),
				"fg_item_qty": row.get("fg_item_qty"),
			}],
		)
		fetched = get("Sales Order", doc["name"])
		self.assertEqual(flt_qty(fetched["items"][0]["qty"]), 2)
		resumed = set_status(doc["name"], "Draft")
		self.assertNotEqual(resumed["status"], "On Hold")
		cancel("Sales Order", doc["name"])


def flt_qty(value) -> float:
	return float(value or 0)

