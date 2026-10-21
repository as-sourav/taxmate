"""Unit tests for the UAE e-invoicing engine (pure functions, no fixtures).

Run: bench --site <site> run-tests --module taxmate.tests.test_uae_e_invoicing
"""

import unittest
from decimal import Decimal

from taxmate.uae_e_invoicing.constants import (
	APPROVED_PAYMENT_MEANS,
	PINT_AE_CUSTOMIZATION_ID,
	SALES_DOCUMENT_TYPE_CODES,
	VAT_CATEGORY_CODES,
)
from taxmate.uae_e_invoicing.utils.pint_ae import build_payload_from_data
from taxmate.uae_e_invoicing.utils.rounding import r2, r6


def golden_transaction_data() -> dict:
	"""A minimal valid AED transaction-data dict (contract of UAETransactionData)."""
	return {
		"invoice_number": "SINV-0001",
		"issue_date": "2026-08-27",
		"issue_time": "10:30:00",
		"due_date": "2026-09-26",
		"document_type_code": "380",
		"currency": "AED",
		"tax_currency": "AED",
		"exchange_rate": 1,
		"buyer_reference": "PO-778",
		"transaction_type_code": "00000000",
		"vat_emirate": "DXB",
		"credit_note": None,
		"invoice_period": {
			"start_date": "2026-08-27",
			"end_date": "2026-09-26",
			"description_code": "MTH",
		},
		"tax_point_date": "2026-08-27",
		"notes": [],
		"document_allowance": None,
		"supplier": {
			"name": "Golden Trading LLC",
			"trn": "100000000000003",
			"peppol_id": "0235:100000000000003",
			"legal_registration_identifier": "CN-1234567",
			"legal_registration_identifier_type": "CL",
			"address": {
				"line1": "Sheikh Zayed Road",
				"city": "Dubai",
				"country_code": "AE",
				"emirate_code": "DXB",
			},
			"contact": {"email": "billing@golden.example", "phone": "+97140000000"},
		},
		"customer": {
			"name": "Buyer FZ-LLC",
			"trn": "100000000000004",
			"peppol_id": None,
			"fz_beneficiary_id": None,
			"address": {
				"line1": "Airport Road",
				"city": "Abu Dhabi",
				"country_code": "AE",
				"emirate_code": "AUH",
			},
			"contact": {},
		},
		"lines": [
			{
				"id": 1,
				"item_code": "SRV-001",
				"item_name": "Consulting",
				"description": "Consulting services",
				"qty": 2,
				"uom": "C62",
				"rate": 500.0,
				"net_amount": 1000.0,
				"base_net_amount": 1000.0,
				"tax_rate": 5.0,
				"tax_amount": 50.0,
				"base_tax_amount": 50.0,
				"vat_category_code": "S",
				"uae_item_type": "Service",
				"sac_code": "998311",
				"hs_code": None,
				"discount_amount": 0,
				"exemption_reason": None,
				"rcm_nature": None,
			},
			{
				"id": 2,
				"item_code": "EXP-001",
				"item_name": "Export Goods",
				"description": "Zero-rated export",
				"qty": 1,
				"uom": "C62",
				"rate": 400.0,
				"net_amount": 400.0,
				"base_net_amount": 400.0,
				"tax_rate": 0.0,
				"tax_amount": 0.0,
				"base_tax_amount": 0.0,
				"vat_category_code": "Z",
				"uae_item_type": "Goods",
				"sac_code": None,
				"hs_code": "85171200",
				"discount_amount": 0,
				"exemption_reason": "Zero-rated export of goods",
				"rcm_nature": None,
			},
		],
		"tax_breakdown": [
			{
				"vat_category_code": "S",
				"tax_rate": 5.0,
				"taxable_amount": 1000.0,
				"tax_amount": 50.0,
				"exemption_reason": None,
				"rcm_nature": None,
			},
			{
				"vat_category_code": "Z",
				"tax_rate": 0.0,
				"taxable_amount": 400.0,
				"tax_amount": 0.0,
				"exemption_reason": "Zero-rated export of goods",
				"rcm_nature": None,
			},
		],
		"totals": {
			"line_extension_amount": 1400.0,
			"tax_exclusive_amount": 1400.0,
			"tax_inclusive_amount": 1450.0,
			"allowance_total_amount": 0.0,
			"charge_total_amount": 0.0,
			"prepaid_amount": 0.0,
			"payable_rounding_amount": 0.0,
			"payable_amount": 1450.0,
			"tax_total_amount": 50.0,
			"base_tax_total_amount": 50.0,
			"base_tax_inclusive_amount": 1450.0,
			"base_payable_amount": 1450.0,
		},
		"payment_means": [
			{
				"code": "30",
				"name": "Credit transfer",
				"payee_financial_account": {
					"scheme": "IBAN",
					"id": "AE070331234567890123456",
					"name": "Operating Account",
					"branch": None,
				},
				"card_account": None,
			}
		],
	}


class TestRounding(unittest.TestCase):
	def test_half_up_at_two_places(self):
		self.assertEqual(r2("2.675"), 2.68)
		self.assertEqual(r2("2.665"), 2.67)
		self.assertEqual(r2("-2.675"), -2.68)

	def test_half_up_at_six_places(self):
		self.assertEqual(r6("0.1234565"), 0.123457)

	def test_none_is_zero(self):
		self.assertEqual(r2(None), 0.0)


class TestCodeLists(unittest.TestCase):
	def test_vat_category_codes(self):
		self.assertEqual(set(VAT_CATEGORY_CODES.values()), {"S", "Z", "E", "O", "AE", "N"})

	def test_payment_means_codes_are_uncl4461_subset(self):
		for code in APPROVED_PAYMENT_MEANS:
			self.assertTrue(code.isdigit(), f"non-numeric payment means code: {code}")

	def test_sales_document_type_codes(self):
		self.assertEqual(set(SALES_DOCUMENT_TYPE_CODES), {"380", "381", "480", "81"})


class TestPintAePayload(unittest.TestCase):
	def setUp(self):
		self.data = golden_transaction_data()
		self.uuid, self.payload = build_payload_from_data(self.data)

	def test_header(self):
		self.assertEqual(self.payload["CustomizationID"], PINT_AE_CUSTOMIZATION_ID)
		self.assertEqual(self.payload["ID"], "SINV-0001")
		self.assertEqual(self.payload["UUID"], self.uuid)
		self.assertEqual(self.payload["InvoiceTypeCode"], "380")
		self.assertEqual(self.payload["InvoiceTransactionTypeCode"], "00000000")
		self.assertEqual(self.payload["DocumentCurrencyCode"], "AED")
		self.assertEqual(self.payload["IssueTime"], "10:30:00")
		self.assertEqual(self.payload["DueDate"], "2026-09-26")
		self.assertEqual(
			self.payload["InvoicePeriod"],
			{"StartDate": "2026-08-27", "EndDate": "2026-09-26", "DescriptionCode": "MTH"},
		)
		self.assertEqual(self.payload["TaxPointDate"], "2026-08-27")
		# AED invoices must not carry a tax-currency conversion block
		self.assertNotIn("TaxCurrencyCode", self.payload)
		self.assertNotIn("TaxExchangeRate", self.payload)

	def test_parties(self):
		supplier = self.payload["AccountingSupplierParty"]["Party"]
		self.assertEqual(supplier["PartyTaxScheme"]["CompanyID"], "100000000000003")
		self.assertEqual(supplier["EndpointID"]["schemeID"], "0235")
		self.assertEqual(supplier["PostalAddress"]["CountrySubentityCode"], "DXB")
		self.assertEqual(
			supplier["PartyLegalEntity"]["CompanyID"],
			{"schemeID": "CL", "value": "CN-1234567"},
		)

		customer = self.payload["AccountingCustomerParty"]["Party"]
		self.assertEqual(customer["PostalAddress"]["Country"]["IdentificationCode"], "AE")
		self.assertNotIn("EndpointID", customer)

	def test_lines_and_classification(self):
		lines = self.payload["InvoiceLine"]
		self.assertEqual(len(lines), 2)

		services = lines[0]
		self.assertEqual(
			services["Item"]["CommodityClassification"]["ItemClassificationCode"],
			{"listID": "SAC", "value": "998311"},
		)
		self.assertEqual(services["Item"]["ClassifiedTaxCategory"]["ID"], "S")
		self.assertEqual(services["LineExtensionAmountAED"], 1000.0)

		goods = lines[1]
		self.assertEqual(
			goods["Item"]["CommodityClassification"]["ItemClassificationCode"],
			{"listID": "HS", "value": "85171200"},
		)
		self.assertEqual(
			goods["Item"]["ClassifiedTaxCategory"]["TaxExemptionReason"],
			"Zero-rated export of goods",
		)

	def test_tax_totals(self):
		tax_totals = self.payload["TaxTotal"]
		self.assertEqual(len(tax_totals), 1)  # AED invoice: single TaxTotal
		self.assertEqual(tax_totals[0]["TaxAmount"]["value"], 50.0)
		categories = {s["TaxCategory"]["ID"] for s in tax_totals[0]["TaxSubtotal"]}
		self.assertEqual(categories, {"S", "Z"})

	def test_monetary_total(self):
		total = self.payload["LegalMonetaryTotal"]
		self.assertEqual(total["LineExtensionAmount"]["value"], 1400.0)
		self.assertEqual(total["TaxInclusiveAmount"]["value"], 1450.0)
		self.assertEqual(total["PayableAmount"]["value"], 1450.0)

	def test_payment_means(self):
		means = self.payload["PaymentMeans"][0]
		self.assertEqual(means["PaymentMeansCode"]["value"], "30")
		self.assertEqual(
			means["PayeeFinancialAccount"]["ID"],
			{"schemeID": "IBAN", "value": "AE070331234567890123456"},
		)

	def test_credit_note_billing_reference(self):
		data = golden_transaction_data()
		data["document_type_code"] = "381"
		data["credit_note"] = {
			"reference": {"id": "SINV-0000", "issue_date": "2026-08-01"},
			"reason": "Goods returned",
		}
		_, payload = build_payload_from_data(data)
		self.assertEqual(payload["InvoiceTypeCode"], "381")
		self.assertEqual(payload["BillingReference"]["InvoiceDocumentReference"]["ID"], "SINV-0000")
		self.assertEqual(payload["Note"], "Goods returned")

	def test_invoice_note_ibt022(self):
		data = golden_transaction_data()
		data["notes"] = ["Summary billing for August"]
		_, payload = build_payload_from_data(data)
		self.assertEqual(payload["Note"], "Summary billing for August")

	def test_note_combines_remarks_and_credit_reason(self):
		data = golden_transaction_data()
		data["notes"] = ["Monthly summary"]
		data["credit_note"] = {"reference": None, "reason": "Goods returned"}
		_, payload = build_payload_from_data(data)
		self.assertEqual(payload["Note"], ["Monthly summary", "Goods returned"])

	def test_external_billing_reference_omits_issue_date(self):
		data = golden_transaction_data()
		data["document_type_code"] = "381"
		data["credit_note"] = {
			"reference": {"id": "LEGACY-INV-42", "issue_date": None},
			"reason": "Pricing correction",
		}
		_, payload = build_payload_from_data(data)
		reference = payload["BillingReference"]["InvoiceDocumentReference"]
		self.assertEqual(reference["ID"], "LEGACY-INV-42")
		self.assertNotIn("IssueDate", reference)

	def test_foreign_currency_carries_aed_totals(self):
		data = golden_transaction_data()
		data["currency"] = "USD"
		data["exchange_rate"] = 3.6725
		_, payload = build_payload_from_data(data)
		self.assertEqual(payload["TaxCurrencyCode"], "AED")
		self.assertEqual(payload["TaxExchangeRate"]["CalculationRate"], 3.6725)
		self.assertEqual(len(payload["TaxTotal"]), 2)
		self.assertEqual(payload["TaxTotal"][1]["TaxAmount"]["currencyID"], "AED")
		self.assertIn("PayableAmountAED", payload["LegalMonetaryTotal"])

	def test_document_allowance_charge(self):
		data = golden_transaction_data()
		# Pre-discount line extensions (1500) - allowance (100) = tax exclusive (1400)
		data["lines"][0]["net_amount"] = 1100.0
		data["lines"][0]["taxable_amount"] = 1000.0
		data["document_allowance"] = {"amount": 100.0, "reason": "Document Discount"}
		data["totals"]["line_extension_amount"] = 1500.0
		data["totals"]["allowance_total_amount"] = 100.0
		data["totals"]["tax_exclusive_amount"] = 1400.0
		data["totals"]["tax_inclusive_amount"] = 1450.0
		data["totals"]["payable_amount"] = 1450.0
		_, payload = build_payload_from_data(data)
		self.assertEqual(payload["AllowanceCharge"][0]["ChargeIndicator"], False)
		self.assertEqual(payload["AllowanceCharge"][0]["Amount"]["value"], 100.0)
		self.assertEqual(payload["LegalMonetaryTotal"]["LineExtensionAmount"]["value"], 1500.0)
		self.assertEqual(payload["LegalMonetaryTotal"]["AllowanceTotalAmount"]["value"], 100.0)
		self.assertEqual(payload["LegalMonetaryTotal"]["TaxExclusiveAmount"]["value"], 1400.0)

	def test_uuid_reuse_on_retry(self):
		data = golden_transaction_data()
		fixed = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
		uuid1, payload1 = build_payload_from_data(data, doc_uuid=fixed)
		uuid2, payload2 = build_payload_from_data(data, doc_uuid=fixed)
		self.assertEqual(uuid1, fixed)
		self.assertEqual(uuid2, fixed)
		self.assertEqual(payload1["UUID"], fixed)
		self.assertEqual(payload2["UUID"], fixed)
		fresh_uuid, _ = build_payload_from_data(data)
		self.assertNotEqual(fresh_uuid, fixed)

	def test_both_item_type_emits_hs_and_sac(self):
		data = golden_transaction_data()
		data["lines"] = [
			{
				"id": 1,
				"item_code": "BOTH-001",
				"item_name": "Mixed supply",
				"description": "Goods and service bundle",
				"qty": 1,
				"uom": "C62",
				"rate": 1000.0,
				"net_amount": 1000.0,
				"base_net_amount": 1000.0,
				"tax_rate": 5.0,
				"tax_amount": 50.0,
				"base_tax_amount": 50.0,
				"vat_category_code": "S",
				"uae_item_type": "Both",
				"sac_code": "998311",
				"hs_code": "85171200",
				"discount_amount": 0,
				"exemption_reason": None,
				"rcm_nature": None,
			}
		]
		_, payload = build_payload_from_data(data)
		classifications = payload["InvoiceLine"][0]["Item"]["CommodityClassification"]
		self.assertEqual(len(classifications), 2)
		lists = {c["ItemClassificationCode"]["listID"] for c in classifications}
		self.assertEqual(lists, {"HS", "SAC"})


class TestIbtRules(unittest.TestCase):
	"""IBG-14 / BTAE-01 checks aligned with ERPGulf, without their due-date-implies-frequency bug."""

	def test_due_date_alone_does_not_require_invoice_period(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import (
			invoice_period_is_required,
			invoice_period_validation_messages,
		)

		flags = {"deemed_supply": False, "summary_invoice": False, "continuous_supply": False}
		self.assertFalse(invoice_period_is_required(flags, None))
		self.assertFalse(invoice_period_is_required(flags, ""))
		self.assertEqual(
			invoice_period_validation_messages(flags, None, "2026-12-01", "2026-12-31", False),
			[],
		)

	def test_deemed_supply_requires_full_ibg14(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import invoice_period_validation_messages

		msgs = invoice_period_validation_messages({"deemed_supply": True}, None, None, None, False)
		self.assertEqual(len(msgs), 3)
		self.assertTrue(any("Billing Frequency" in m for m in msgs))
		self.assertTrue(any("start date" in m for m in msgs))
		self.assertTrue(any("end date" in m for m in msgs))

	def test_summary_and_continuous_still_require_period(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import invoice_period_is_required

		self.assertTrue(invoice_period_is_required({"deemed_supply": True}, None))
		self.assertTrue(invoice_period_is_required({"summary_invoice": True}, None))
		self.assertTrue(invoice_period_is_required({"continuous_supply": True}, None))

	def test_complete_deemed_period_is_valid(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import invoice_period_validation_messages

		self.assertEqual(
			invoice_period_validation_messages(
				{"deemed_supply": True}, "MTH", "2026-12-01", "2026-12-31", False
			),
			[],
		)

	def test_oth_requires_invoice_note(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import invoice_period_validation_messages

		msgs = invoice_period_validation_messages({}, "OTH", "2026-12-01", "2026-12-31", False)
		self.assertTrue(any("IBT-022" in m for m in msgs))
		self.assertEqual(
			invoice_period_validation_messages({}, "OTH", "2026-12-01", "2026-12-31", True),
			[],
		)

	def test_buyer_fz_is_required_on_ftz(self):
		from taxmate.uae_e_invoicing.utils.transaction_data import buyer_fz_validation_messages

		msgs = buyer_fz_validation_messages({"free_trade_zone": True}, None)
		self.assertEqual(len(msgs), 1)
		self.assertIn("IBR-007-ae", msgs[0])
		self.assertIn("buyer", msgs[0].lower())
		self.assertEqual(buyer_fz_validation_messages({"free_trade_zone": True}, "FZ-99"), [])
		self.assertEqual(buyer_fz_validation_messages({"free_trade_zone": False}, None), [])


class TestComplyanceUnify(unittest.TestCase):
	"""PINT-AE payload → Complyance Unify envelope. No network."""

	def test_ordinary_invoice_uses_tax_invoice(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import build_unify_request

		_, payload = build_payload_from_data(golden_transaction_data())
		body = build_unify_request(
			payload, source="taxmate:1.0", environment="sandbox", purpose="invoicing"
		)
		self.assertEqual(body["country"], "AE")
		self.assertEqual(body["environment"], "sandbox")
		self.assertEqual(body["purpose"], "invoicing")
		self.assertEqual(body["source"], "taxmate:1.0")
		self.assertEqual(body["documentType"], {"base": "tax_invoice", "modifiers": []})
		self.assertIs(body["payload"], payload)

	def test_uae_document_selections(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import document_type_for

		cases = {
			"380": ("tax_invoice", []),
			"381": ("credit_note", []),
			"480": ("tax_invoice", ["out_of_scope"]),
			"81": ("credit_note", ["out_of_scope"]),
			"389": ("tax_invoice", ["self_billed"]),
			"361": ("credit_note", ["self_billed"]),
		}
		for code, (base, modifiers) in cases.items():
			self.assertEqual(
				document_type_for({"InvoiceTypeCode": code}),
				{"base": base, "modifiers": modifiers},
			)

	def test_export_flag_adds_modifier(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import document_type_for

		doc_type = document_type_for(
			{"InvoiceTypeCode": "389", "InvoiceTransactionTypeCode": "00000001"}
		)
		self.assertEqual(doc_type["modifiers"], ["self_billed", "export"])

	def test_source_splits_on_the_last_colon(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import (
			ComplyanceSourceError,
			parse_complyance_source,
		)

		self.assertEqual(parse_complyance_source("acme-erp:1.0.0"), "acme-erp:1.0.0")
		with self.assertRaises(ComplyanceSourceError):
			parse_complyance_source("taxmate")
		with self.assertRaises(ComplyanceSourceError):
			parse_complyance_source("tax mate:1.0")

	def test_auth_header_reads_password_store_when_field_is_blank(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import ComplyanceAPI

		class Settings:
			auth_key = ""

			def get_password(self, fieldname, raise_exception=True):
				self.fieldname = fieldname
				self.raise_exception = raise_exception
				return "ak_test_key"

		settings = Settings()
		api = ComplyanceAPI.__new__(ComplyanceAPI)
		api.settings = settings
		self.assertEqual(api.get_auth_headers(), {"Authorization": "Bearer ak_test_key"})
		self.assertEqual(settings.fieldname, "auth_key")
		self.assertFalse(settings.raise_exception)

	def test_states(self):
		from taxmate.uae_e_invoicing.api_classes.complyance import taxmate_status_for_state

		self.assertEqual(taxmate_status_for_state("final_valid"), "Accepted")
		self.assertEqual(taxmate_status_for_state("final_invalid"), "Rejected")
		self.assertEqual(taxmate_status_for_state("rejected"), "Rejected")
		self.assertEqual(taxmate_status_for_state("delivery_failed"), "Submitted")
		self.assertEqual(taxmate_status_for_state("processing"), "Submitted")
		self.assertIsNone(taxmate_status_for_state(""))

	def test_map_asp_status_accepts_complyance_states(self):
		from taxmate.uae_e_invoicing.utils.e_invoice import map_asp_status

		self.assertEqual(map_asp_status("final_valid"), "Accepted")
		self.assertEqual(map_asp_status("Accepted"), "Accepted")
		self.assertEqual(map_asp_status("processing"), "Submitted")
		self.assertEqual(map_asp_status("final_invalid"), "Rejected")
		self.assertIsNone(map_asp_status(""))
