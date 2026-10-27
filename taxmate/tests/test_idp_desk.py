"""Dashboard IDP surface. No site and no OpenAI.

Run: PYTHONPATH=apps/taxmate python -m unittest taxmate.tests.test_idp_desk
"""

from __future__ import annotations

import unittest

from taxmate.idp.desk import (
	JOBS,
	TARGETS,
	apply_writes,
	attach_item_codes,
	build_surface,
	diffs_from_compare,
	draft_instructions,
	draft_only_error,
	file_read_error,
	finish_draft,
	gaps_from_validation,
	header_updates,
	match_filters,
	matches_from_rows,
	plan_run,
	resolve_ocr_language,
	review_from_extract,
	search_arguments,
	submit_requested,
)

ALL_JOB_IDS = frozenset(str(job["id"]) for job in JOBS)


def _allow_all(_doctype: str, _permission: str) -> bool:
	return True


def _full_surface(*, llm_ready: bool = True):
	"""Surface with every JOBS row — for plan_run coverage of non-create actions."""
	return build_surface(can=_allow_all, llm_ready=llm_ready, job_ids=ALL_JOB_IDS)


class TestIdpDeskSurface(unittest.TestCase):
	def test_dashboard_surface_is_create_only(self):
		surface = build_surface(can=_allow_all, llm_ready=True)
		ids = [row["id"] for row in surface["actions"]]
		self.assertEqual(ids, ["create"])
		self.assertNotIn("submit", ids)
		self.assertNotIn("create_master", ids)
		self.assertNotIn("compare", ids)

	def test_full_job_list_still_available_for_tooling(self):
		surface = _full_surface()
		ids = [row["id"] for row in surface["actions"]]
		self.assertEqual(ids, ["create", "compare", "search", "update", "match", "delete"])

	def test_surface_notices_stay_empty(self):
		surface = build_surface(can=_allow_all, llm_ready=True)
		self.assertEqual(surface["notices"], [])

	def test_permission_drops_a_doctype_and_an_empty_job(self):
		def can(doctype: str, permission: str) -> bool:
			return doctype == "Sales Invoice" and permission == "create"

		surface = build_surface(can=can, llm_ready=True)
		self.assertEqual([row["id"] for row in surface["actions"]], ["create"])
		targets = surface["actions"][0]["targets"]
		self.assertEqual([row["doctype"] for row in targets], ["Sales Invoice"])

	def test_scan_dialog_offers_the_books_documents(self):
		surface = build_surface(can=_allow_all, llm_ready=True)
		ready = [row["doctype"] for row in surface["actions"][0]["targets"] if row["ready"]]
		self.assertEqual(
			ready,
			["Sales Invoice", "Purchase Invoice", "Quotation", "Payment Entry"],
		)

	def test_opportunity_has_no_desk_route(self):
		surface = _full_surface()
		create = surface["actions"][0]
		opportunity = next(row for row in create["targets"] if row["doctype"] == "Opportunity")
		self.assertIsNone(opportunity["route"])
		self.assertFalse(opportunity["ready"])
		for action in surface["actions"]:
			for target in action["targets"]:
				route = target["route"] or ""
				self.assertNotIn("/app/", route)

	def test_create_runs_without_a_model_key(self):
		surface = build_surface(can=_allow_all, llm_ready=False)
		self.assertIsNone(surface["blocked_key"])
		runnable = [row["id"] for row in surface["actions"] if row["runnable"]]
		self.assertEqual(runnable, ["create"])
		full = _full_surface(llm_ready=False)
		self.assertEqual(
			[row["id"] for row in full["actions"] if row["runnable"]],
			["create", "compare", "search", "update", "match", "delete"],
		)

	def test_plan_run_refuses_unwired_jobs_and_unknown_files(self):
		surface = _full_surface()
		self.assertEqual(
			plan_run(surface, action="delete", target="Sales Invoice", file_name=None)["error_key"],
			"idp.query",
		)
		self.assertTrue(
			plan_run(surface, action="delete", target="Sales Invoice", file_name=None, query="ACC-SINV-0001")[
				"ok"
			]
		)
		self.assertTrue(
			plan_run(surface, action="search", target="Sales Invoice", file_name=None, query="Acme")["ok"]
		)
		self.assertEqual(
			plan_run(surface, action="create", target="Opportunity", file_name="bill.pdf")["error_key"],
			"idp.noRoute",
		)
		self.assertEqual(
			plan_run(surface, action="create", target="Sales Invoice", file_name="bill.exe")["error_key"],
			"idp.file",
		)
		planned = plan_run(
			surface, action="create", target="Purchase Invoice", file_name="/private/files/bill.pdf"
		)
		self.assertTrue(planned["ok"])
		self.assertEqual(planned["route"], "/purchase-invoices")
		dash = build_surface(can=_allow_all, llm_ready=True)
		self.assertEqual(
			plan_run(dash, action="compare", target="Sales Invoice", file_name="bill.pdf", query="X")[
				"error_key"
			],
			"idp.denied",
		)

	def test_draft_is_never_a_submit(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {"customer": "Acme"},
				"items": [{"item_code": "ITEM-1", "item_name": "Desk"}],
			},
			"validation": {"is_valid": True, "errors": [], "warnings": [], "missing_masters": []},
		}
		review = review_from_extract(extracted, route="/invoices")
		self.assertTrue(review["can_save"])
		self.assertEqual(review["lines"], [{"label_key": "f.customer", "value": "Acme"}])
		self.assertEqual(review["items"], [{"label": "ITEM-1 — Desk"}])
		instructions = draft_instructions(extracted)
		self.assertFalse(instructions["submit"])
		self.assertTrue(instructions["user_confirmed"])
		self.assertNotIn("docstatus", instructions["header"])

	def test_draft_drops_docstatus_and_keeps_the_party(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Acme", "docstatus": 1, "posting_date": "2026-09-01"},
				"items": [],
			},
			"validation": {"is_valid": True, "errors": [], "warnings": [], "missing_masters": []},
		}
		instructions = draft_instructions(extracted)
		self.assertEqual(instructions["header"], {"supplier": "Acme", "posting_date": "2026-09-01"})
		self.assertFalse(instructions["submit"])
		review = review_from_extract(extracted, route="/purchase-invoices")
		self.assertEqual(
			[row["label_key"] for row in review["lines"]],
			["idp.field.supplier", "idp.field.date"],
		)

	def test_ocr_language_never_stays_auto(self):
		known = {"en", "ar"}
		self.assertEqual(resolve_ocr_language("auto", known), "en")
		self.assertEqual(resolve_ocr_language("ar", known), "ar")
		self.assertEqual(resolve_ocr_language("ar-AE", known), "ar")
		self.assertEqual(resolve_ocr_language("", known), "en")

	def test_file_read_requires_a_row_and_permission(self):
		self.assertEqual(file_read_error(found=False, allowed=False), "idp.file")
		self.assertEqual(file_read_error(found=True, allowed=False), "idp.file")
		self.assertIsNone(file_read_error(found=True, allowed=True))

	def test_review_hides_system_fields_and_names_the_gaps(self):
		validation = {
			"errors": [
				{"field": "customer", "message": 'Required field "Customer" is missing'},
				{"field": "selling_price_list", "message": 'Required field "Price List" is missing'},
				{
					"field": "base_grand_total",
					"message": 'Required field "Grand Total (Company Currency)" is missing',
				},
				{"field": "grand_total", "message": 'Required field "Grand Total" is missing'},
				{
					"field": "price_list_currency",
					"message": 'Required field "Price List Currency" is missing',
				},
			],
			"warnings": [{"field": "", "message": "At least one line item is required"}],
		}
		self.assertEqual(
			gaps_from_validation(validation),
			["f.customer", "idp.gap.items"],
		)

	def test_a_missing_cost_center_can_be_typed_and_submit_stays_off(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {"customer": "Acme", "posting_date": "2026-09-27", "taxes_and_charges": "12.50"},
				"items": [{"item_name": "Paper"}],
			},
			"validation": {
				"is_valid": False,
				"errors": [
					{"field": "cost_center", "message": 'Required field "Cost Center" is missing'},
					{"field": "selling_price_list", "message": 'Required field "Price List" is missing'},
				],
				"warnings": [],
				"missing_masters": [],
			},
		}
		review = review_from_extract(extracted, route="/invoices")
		self.assertTrue(review["can_save"])
		self.assertTrue(review["can_submit"])
		self.assertEqual(review["gaps"], [])
		self.assertEqual(
			[row["field"] for row in review["writes"]],
			["currency", "due_date", "cost_center", "vat_emirate"],
		)
		self.assertIn("AED", review["writes"][0]["options"])
		self.assertIn("Dubai", review["writes"][-1]["options"])
		instructions = draft_instructions(extracted)
		self.assertFalse(instructions["submit"])
		header, items = apply_writes(
			instructions["header"],
			instructions["items"],
			{"cost_center": "Main - ATL", "due_date": "2026-10-27", "docstatus": "1"},
			default_cost_center="Other - ATL",
		)
		self.assertEqual(header["customer"], "Acme")
		self.assertEqual(header["cost_center"], "Main - ATL")
		self.assertEqual(header["due_date"], "2026-10-27")
		self.assertNotIn("docstatus", header)
		self.assertNotIn("taxes_and_charges", header)
		self.assertEqual(items[0]["cost_center"], "Main - ATL")
		self.assertFalse(submit_requested(""))
		self.assertFalse(submit_requested("0"))
		self.assertTrue(submit_requested("1"))

	def test_missing_currency_is_asked_not_only_listed(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {"customer": "Acme", "posting_date": "2026-09-27", "due_date": "2026-10-27"},
				"items": [{"item_name": "Paper"}],
			},
			"validation": {
				"is_valid": False,
				"errors": [
					{"field": "currency", "message": 'Required field "Currency" is missing'},
					{"field": "selling_price_list", "message": 'Required field "Price List" is missing'},
				],
				"warnings": [],
				"missing_masters": [],
			},
		}
		review = review_from_extract(extracted, route="/invoices")
		self.assertTrue(review["can_save"])
		self.assertEqual(review["gaps"], [])
		currency_write = next(row for row in review["writes"] if row["field"] == "currency")
		self.assertEqual(currency_write["label_key"], "f.currency")
		self.assertEqual(currency_write["options"][0], "AED")
		header, _items = apply_writes(
			extracted["extracted_data"]["header"],
			extracted["extracted_data"]["items"],
			{"currency": "aed"},
		)
		self.assertEqual(header["currency"], "AED")

	def test_calculated_invoice_fields_do_not_block_the_draft(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {
					"customer": "Nordic Tax Partners AB",
					"posting_date": "2026-09-27",
					"due_date": "2026-10-27",
					"currency": "AED",
					"grand_total": 262.5,
				},
				"items": [{"item_name": "A4 Copy Paper (5 Reams)", "qty": 10, "rate": 25}],
			},
			"validation": {
				"is_valid": False,
				"errors": [
					{"field": "selling_price_list", "message": 'Required field "Price List" is missing'},
					{"field": "uom", "message": 'Row 1 — Required field "UOM" is missing'},
					{"field": "charge_type", "message": 'Row 1 — Required field "Type" is missing'},
					{
						"field": "income_account",
						"message": 'Row 1 — Required field "Income Account" is missing',
					},
					{"field": "cost_center", "message": 'Row 1 — Required field "Cost Center" is missing'},
				],
				"warnings": [],
				"missing_masters": [],
			},
		}
		review = review_from_extract(extracted, route="/invoices")
		self.assertTrue(review["can_save"])
		self.assertEqual(review["gaps"], [])
		self.assertEqual([row["field"] for row in review["writes"]], ["cost_center", "vat_emirate"])
		header, items = finish_draft(
			extracted["extracted_data"]["header"],
			extracted["extracted_data"]["items"],
			{"vat_emirate": "Not a place"},
			{
				"company": "Ascra Technology LLP",
				"cost_center": "Main - ATL",
				"vat_emirate": "Dubai",
				"selling_price_list": "Standard Selling",
				"income_account": "Sales - ATL",
				"item_uom": {},
			},
		)
		self.assertEqual(header["vat_emirate"], "Dubai")
		self.assertEqual(header["company"], "Ascra Technology LLP")
		self.assertEqual(items[0]["cost_center"], "Main - ATL")
		self.assertEqual(items[0]["income_account"], "Sales - ATL")

	def test_the_model_can_add_an_item_code_the_rules_missed(self):
		try:
			from idp.mappers.base import MappedDocument
			from idp.mappers.hybrid_mapper import HybridFieldMapper
		except ImportError:
			self.skipTest("idp is not on PYTHONPATH")
		mapper = HybridFieldMapper(object(), object())
		rule = MappedDocument(
			doctype="Sales Invoice",
			items=[{"item_name": "A4 Copy Paper (5 Reams)", "qty": 10}],
		)
		merged = mapper._merge(
			rule,
			{
				"header": {},
				"items": [{"item_name": "A4 Copy Paper (5 Reams)", "item_code": "PAP-A4-01", "uom": "Nos"}],
			},
		)
		self.assertEqual(merged.items[0]["item_code"], "PAP-A4-01")
		self.assertEqual(merged.items[0]["uom"], "Nos")
		self.assertEqual(merged.items[0]["qty"], 10)

	def test_a_printed_item_name_uses_the_existing_code(self):
		items = [{"item_name": "A4 Copy Paper (5 Reams)", "qty": 10}]
		attach_item_codes(items, lambda name: "PAP-A4-01" if "Paper" in name else None)
		self.assertEqual(items[0]["item_code"], "PAP-A4-01")
		attach_item_codes(items, lambda _name: "OTHER")
		self.assertEqual(items[0]["item_code"], "PAP-A4-01")

	def test_draft_blocks_missing_masters(self):
		extracted = {
			"success": True,
			"extracted_data": {"doctype": "Purchase Invoice", "header": {"supplier": "New Co"}, "items": []},
			"validation": {"is_valid": True, "errors": [], "warnings": [], "missing_masters": ["supplier"]},
		}
		self.assertFalse(draft_instructions(extracted)["ok"])
		self.assertEqual(draft_instructions(extracted)["error_key"], "idp.propose.needConsent")

	def test_confirmed_proposals_bypass_schema_noise(self):
		"""ERPNext base_rate noise must not soft-fail Save after the clerk confirms create."""
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Real Supplier LLC", "bill_no": "SOC_0001/2026", "grand_total": 100},
				"items": [{"item_code": "ITEM-1", "item_name": "Service", "qty": 1, "rate": 100}],
			},
			"validation": {
				"is_valid": False,
				"errors": [
					{
						"field": "mystery_field",
						"message": "Something obscure blocked the schema",
						"severity": "error",
					}
				],
				"warnings": [],
				"missing_masters": [],
			},
		}
		self.assertFalse(draft_instructions(extracted, proposals=[])["ok"])
		confirmed = [
			{
				"key": "supplier:Real Supplier LLC",
				"doctype": "Supplier",
				"confirmed": True,
				"required_fields": [
					{"field": "supplier_name", "value": "Real Supplier LLC"},
					{"field": "supplier_type", "value": "Company"},
				],
				"optional_fields": [],
			}
		]
		ok = draft_instructions(extracted, proposals=confirmed)
		self.assertTrue(ok.get("ok"), ok)
		self.assertEqual(ok["header"]["supplier"], "Real Supplier LLC")

	def test_unresolved_supplier_becomes_a_proposal(self):
		from taxmate.idp.masters import build_proposals, proposals_complete, split_missing

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"supplier": "Scan Co LLC",
					"tax_id": "100123456700003",
					"address_line1": "Sheikh Zayed Rd",
					"city": "Dubai",
					"vat_emirate": "Dubai",
				},
				"items": [{"item_name": "Office Chair", "qty": 2}],
			},
			"validation": {
				"is_valid": False,
				"errors": [],
				"warnings": [],
				"missing_masters": [
					"supplier",
					{"doctype": "Item", "name": "Office Chair", "field": "item_code"},
				],
			},
		}
		creatable, blocked = split_missing(extracted["validation"]["missing_masters"])
		self.assertEqual([row["doctype"] for row in creatable], ["Supplier", "Item"])
		self.assertEqual(blocked, [])
		review = review_from_extract(extracted, route="/purchase-invoices")
		self.assertTrue(review["ok"])
		self.assertTrue(review["can_save"])
		self.assertFalse(review["can_submit"])
		self.assertEqual(review["error_key"], "idp.notice.propose")
		self.assertEqual(review["lines"][0]["value"], "Scan Co LLC")
		self.assertEqual(len(review["proposals"]), 2)
		self.assertEqual(review["proposals"][0]["doctype"], "Supplier")
		self.assertEqual(review["proposals"][1]["doctype"], "Item")
		self.assertFalse(proposals_complete(review["proposals"]))
		self.assertEqual(len(build_proposals(extracted)), 2)
		self.assertTrue(any(row["status"] == "done" for row in review["stage_log"]))

	def test_missing_account_still_blocks(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Acme", "credit_to": "Creditors - X"},
				"items": [],
			},
			"validation": {
				"is_valid": False,
				"errors": [],
				"warnings": [],
				"missing_masters": [{"doctype": "Account", "name": "Creditors - X", "field": "credit_to"}],
			},
		}
		review = review_from_extract(extracted, route="/purchase-invoices")
		self.assertFalse(review["can_save"])
		self.assertEqual(review["error_key"], "idp.notice.masters")
		self.assertEqual(review["proposals"], [])
		self.assertFalse(draft_instructions(extracted)["ok"])

	def test_ocr_billing_address_does_not_block_purchase(self):
		"""Street text on billing_address must not hard-block Save as a missing Address."""
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"supplier": "Eprotect360 Cyber Security FZCO",
					"billing_address": (
						"302, Sheikh Mohamed Bin Sultan Suroor Al Dhaheri Building, "
						"Salam, Lulu Center, AbuDhabi, UAE"
					),
					"bill_no": "SOC_0001/2026",
					"grand_total": 271000,
				},
				"items": [{"item_code": "CRITICAL-DEVICE-WITH", "item_name": "Critical Device", "qty": 1}],
			},
			"validation": {
				"is_valid": False,
				"errors": [],
				"warnings": [],
				"missing_masters": [
					{"doctype": "Supplier", "name": "Eprotect360 Cyber Security FZCO", "field": "supplier"},
					{
						"doctype": "Address",
						"name": "302, Sheikh Mohamed Bin Sultan Suroor Al Dhaheri Building",
						"field": "billing_address",
					},
					{"doctype": "Item", "name": "CRITICAL-DEVICE-WITH", "field": "item_code"},
				],
			},
		}
		review = review_from_extract(extracted, route="/purchase-invoices")
		self.assertTrue(review["can_save"])
		self.assertEqual(review["error_key"], "idp.notice.propose")
		self.assertEqual([row["doctype"] for row in review["proposals"]], ["Supplier", "Item"])
		self.assertNotIn("billing_address", extracted["extracted_data"]["header"])

	def test_sales_invoice_customer_proposal(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {
					"customer": "Buyer LLC",
					"tax_id": "100987654300003",
					"address_line1": "Marina Walk",
					"city": "Dubai",
					"vat_emirate": "Dubai",
				},
				"items": [{"item_code": "EXISTING", "item_name": "Paper"}],
			},
			"validation": {
				"is_valid": False,
				"errors": [],
				"warnings": [],
				"missing_masters": ["customer"],
			},
		}
		review = review_from_extract(extracted, route="/invoices")
		self.assertEqual(len(review["proposals"]), 1)
		self.assertEqual(review["proposals"][0]["doctype"], "Customer")
		self.assertEqual(review["proposals"][0]["consent_label_key"], "idp.propose.customer")
		self.assertEqual(review["error_key"], "idp.notice.propose")

	def test_surface_exposes_read_stages(self):
		surface = build_surface(can=_allow_all, llm_ready=True)
		self.assertEqual(
			[row["key"] for row in surface["read_stages"]],
			["upload", "ocr", "parties", "items", "review"],
		)

	def test_ocr_bill_to_becomes_customer_proposal(self):
		from taxmate.idp.masters import build_proposals, normalize_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {
					"invoice_number": "SOC_0001/2026",
					"bill_to": "NAS NEURON Health Services",
					"billing_address": "302, Sheikh Mohamed Building, Salam, Lulu Center, AbuDhabi, UAE",
					"Date": "2026-08-18",
					"subtotal": 271000,
					"Total": 271000,
					"Currency": "AED",
				},
				"items": [{"item_name": "Eprotect 360 Cyber Security - FZCO", "qty": 1}],
			},
			"validation": {"is_valid": False, "errors": [], "warnings": [], "missing_masters": []},
		}
		normalize_extract(extracted)
		header = extracted["extracted_data"]["header"]
		self.assertEqual(header["customer"], "NAS NEURON Health Services")
		self.assertEqual(header["bill_no"], "SOC_0001/2026")
		self.assertTrue(header.get("address_line1"))
		self.assertEqual(header.get("state") or header.get("vat_emirate"), "Abu Dhabi")
		item = extracted["extracted_data"]["items"][0]
		self.assertEqual(item["item_name"], "Eprotect 360 Cyber Security - FZCO")
		self.assertLessEqual(len(item["item_code"]), 20)
		self.assertNotIn(" ", item["item_code"])
		extracted["validation"]["missing_masters"] = [
			{"doctype": "Customer", "name": header["customer"], "field": "customer"},
			{
				"doctype": "Item",
				"name": "Eprotect 360 Cyber Security - FZCO",
				"field": "item_code",
			},
		]
		proposals = build_proposals(extracted)
		self.assertEqual([row["doctype"] for row in proposals], ["Customer", "Item"])
		self.assertEqual(proposals[0]["source_fields"].get("city"), "Lulu Center")
		review = review_from_extract(extracted, route="/invoices")
		self.assertEqual(review["error_key"], "idp.notice.propose")
		self.assertTrue(review["can_save"])
		self.assertEqual(len(review["proposals"]), 2)

	def test_ocr_bill_to_becomes_supplier_on_purchase(self):
		from taxmate.idp.masters import normalize_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"bill_to": "Buyer Co LLC", "vendor": "Real Supplier LLC"},
				"items": [],
			},
			"validation": {"missing_masters": []},
		}
		normalize_extract(extracted)
		self.assertEqual(extracted["extracted_data"]["header"]["supplier"], "Real Supplier LLC")
		# bill_to is the buyer — must not overwrite supplier on purchase docs
		extracted["extracted_data"]["header"].pop("supplier", None)
		extracted["extracted_data"]["header"].pop("vendor", None)
		normalize_extract(extracted)
		self.assertNotIn("supplier", extracted["extracted_data"]["header"])

	def test_ocr_account_name_becomes_supplier_on_purchase(self):
		from taxmate.idp.masters import build_proposals, normalize_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"bill_to": "NAS NEURON Health Services",
					"account_name": "Eprotect360 Cyber Security FZCO",
					"invoice_number": "SOC_0001/2026",
					"Date": "2026-08-18",
					"total_due": 271000,
					"Currency": "AED",
					"bank_name": "WIO Bank",
					"iban_number": "AE870860000009365222307",
				},
				"items": [
					{
						"item_name": (
							"300 Critical Device with actionable intelligence, "
							"security orch from 15th Aug'26 to 14thAug'29"
						),
						"qty": 300,
						"uom": "Nos",
					}
				],
			},
			"validation": {"is_valid": False, "errors": [], "warnings": [], "missing_masters": []},
		}
		normalize_extract(extracted)
		header = extracted["extracted_data"]["header"]
		self.assertEqual(header["supplier"], "Eprotect360 Cyber Security FZCO")
		self.assertNotEqual(header.get("supplier"), header.get("bill_to"))
		item = extracted["extracted_data"]["items"][0]
		self.assertEqual(item["item_name"], "Critical Device with actionable intelligence")
		self.assertEqual(item["item_code"], "CRITICAL-DEVICE-WITH")
		extracted["validation"]["missing_masters"] = [
			{"doctype": "Supplier", "name": header["supplier"], "field": "supplier"},
			{"doctype": "Item", "name": item["item_code"], "field": "item_code"},
		]
		proposals = build_proposals(extracted)
		self.assertEqual([row["doctype"] for row in proposals], ["Supplier", "Item"])
		self.assertEqual(proposals[1]["source_fields"]["item_code"], "CRITICAL-DEVICE-WITH")
		review = review_from_extract(extracted, route="/purchases")
		line_keys = [row["label_key"] for row in review["lines"]]
		self.assertIn("idp.field.supplier", line_keys)
		self.assertNotIn("idp.field.account_name", line_keys)
		self.assertFalse(any("iban" in key.lower() for key in line_keys))

	def test_ocr_rejects_fake_email_and_fills_total(self):
		from taxmate.idp.masters import build_proposals, normalize_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {
					"bill_to": "NAS NEURON Health Services",
					"email": "NNHS/2026/0023",
					"invoice_number": "SOC_0001/2026",
					"Date": "2026-08-18",
					"net_total": 271000,
					"Currency": "AED",
				},
				"items": [],
			},
			"validation": {"is_valid": False, "errors": [], "warnings": [], "missing_masters": []},
		}
		normalize_extract(extracted)
		header = extracted["extracted_data"]["header"]
		self.assertEqual(header["customer"], "NAS NEURON Health Services")
		self.assertEqual(header["grand_total"], 271000)
		self.assertNotIn("email", header)
		self.assertNotIn("email_id", header)
		items = extracted["extracted_data"]["items"]
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["rate"], 271000)
		extracted["validation"]["missing_masters"] = [
			{"doctype": "Customer", "name": header["customer"], "field": "customer"},
			{"doctype": "Item", "name": items[0]["item_code"], "field": "item_code"},
		]
		proposals = build_proposals(extracted)
		by_dt = {row["doctype"]: row for row in proposals}
		self.assertIn("Customer", by_dt)
		self.assertEqual(by_dt["Customer"]["source_fields"].get("email_id"), "")
		review = review_from_extract(extracted, route="/invoices")
		self.assertTrue(review["can_save"])
		self.assertEqual(review["gaps"], [])

	def test_currency_code_is_not_the_company(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"company": "AED",
					"supplier": "Eprotect360 Cyber Security FZCO",
					"posting_date": "2026-08-18",
					"bill_no": "SOC_0001/2026",
					"net_total": 271000,
					"grand_total": 271000,
					"vat_emirate": "Dubai",
					"tax_invoice": True,
					"seller_address": "IFZA Business Park, Dubai",
					"address_line1": "IFZA Business Park",
					"city": "Dubai",
					"state": "Dubai",
				},
				"items": [{"item_name": "Cyber security", "qty": 1}],
			},
			"validation": {
				"is_valid": False,
				"errors": [],
				"warnings": [],
				"missing_masters": [{"doctype": "Company", "name": "AED", "field": "company"}],
			},
		}
		review = review_from_extract(extracted, route="/purchase-invoices")
		header = extracted["extracted_data"]["header"]
		self.assertNotIn("company", header)
		self.assertEqual(header["currency"], "AED")
		self.assertTrue(review["can_save"])
		self.assertNotEqual(review["error_key"], "idp.notice.masters")
		labels = [row["label_key"] for row in review["lines"]]
		self.assertNotIn("idp.field.company", labels)
		self.assertNotIn("idp.field.seller_address", labels)
		self.assertNotIn("idp.field.address_line1", labels)
		self.assertIn("idp.field.supplier", labels)
		self.assertIn("idp.field.emirate", labels)

	def test_a_blocked_master_is_named(self):
		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Acme", "posting_date": "2026-09-01"},
				"items": [],
			},
			"validation": {
				"errors": [],
				"warnings": [],
				"missing_masters": [{"doctype": "Cost Center", "name": "Main - X", "field": "cost_center"}],
			},
		}
		review = review_from_extract(extracted, route="/purchase-invoices")
		self.assertFalse(review["can_save"])
		self.assertEqual(review["detail"], "Cost Center: Main - X")

	def test_proposal_merge_and_consent(self):
		from taxmate.idp.masters import merge_proposal_values, proposals_complete

		base = [
			{
				"key": "supplier:Acme",
				"doctype": "Supplier",
				"confirmed": False,
				"required_fields": [
					{"field": "supplier_name", "label_key": "idp.field.supplier", "value": "Acme"},
					{"field": "supplier_type", "label_key": "idp.field.partyType", "value": "Company"},
				],
				"optional_fields": [
					{"field": "address_line1", "label_key": "idp.field.addressLine", "value": ""},
				],
				"source_fields": {"supplier_name": "Acme"},
			}
		]
		self.assertFalse(proposals_complete(base))
		merged = merge_proposal_values(base, [{"key": "supplier:Acme", "confirmed": True}])
		self.assertTrue(merged[0]["confirmed"])
		self.assertTrue(proposals_complete(merged))

	def test_targets_match_idp_when_the_app_imports(self):
		try:
			from idp.core.constants import SUPPORTED_DOCTYPES
		except ImportError:
			self.skipTest("idp is not on PYTHONPATH")
		self.assertEqual([row["doctype"] for row in TARGETS], list(SUPPORTED_DOCTYPES))

	def test_accepts_the_idp_file_types(self):
		surface = build_surface(can=_allow_all, llm_ready=True)
		for ext in (".pdf", ".png", ".jpg", ".xlsx", ".csv", ".docx"):
			self.assertIn(ext, surface["accept"])

	def test_search_matches_the_name_or_the_party(self):
		args = search_arguments("Sales Invoice", "Acme")
		self.assertEqual(args["or_filters"], {"name": "Acme", "customer": "Acme"})
		self.assertEqual(args["filters"], {})
		self.assertEqual(
			match_filters({"customer": "Acme", "posting_date": "2026-09-01"}), {"customer": "Acme"}
		)
		self.assertEqual(match_filters({"remarks": "hello"}), {})

	def test_update_keeps_scalars_and_drafts_only(self):
		self.assertEqual(
			header_updates({"customer": "Acme", "docstatus": 1, "items": [{"item_code": "A"}]}),
			{"customer": "Acme"},
		)
		self.assertIsNone(draft_only_error(0))
		self.assertEqual(draft_only_error(1), "idp.submitted")

	def test_compare_rows_use_labels_and_routes(self):
		diffs = diffs_from_compare(
			[{"fieldname": "customer", "expected": "Acme", "actual": "Old", "status": "mismatch"}]
		)
		self.assertEqual(diffs[0]["label_key"], "f.customer")
		self.assertEqual(diffs[0]["after"], "Acme")
		matches = matches_from_rows([{"name": "ACC-SINV-0001"}], "/invoices")
		self.assertEqual(
			matches, [{"name": "ACC-SINV-0001", "label": "ACC-SINV-0001", "route": "/invoices/ACC-SINV-0001"}]
		)


GULF_DAIRY = """
Gulf Dairy Products Trading LLC  TAX INVOICE
Plot 7, Dubai Investments Park 2, Dubai, UAE
Invoice No: GDP-INV-55190
Tel: +971 4 885 3302
Invoice Date: 09/10/2026
TRN: 100938471500003
Due Date: 08/11/2026

Bill To
Al Madina Hypermarket LLC
Al Qusais Industrial Area 2, Dubai, UAE
TRN: 100398765400003

1 DY-MILK-1L Full Cream Milk 1 L 400 Btl 5.75 115.00 2,185.00 109.25 2,294.25
2 DY-MILK-2L Full Cream Milk 2 L 200 Btl 10.50 105.00 1,995.00 99.75 2,094.75
3 DY-LBN-1L Laban Fresh 1 L 250 Btl 4.25 - 1,062.50 53.12 1,115.62
4 DY-YOG-500 Plain Yoghurt 500 g 300 Cup 4.75 71.25 1,353.75 67.69 1,421.44
5 DY-LBNH-400 Labneh 400 g 120 Tub 9.50 - 1,140.00 57.00 1,197.00
6 DY-CHZ-SL Cheddar Cheese Slices 200 g 150 Pkt 8.25 - 1,237.50 61.88 1,299.38
7 DY-BTR-200 Salted Butter 200 g 100 Pkt 11.00 55.00 1,045.00 52.25 1,097.25
8 DY-CRM-250 Cooking Cream 250 ml 180 Pkt 6.50 - 1,170.00 58.50 1,228.50
9 DY-JCE-OR1 Orange Juice Fresh 1 L 160 Btl 8.75 - 1,400.00 70.00 1,470.00
10 DY-JCE-MG1 Mango Juice 1 L 120 Btl 7.50 - 900.00 45.00 945.00
11 DY-ICE-2L Vanilla Ice Cream 2 L 60 Tub 19.00 57.00 1,083.00 54.15 1,137.15
12 DY-EGG-30 Fresh Eggs Tray of 30 200 Tray 16.50 - 3,300.00 165.00 3,465.00

Total Taxable Amount 17,871.75
VAT @ 5% 893.59
Grand Total (AED) 18,765.34
"""


class TestGulfDairyPurchaseScan(unittest.TestCase):
	def test_units_are_not_items_and_seller_trn_is_kept(self):
		from taxmate.idp.masters import build_proposals, salvage_from_ocr_text

		extracted = {
			"success": True,
			"ocr_text": GULF_DAIRY,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"bill_no": "GDP-INV-55190",
					"net_total": 17871.75,
					"grand_total": 18765.34,
					"tax_id": "100398765400003",
					"vat_emirate": "Dubai",
				},
				"items": [
					{"item_name": "Btl"},
					{"item_name": "Btl"},
					{"item_name": "Cup"},
					{"item_name": "Pkt"},
					{"item_name": "Tub"},
				],
			},
			"validation": {
				"missing_masters": [
					{"doctype": "UOM", "name": "Btl", "field": "uom"},
					{"doctype": "UOM", "name": "Cup", "field": "uom"},
					{"doctype": "UOM", "name": "Pkt", "field": "uom"},
					{"doctype": "UOM", "name": "Tub", "field": "uom"},
					{"doctype": "UOM", "name": "Tray", "field": "uom"},
					{"doctype": "Item", "name": "DY-MILK-1L", "field": "item_code"},
				]
			},
		}
		salvage_from_ocr_text(extracted, GULF_DAIRY)
		header = extracted["extracted_data"]["header"]
		items = extracted["extracted_data"]["items"]
		self.assertEqual(header["supplier"], "Gulf Dairy Products Trading LLC")
		self.assertEqual(header["tax_id"], "100938471500003")
		self.assertEqual(header["currency"], "AED")
		self.assertEqual(header["posting_date"], "2026-10-09")
		self.assertEqual(header["due_date"], "2026-11-08")
		self.assertEqual(len(items), 12)
		self.assertEqual(items[0]["item_code"], "DY-MILK-1L")
		self.assertEqual(items[0]["item_name"], "Full Cream Milk 1 L")
		self.assertEqual(items[0]["uom"], "Btl")
		self.assertEqual(items[0]["qty"], 400)
		self.assertEqual(items[0]["discount_amount"], 115)
		self.assertEqual(items[0]["amount"], 2185)
		self.assertEqual(items[2]["uom"], "Btl")
		self.assertNotIn("discount_amount", items[2])
		self.assertEqual(items[11]["item_code"], "DY-EGG-30")
		self.assertEqual(items[11]["uom"], "Tray")
		self.assertEqual(items[11]["item_name"], "Fresh Eggs Tray of 30")
		cards = build_proposals(extracted)
		self.assertEqual([card["doctype"] for card in cards[:5]], ["UOM", "UOM", "UOM", "UOM", "UOM"])
		self.assertEqual(cards[-1]["doctype"], "Item")
		units = {card["title"] for card in cards if card["doctype"] == "UOM"}
		self.assertEqual(units, {"Btl", "Cup", "Pkt", "Tub", "Tray"})

	def test_one_mashed_line_is_replaced_and_vat_is_not_a_template(self):
		from taxmate.idp.masters import salvage_from_ocr_text

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {
					"supplier": "Gulf Dairy Products Trading LLC",
					"taxes_and_charges": "893.59",
					"net_total": 17871.75,
					"grand_total": 18765.34,
				},
				"items": [
					{
						"item_name": "DY-JCE-MG1 Mango Juice 1 L 120 Btl 7.50",
						"item_code": "DY-JCE-MG1-MANGO-JUI",
						"qty": 900,
						"uom": "Nos",
					}
				],
			},
		}
		salvage_from_ocr_text(extracted, GULF_DAIRY)
		header = extracted["extracted_data"]["header"]
		items = extracted["extracted_data"]["items"]
		self.assertNotIn("taxes_and_charges", header)
		self.assertEqual(len(items), 12)
		self.assertEqual(items[9]["item_code"], "DY-JCE-MG1")
		self.assertEqual(items[9]["item_name"], "Mango Juice 1 L")
		self.assertEqual(items[9]["uom"], "Btl")
		self.assertEqual(items[9]["qty"], 120)


NAHAR_RECEIPT = """
NAHAR W LAIL MINIMART
FRESH MARKET MINIMART
SHOP NO:1 CITADEL TOWER
BUSINESS BAY, DUBAI - U.A.E
TEL: 04 368 6868 ,052 7153 808
TRN : 100376117600003
TAX INVOICE
Date Time / تاريخ : 26/10/2026 17:36:55
Invoice # / فاتورة : 165847
SL Commodity Price Qty Amt
1 Al Rawabi Long Life 2.50 1.00 2.50
Fruit Cocktail Juice -
no added sugar 200 ml
6291030003817
2 Galaxy Strawberry 4.00 1.00 4.00
Chocolate Bar 36 gr
6285835000171
Net Amount 6.50
VAT% Sub Total Excl. VAT VAT VAT Incl
5.00 6.19 0.31 6.50
"""


class TestRetailReceiptScan(unittest.TestCase):
	def test_price_qty_columns_and_printed_vat(self):
		from taxmate.idp.masters import salvage_from_ocr_text

		extracted = {
			"success": True,
			"ocr_text": NAHAR_RECEIPT,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {},
				"items": [
					{"item_name": "Galaxy Strawberry", "qty": 4, "rate": 1, "amount": 4},
				],
			},
			"validation": {"errors": [], "warnings": [], "missing_masters": []},
		}
		salvage_from_ocr_text(extracted, NAHAR_RECEIPT)
		header = extracted["extracted_data"]["header"]
		items = extracted["extracted_data"]["items"]
		self.assertEqual(len(items), 2)
		self.assertIn("Al Rawabi", items[0]["item_name"])
		self.assertIn("Galaxy", items[1]["item_name"])
		self.assertEqual(items[0]["qty"], 1)
		self.assertEqual(items[1]["qty"], 1)
		self.assertNotEqual(items[0]["rate"], 1)
		self.assertAlmostEqual(sum(row["amount"] for row in items), 6.19, places=2)
		self.assertEqual(header["tax_total"], 0.31)
		self.assertEqual(header["net_total"], 6.19)
		self.assertEqual(header["grand_total"], 6.50)
		self.assertEqual(header["bill_no"], "165847")
		self.assertEqual(header["posting_date"], "2026-10-26")
		self.assertEqual(header["tax_id"], "100376117600003")

	def test_sale_customer_is_a_field_and_supplier_is_not_saved(self):
		from taxmate.idp.desk import gaps_from_validation, keep_known_fields, writes_from_extract

		extracted = {
			"success": True,
			"extracted_data": {
				"doctype": "Sales Invoice",
				"header": {
					"supplier": "NAHAR W LAIL MINIMART",
					"posting_date": "2026-10-26",
					"bill_no": "165847",
				},
				"items": [
					{"item_name": "Galaxy Strawberry", "qty": 1, "rate": 3.81, "amount": 3.81},
				],
			},
			"validation": {
				"errors": [
					{"field": "customer", "message": 'Required field "Customer" is missing'},
					{"field": "item_code", "message": 'Row 1 — Required field "Item" is missing'},
				],
				"warnings": [],
				"missing_masters": [],
			},
		}
		header_in = extracted["extracted_data"]["header"]
		validation = extracted["validation"]
		gaps = gaps_from_validation(validation, "Sales Invoice")
		writes = writes_from_extract(header_in, validation, doctype="Sales Invoice")
		self.assertNotIn("f.customer", gaps)
		self.assertIn("customer", [row["field"] for row in writes])
		self.assertIn("f.customer", gaps_from_validation(validation))
		header, items = keep_known_fields(
			extracted["extracted_data"]["header"],
			extracted["extracted_data"]["items"],
			{"customer", "posting_date", "currency"},
			{"item_name", "qty", "rate", "amount"},
		)
		self.assertNotIn("supplier", header)
		self.assertNotIn("bill_no", header)
		self.assertEqual(items[0]["item_name"], "Galaxy Strawberry")
		self.assertNotIn("uom", items[0])


DUBAI_FRESH = """
Dubai Fresh Fruits & Vegetables Trading                                                                            TAX INVOICE
LLC
Shop 41, Al Aweer Fruit & Vegetable Market, Dubai, UAE                                                             Invoice No: DFV/26/7712
Tel: +971 4 320 1177                                                                                                Invoice Date: 08/10/2026
TRN: 100583920600003                                                                                                   Due Date: 15/10/2026
Bill To
Olive Grove Kitchen LLC
TRN: 100512847300003
#    Description                                                   Qty         UOM           Rate     Taxable Amt      VAT 5%              Total
1    Tomatoes (Jordan)                                             40            Kg          4.25           170.00         8.50          178.50
2    Onion Red (India)                                             50            Kg          2.10           105.00         5.25          110.25
3    Lettuce Iceberg                                               30           Pcs          3.50           105.00         5.25          110.25
4    Lemon (Egypt)                                                 20            Kg          5.75           115.00         5.75          120.75
5    Fresh Coriander                                               15        Bunch           1.50            22.50         1.12           23.62
6    Avocado Hass                                                  10           Box         62.00           620.00       31.00           651.00
                                                                               Total Taxable Amount                                 1,137.50
                                                                               VAT @ 5%                                                 56.87
                                                                               Grand Total (AED)                                   1,194.37
"""

FACILITY = """
Emirates Facility Services LLC                                                                                       TAX INVOICE
Office 1104, Business Bay Tower B, Dubai, UAE                                                                       Invoice No: EFS-0926-118
Invoice Date: 30/09/2026
TRN: 100792154300003                                                                                                      Due Date: 30/10/2026
Bill To
Al Madina Hypermarket LLC
TRN: 100398765400003
#    Description                                                     Qty         UOM           Rate     Taxable Amt       VAT 5%              Total
1    AC preventive maintenance - September 2026 (store and           1         Month       4,800.00         4,800.00       240.00         5,040.00
     warehouse)
2    Deep cleaning - cold storage rooms                              2           Visit     1,250.00         2,500.00       125.00         2,625.00
3    Pest control service                                            1           Visit       650.00           650.00        32.50           682.50
4    Replacement filters (call-out)                                  12           Nos         45.00           540.00        27.00           567.00
                                                                                 Total Taxable Amount                                  8,490.00
                                                                                 VAT @ 5%                                                 424.50
                                                                                 Grand Total (AED)                                    8,914.50
"""

KHALEJ = """
                                                          TAX INVOICE
        Al Khaleej Office Supplies LLC | Shop 6, Al Karama Commercial Complex, Dubai, UAE | Tel: +971 4 337 5520 | TRN:
                                                                100419306800003
Customer                                                                               Invoice No: AKOS-INV-20931
Gulfline General Trading LLC                                                           Invoice Date: 08/10/2026
TRN: 100274639100003                                                                   Due Date: 07/11/2026
#    Item Code            Description                                  Qty        UOM            Rate     Taxable Amt       VAT 5%             Total
1    ST-A4-500            A4 Copy Paper 80gsm (Ream 500)               40        Ream           18.50           740.00        37.00          777.00
2    TN-HP-85A            HP 85A Toner Cartridge (Compatible)          6           Nos        145.00            870.00        43.50          913.50
3    ST-FILE-LA           Lever Arch File A4                           25          Nos           9.75           243.75        12.19          255.94
4    ST-PEN-BL            Ball Pen Blue (Box of 50)                    4           Box          32.00           128.00         6.40          134.40
                                                                                  Total Taxable Amount                                  1,981.75
                                                                                  VAT @ 5%                                                  99.09
                                                                                  Grand Total (AED)                                    2,080.84
"""

GOLD = """
EMIRATES GOLD TRADING LLC
Shop 14, Gold Souk, Deira, Dubai, United Arab Emirates
Tel +971 4 225 7710   |   TRN: 100234567800003
TAX INVOICE
Bill To                                                         Invoice No: EGT/2026/0934
Al Noor Jewellers LLC                                           Invoice Date: 29-Sep-2026
TRN: 100456789000003                                            Due Date: 29-Oct-2026
Item Code           Description                                           Qty                Rate        Amount (AED)
GN-22K-02           22K Gold Necklace (2 g)                                10              300.00               3,000.00
DR-18K-2CT          Diamond Ring 18K (2 ct)                                  5             500.00               2,500.00
PKG-BOX             Jewellery Packaging & Gift Box                           1             100.00                 100.00
                                                                                         Subtotal               5,600.00
                                                                                          VAT 5%                  280.00
                                                                                     TOTAL AED                  5,880.00
"""


class TestPurchaseInvoiceLayouts(unittest.TestCase):
	def _read(self, text: str, items: list | None = None) -> tuple[dict, list]:
		from taxmate.idp.masters import salvage_from_ocr_text

		extracted = {
			"success": True,
			"ocr_text": text,
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"supplier": "Dubai Fresh Fruits & Vegetables Trading"} if "Dubai Fresh" in text else {},
				"items": items
				or [
					{"item_name": "Tomatoes (Jordan) 40 Kg 4.25", "qty": 170, "rate": 8.5, "amount": 178.5},
					{"item_name": "Onion Red (India) 50 Kg 2.10", "qty": 105, "rate": 5.25, "amount": 110.25},
				],
			},
		}
		salvage_from_ocr_text(extracted, text)
		data = extracted["extracted_data"]
		return data["header"], data["items"]

	def test_produce_invoice_keeps_qty_uom_and_footer_vat(self):
		header, items = self._read(DUBAI_FRESH)
		self.assertEqual(header["supplier"], "Dubai Fresh Fruits & Vegetables Trading LLC")
		self.assertEqual(header["tax_id"], "100583920600003")
		self.assertEqual(header["bill_no"], "DFV/26/7712")
		self.assertEqual(len(items), 6)
		self.assertEqual(items[0]["item_name"], "Tomatoes (Jordan)")
		self.assertEqual(items[0]["qty"], 40)
		self.assertEqual(items[0]["uom"], "Kg")
		self.assertEqual(items[0]["rate"], 4.25)
		self.assertEqual(items[0]["amount"], 170)
		self.assertEqual(items[4]["uom"], "Bunch")
		self.assertEqual(items[5]["qty"], 10)
		self.assertEqual(items[5]["uom"], "Box")
		self.assertEqual(header["net_total"], 1137.50)
		self.assertEqual(header["tax_total"], 56.87)
		self.assertEqual(header["grand_total"], 1194.37)

	def test_wrapped_service_line_stays_one_item(self):
		header, items = self._read(FACILITY, items=[])
		self.assertEqual(header["supplier"], "Emirates Facility Services LLC")
		self.assertEqual(header["bill_no"], "EFS-0926-118")
		self.assertEqual(len(items), 4)
		from taxmate.idp.masters import promote_unresolved_items

		promote_unresolved_items(items)
		self.assertIn("warehouse", items[0]["item_name"])
		self.assertEqual(items[0]["qty"], 1)
		self.assertEqual(items[0]["uom"], "Month")
		self.assertEqual(items[0]["rate"], 4800)
		self.assertEqual(items[0]["amount"], 4800)
		self.assertEqual(items[1]["qty"], 2)
		self.assertEqual(items[1]["uom"], "Visit")
		self.assertEqual(header["tax_total"], 424.50)
		self.assertEqual(header["grand_total"], 8914.50)

	def test_coded_lines_without_a_discount_column(self):
		header, items = self._read(KHALEJ, items=[])
		self.assertEqual(header["supplier"], "Al Khaleej Office Supplies LLC")
		self.assertEqual(header["tax_id"], "100419306800003")
		self.assertEqual(header["bill_no"], "AKOS-INV-20931")
		self.assertEqual(items[0]["item_code"], "ST-A4-500")
		self.assertEqual(items[0]["qty"], 40)
		self.assertEqual(items[0]["uom"], "Ream")
		self.assertEqual(items[0]["rate"], 18.50)
		self.assertEqual(items[0]["amount"], 740)
		self.assertEqual(items[1]["item_code"], "TN-HP-85A")
		self.assertEqual(header["tax_total"], 99.09)
		self.assertNotEqual(header["tax_id"], "100274639100003")

	def test_gold_invoice_reads_code_qty_rate_and_month_date(self):
		header, items = self._read(GOLD, items=[{"item_name": "EGT/2026/0934", "qty": 1, "rate": 5600, "amount": 5600}])
		self.assertEqual(header["supplier"], "EMIRATES GOLD TRADING LLC")
		self.assertEqual(header["tax_id"], "100234567800003")
		self.assertEqual(header["bill_no"], "EGT/2026/0934")
		self.assertEqual(header["posting_date"], "2026-09-29")
		self.assertEqual(header["due_date"], "2026-10-29")
		self.assertEqual(len(items), 3)
		self.assertEqual(items[0]["item_code"], "GN-22K-02")
		self.assertEqual(items[0]["qty"], 10)
		self.assertEqual(items[0]["rate"], 300)
		self.assertEqual(items[0]["amount"], 3000)
		self.assertEqual(items[2]["item_code"], "PKG-BOX")
		self.assertEqual(items[2]["qty"], 1)
		self.assertEqual(header["net_total"], 5600)
		self.assertEqual(header["tax_total"], 280)
		self.assertEqual(header["grand_total"], 5880)

	def test_printed_date_is_kept_and_line_discount_becomes_a_net_discount(self):
		from taxmate.idp.masters import fold_printed_discounts, keep_supplier_invoice_date

		header = {"posting_date": "2026-10-09", "due_date": "2026-11-08"}
		items = [
			{"qty": 400, "rate": 5.75, "discount_amount": 115, "amount": 2185},
			{"qty": 250, "rate": 4.25, "amount": 1062.5},
		]
		keep_supplier_invoice_date(header, "Purchase Invoice")
		fold_printed_discounts(header, items)
		self.assertEqual(header["set_posting_time"], 1)
		self.assertEqual(header["bill_date"], "2026-10-09")
		self.assertEqual(header["discount_amount"], 115)
		self.assertEqual(header["apply_discount_on"], "Net Total")
		self.assertNotIn("discount_amount", items[0])
		self.assertEqual(items[0]["rate"], 5.75)


class TestScanCreate(unittest.TestCase):
	def _clerk(self):
		import frappe

		email = frappe.db.get_value(
			"User",
			{"enabled": 1, "name": ["not in", ["Administrator", "Guest"]]},
			"name",
		)
		self.assertTrue(email)
		return email

	def test_clerk_who_can_create_the_invoice_can_store_the_scan(self):
		import frappe

		from taxmate.idp.scan import persist_scan

		email = self._clerk()
		real = frappe.has_permission
		real_roles = frappe.get_roles
		frappe.get_roles = lambda user=None: ["Accounts User"]

		def invoice_only(doctype, ptype="read", *args, **kwargs):
			if doctype == "IDP Document Log":
				return False
			if doctype == "Purchase Invoice" and ptype == "create":
				return True
			return real(doctype, ptype, *args, **kwargs)

		frappe.set_user(email)
		frappe.has_permission = invoice_only
		name = None
		try:
			name = persist_scan(
				file_url="/private/files/clerk-scan-test.pdf",
				target_doctype="Purchase Invoice",
				extracted={},
				file_sha256_hex=None,
			)
			self.assertTrue(frappe.db.exists("IDP Document Log", name))
		finally:
			frappe.has_permission = real
			frappe.get_roles = real_roles
			frappe.set_user("Administrator")
			if name:
				frappe.db.delete("IDP Document Log", {"name": name})

	def test_a_scan_cannot_target_an_unrelated_doctype(self):
		import frappe

		from taxmate.idp.scan import persist_scan

		with self.assertRaises(frappe.PermissionError):
			persist_scan(
				file_url="/private/files/clerk-scan-test.pdf",
				target_doctype="User",
				extracted={},
				file_sha256_hex=None,
			)

	def test_a_user_who_cannot_create_the_invoice_cannot_store_the_scan(self):
		import frappe

		from taxmate.idp.scan import persist_scan

		email = self._clerk()
		real = frappe.has_permission
		real_roles = frappe.get_roles
		frappe.set_user(email)
		frappe.get_roles = lambda user=None: ["Accounts User"]
		frappe.has_permission = lambda *args, **kwargs: False
		try:
			with self.assertRaises(frappe.PermissionError):
				persist_scan(
					file_url="/private/files/clerk-scan-test.pdf",
					target_doctype="Purchase Invoice",
					extracted={},
					file_sha256_hex=None,
				)
		finally:
			frappe.has_permission = real
			frappe.get_roles = real_roles
			frappe.set_user("Administrator")

	def test_a_blank_page_is_read_from_the_image(self):
		from idp.extractors.extractor import PDFExtractor
		from idp.extractors import llm_vision

		extractor = PDFExtractor()
		extractor._extract_text_pypdf = lambda path: ""
		extractor._get_page_count = lambda path: 1
		original = llm_vision.read_pages
		llm_vision.read_pages = lambda path: "EMIRATES GOLD TRADING LLC\nTRN 100234567800003"
		try:
			extraction = extractor.extract("/tmp/blank.pdf")
		finally:
			llm_vision.read_pages = original
		self.assertIn("EMIRATES GOLD TRADING LLC", extraction.text)

	def test_a_text_invoice_is_not_sent_to_the_model(self):
		from idp.extractors.extractor import PDFExtractor
		from idp.extractors import llm_vision

		extractor = PDFExtractor()
		extractor._extract_text_pypdf = lambda path: "TAX INVOICE " * 40
		extractor._get_page_count = lambda path: 1
		calls = []
		original = llm_vision.read_pages
		llm_vision.read_pages = lambda path: calls.append(path)
		try:
			extraction = extractor.extract("/tmp/digital.pdf")
		finally:
			llm_vision.read_pages = original
		self.assertEqual(calls, [])
		self.assertIn("TAX INVOICE", extraction.text)

	def test_claude_and_openai_receive_their_own_image_blocks(self):
		from idp.extractors.llm_vision import image_content as _image_content

		class AnthropicProvider:
			pass

		class OpenAIProvider:
			pass

		path = "/tmp/taxmate-vision-block.png"
		with open(path, "wb") as handle:
			handle.write(b"\x89PNG\r\n")
		try:
			claude = _image_content(AnthropicProvider(), path, "read")
			openai = _image_content(OpenAIProvider(), path, "read")
		finally:
			import os

			os.remove(path)
		self.assertEqual(claude[0]["type"], "image")
		self.assertEqual(claude[0]["source"]["media_type"], "image/png")
		self.assertEqual(openai[1]["type"], "image_url")
		self.assertTrue(openai[1]["image_url"]["url"].startswith("data:image/png;base64,"))
