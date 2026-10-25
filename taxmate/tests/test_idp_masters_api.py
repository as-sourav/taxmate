"""Site tests for consent-based Scan masters.

Callers: bench run-tests --module taxmate.tests.test_idp_masters_api.
Exercises taxmate.idp.masters.create_confirmed / apply_created_links / party_by_trn
(Supplier, Customer, Item, Address). SPA write path via idp_desk.save uses the same helpers.
Schema: proposals[{key, doctype, confirmed, required_fields, optional_fields}].

User: Implement the plan as specified… Don't stop until you have completed all the to-dos.
"""

from __future__ import annotations

import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from taxmate.idp.masters import apply_created_links, create_confirmed, party_by_trn


class TestIdpMastersApi(FrappeTestCase):
	def test_create_confirmed_supplier_and_item(self):
		suffix = uuid.uuid4().hex[:8]
		supplier_name = f"Scan Sup {suffix}"
		item_name = f"Scan Chair {suffix}"
		item_code = f"SCAN-{suffix[:6].upper()}"
		digits = "".join(str(int(c, 16) % 10) for c in suffix)
		trn = ("100" + digits + "000000000")[:13] + "03"
		proposals = [
			{
				"key": f"supplier:{supplier_name}",
				"doctype": "Supplier",
				"confirmed": True,
				"required_fields": [
					{"field": "supplier_name", "value": supplier_name},
					{"field": "supplier_type", "value": "Company"},
					{"field": "address_line1", "value": "Sheikh Zayed Rd"},
					{"field": "city", "value": "Dubai"},
					{"field": "state", "value": "Dubai"},
				],
				"optional_fields": [
					{"field": "tax_id", "value": trn},
					{"field": "email_id", "value": f"scan-{suffix}@example.com"},
					{"field": "phone", "value": "+971500000001"},
				],
				"source_fields": {},
			},
			{
				"key": f"item:{item_name}",
				"doctype": "Item",
				"link_index": 0,
				"confirmed": True,
				"required_fields": [
					{"field": "item_code", "value": item_code},
					{"field": "item_name", "value": item_name},
					{"field": "stock_uom", "value": "Nos"},
				],
				"optional_fields": [],
				"source_fields": {},
			},
		]
		made = create_confirmed(proposals)
		self.assertTrue(made.get("ok"), made)
		self.assertTrue(frappe.db.exists("Supplier", made["created"]["supplier"]))
		self.assertTrue(frappe.db.exists("Item", made["created"]["item_code"]))
		addr = frappe.db.get_value("Supplier", made["created"]["supplier"], "supplier_primary_address")
		self.assertTrue(addr)
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": supplier_name},
				"items": [{"item_name": item_name}],
			},
		}
		apply_created_links(extracted, made["created"])
		self.assertEqual(extracted["extracted_data"]["header"]["supplier"], made["created"]["supplier"])
		self.assertEqual(extracted["extracted_data"]["items"][0]["item_code"], made["created"]["item_code"])

	def test_apply_created_links_overwrites_stale_item_code(self):
		"""Second LLM read often leaves a different item_code than the clerk confirmed."""
		suffix = uuid.uuid4().hex[:8]
		code = f"OVW-{suffix[:6].upper()}"
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {"customer": "Stale Customer Name"},
				"items": [{"item_code": "STALE-FROM-LLM", "item_name": "Critical Device"}],
			},
		}
		apply_created_links(
			extracted,
			{"customer": f"Real Cust {suffix}", "item_code": code, "item:0": code},
		)
		self.assertEqual(extracted["extracted_data"]["header"]["customer"], f"Real Cust {suffix}")
		self.assertEqual(extracted["extracted_data"]["items"][0]["item_code"], code)

	def test_zero_line_rate_filled_from_header_total(self):
		from taxmate.idp.masters import normalize_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Vendor LLC", "grand_total": 271000},
				"items": [
					{
						"item_name": "Critical Device with actionable intelligence",
						"qty": 1,
						"rate": 0,
						"amount": 0,
						"uom": "Nos",
					}
				],
			},
			"validation": {"missing_masters": []},
		}
		normalize_extract(extracted)
		item = extracted["extracted_data"]["items"][0]
		self.assertEqual(item["rate"], 271000)
		self.assertEqual(item["amount"], 271000)

	def test_create_confirmed_customer(self):
		suffix = uuid.uuid4().hex[:8]
		name = f"Scan Cust {suffix}"
		digits = "".join(str(int(c, 16) % 10) for c in suffix)
		trn = ("200" + digits + "000000000")[:15]
		made = create_confirmed(
			[
				{
					"key": f"customer:{name}",
					"doctype": "Customer",
					"confirmed": True,
					"required_fields": [
						{"field": "customer_name", "value": name},
						{"field": "customer_type", "value": "Company"},
						{"field": "address_line1", "value": "Marina Walk"},
						{"field": "city", "value": "Dubai"},
						{"field": "state", "value": "Dubai"},
					],
					"optional_fields": [{"field": "tax_id", "value": trn}],
					"source_fields": {},
				}
			]
		)
		self.assertTrue(made.get("ok"), made)
		self.assertTrue(frappe.db.exists("Customer", made["created"]["customer"]))
		trn = frappe.db.get_value("Customer", made["created"]["customer"], "tax_id")
		matched = party_by_trn("Customer", trn)
		self.assertEqual(matched, made["created"]["customer"])

	def test_unconfirmed_proposal_is_refused(self):
		made = create_confirmed(
			[
				{
					"key": "supplier:No",
					"doctype": "Supplier",
					"confirmed": False,
					"required_fields": [{"field": "supplier_name", "value": "No"}],
					"optional_fields": [],
					"source_fields": {},
				}
			]
		)
		self.assertFalse(made["ok"])
		self.assertEqual(made["error_key"], "idp.propose.needConsent")

	def test_confirmed_unit_is_created_before_the_item(self):
		suffix = uuid.uuid4().hex[:6]
		unit = f"Bx{suffix}"
		item_code = f"SCAN-{suffix.upper()}"
		proposals = [
			{
				"key": f"item:{item_code}",
				"doctype": "Item",
				"link_index": 0,
				"confirmed": True,
				"required_fields": [
					{"field": "item_code", "value": item_code},
					{"field": "item_name", "value": f"Scan goods {suffix}"},
					{"field": "stock_uom", "value": unit},
				],
				"optional_fields": [],
				"source_fields": {},
			},
			{
				"key": f"uom:{unit}",
				"doctype": "UOM",
				"confirmed": True,
				"required_fields": [{"field": "uom_name", "value": unit}],
				"optional_fields": [],
				"source_fields": {},
			},
		]
		made = create_confirmed(proposals)
		self.assertTrue(made.get("ok"), made)
		self.assertTrue(frappe.db.exists("UOM", unit))
		self.assertEqual(frappe.db.get_value("Item", item_code, "stock_uom"), unit)

	def test_an_accounts_user_can_create_their_scan_log(self):
		from taxmate.setup.spa_roles import _ensure_scan_perms

		_ensure_scan_perms()
		email = f"scan-{uuid.uuid4().hex[:8]}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Scan",
				"send_welcome_email": 0,
				"roles": [{"role": "Accounts User"}],
			}
		)
		user.insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			self.assertTrue(frappe.has_permission("IDP Document Log", "create"))
		finally:
			frappe.set_user("Administrator")

	def test_dairy_line_is_not_filed_under_a_services_group(self):
		"""Item and Item Group are different. Labneh is not Consulting Services.

		Caller: bench run-tests --module taxmate.tests.test_idp_masters_api.
		User: Items and Item Groups are different. The OCR should understand Frappe.
		"""
		from taxmate.idp.masters import item_group_for_label, resolve_item_group

		parent = frappe.db.get_value("Item Group", {"is_group": 1}, "name")
		name = "Dairy Isolation Test"
		if not frappe.db.exists("Item Group", name):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": name,
					"parent_item_group": parent,
					"is_group": 0,
				}
			).insert()
		group = item_group_for_label("Labneh 400 g")
		self.assertIn("dairy", group.lower())
		self.assertNotIn("consulting", group.lower())
		chosen = resolve_item_group("Labneh 400 g", "Consulting Services")
		self.assertIn("dairy", chosen.lower())
		self.assertNotEqual(chosen, "Consulting Services")

	def test_other_company_supplier_is_not_reused(self):
		"""Two companies, one printed supplier. Do not reuse the other company's row.

		Caller: bench run-tests --module taxmate.tests.test_idp_masters_api.
		User: the scan may be used by multiple users at once, and save draft must not
		fail with permission denied after a good read.
		"""
		from taxmate.idp.masters import scope_extract_to_company
		from taxmate.utils.company import set_active_company

		companies = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(companies) < 2:
			self.skipTest("need two companies")
		if not frappe.get_meta("Supplier").has_field("custom_company"):
			self.skipTest("Supplier has no custom_company")
		home, other = companies[0], companies[1]
		suffix = uuid.uuid4().hex[:8]
		legal = f"Scan Dairy {suffix}"
		digits = "".join(str(int(c, 16) % 10) for c in suffix)
		trn = ("100" + digits + "000000000")[:13] + "03"
		group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
		foreign = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": legal,
				"supplier_group": group,
				"supplier_type": "Company",
				"custom_company": other,
				"tax_id": trn,
			}
		)
		foreign.insert()
		email = f"scan-co-{suffix}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "ScanCo",
				"send_welcome_email": 0,
				"roles": [{"role": "TaxMate Accountant"}],
			}
		)
		user.insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": email,
				"allow": "Company",
				"for_value": home,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(email)
		set_active_company(home)
		self.assertIsNone(party_by_trn("Supplier", trn))
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": foreign.name, "tax_id": trn},
				"items": [],
			},
			"validation": {"missing_masters": []},
		}
		scope_extract_to_company(extracted)
		self.assertNotIn("supplier", extracted["extracted_data"]["header"])
		made = create_confirmed(
			[
				{
					"key": f"supplier:{legal}",
					"doctype": "Supplier",
					"confirmed": True,
					"required_fields": [
						{"field": "supplier_name", "value": legal},
						{"field": "supplier_type", "value": "Company"},
					],
					"optional_fields": [{"field": "tax_id", "value": trn}],
					"source_fields": {},
				}
			]
		)
		self.assertTrue(made.get("ok"), made)
		created = made["created"]["supplier"]
		self.assertNotEqual(created, foreign.name)
		self.assertEqual(frappe.db.get_value("Supplier", created, "custom_company"), home)
		self.assertEqual(party_by_trn("Supplier", trn), created)
