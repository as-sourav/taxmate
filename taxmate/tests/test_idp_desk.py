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
		self.assertEqual(review["items"], [{"label": "Desk"}])
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
