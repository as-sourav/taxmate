"""PINT-AE (Peppol UAE billing) payload builder.

Maps the validated transaction model from ``UAETransactionData`` onto a
UBL-2.1-aligned JSON structure covering the PINT-AE mandatory business
terms, including UAE-specific BTAE fields (transaction type code, AED
tax-currency amounts, FZ beneficiary).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from taxmate.uae_e_invoicing.constants import (
	AED_CURRENCY,
	PINT_AE_CUSTOMIZATION_ID,
	PINT_AE_PROFILE_ID,
	credit_note_reason_code,
)
from taxmate.uae_e_invoicing.utils.transaction_data import UAETransactionData


def build_pint_ae_payload(doc, doc_uuid: str | None = None) -> tuple[str, dict[str, Any]]:
	"""Return (uuid, payload_dict) for a Sales Invoice."""
	data = UAETransactionData(doc).get_data()
	return build_payload_from_data(data, doc_uuid=doc_uuid)


def build_payload_from_data(data: dict[str, Any], doc_uuid: str | None = None) -> tuple[str, dict[str, Any]]:
	"""Map a validated transaction-data dict onto the PINT-AE structure.

	``doc_uuid`` reuses an existing fiscal document UUID on retry so the ASP
	does not treat the resubmission as a new invoice.
	"""
	doc_uuid = doc_uuid or str(uuid.uuid4())

	payload: dict[str, Any] = {
		"CustomizationID": PINT_AE_CUSTOMIZATION_ID,
		"ProfileID": PINT_AE_PROFILE_ID,
		"ID": data["invoice_number"],
		"UUID": doc_uuid,
		"IssueDate": data["issue_date"],
		"InvoiceTypeCode": data["document_type_code"],
		"DocumentCurrencyCode": data["currency"],
		"BuyerReference": data["buyer_reference"],
		# BTAE-02: UAE invoice transaction type bit-flag code
		"InvoiceTransactionTypeCode": data["transaction_type_code"],
		"AccountingSupplierParty": {"Party": _party(data["supplier"])},
		"AccountingCustomerParty": {"Party": _party(data["customer"])},
		"InvoiceLine": [_invoice_line(line, data["currency"]) for line in data["lines"]],
		"TaxTotal": _tax_totals(data),
		"LegalMonetaryTotal": _legal_monetary_total(data),
	}

	if data["issue_time"]:
		payload["IssueTime"] = data["issue_time"]
	if data["due_date"]:
		payload["DueDate"] = data["due_date"]
	if data["currency"] != AED_CURRENCY:
		payload["TaxCurrencyCode"] = data["tax_currency"]
		payload["TaxExchangeRate"] = {
			"SourceCurrencyCode": data["currency"],
			"TargetCurrencyCode": AED_CURRENCY,
			"CalculationRate": data["exchange_rate"],
		}
	if data["payment_means"]:
		payload["PaymentMeans"] = [_payment_means(entry) for entry in data["payment_means"]]

	period = data.get("invoice_period")
	if period and (period.get("start_date") or period.get("end_date")):
		invoice_period: dict[str, Any] = {}
		if period.get("start_date"):
			invoice_period["StartDate"] = period["start_date"]
		if period.get("end_date"):
			invoice_period["EndDate"] = period["end_date"]
		if period.get("description_code"):
			invoice_period["DescriptionCode"] = period["description_code"]
		payload["InvoicePeriod"] = invoice_period

	# IBR-151-AE: a VAT point date must be before the issue date. The same day
	# is the normal ERPNext case and must be omitted.
	tax_point = data.get("tax_point_date")
	if tax_point and data.get("issue_date") and str(tax_point) < str(data["issue_date"]):
		payload["TaxPointDate"] = tax_point

	delivery = _postal_address((data.get("customer") or {}).get("address"))
	if delivery:
		payload["Delivery"] = {"DeliveryLocation": {"Address": delivery}}

	doc_allowance = data.get("document_allowance")
	if doc_allowance:
		payload["AllowanceCharge"] = [
			{
				"ChargeIndicator": False,
				"AllowanceChargeReason": doc_allowance["reason"],
				"Amount": {
					"value": doc_allowance["amount"],
					"currencyID": data["currency"],
				},
			}
		]

	# IBT-022: invoice remarks. The credit-note reason is CreditNoteReasonCode, not a note.
	notes = [note for note in (data.get("notes") or []) if note]

	credit_note = data.get("credit_note")
	if credit_note:
		if credit_note.get("reference"):
			document_reference: dict[str, Any] = {"ID": credit_note["reference"]["id"]}
			# IssueDate is unknown for invoices issued outside this system
			if credit_note["reference"].get("issue_date"):
				document_reference["IssueDate"] = credit_note["reference"]["issue_date"]
			payload["BillingReference"] = {"InvoiceDocumentReference": document_reference}
		reason_code = credit_note_reason_code(credit_note.get("reason"))
		if reason_code:
			# BTAE-03. Mapped to extensions.ae_creditNoteReasonCode. Not a free-text note.
			payload["CreditNoteReasonCode"] = reason_code

	if notes:
		payload["Note"] = notes[0] if len(notes) == 1 else notes

	if data.get("principal_trn"):
		# BTAE-14. Own key so it is not the seller or buyer VAT identifier (IBR-176-AE).
		payload["PrincipalTRN"] = data["principal_trn"]

	fz_beneficiary = data["customer"].get("fz_beneficiary_id")
	if fz_beneficiary:
		# BTAE-01: Free Zone beneficiary identifier
		payload["FZBeneficiaryID"] = fz_beneficiary

	if data.get("vat_emirate"):
		payload["VATEmirate"] = data["vat_emirate"]

	return doc_uuid, payload


def payload_to_json(payload: dict[str, Any]) -> str:
	return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------


def _postal_address(address: dict[str, Any] | None) -> dict[str, Any] | None:
	if not address or not address.get("line1"):
		return None
	postal: dict[str, Any] = {
		"StreetName": address.get("line1"),
		"CityName": address.get("city"),
		"Country": {"IdentificationCode": address.get("country_code")},
	}
	if address.get("line2"):
		postal["AdditionalStreetName"] = address["line2"]
	if address.get("postal_zone"):
		postal["PostalZone"] = address["postal_zone"]
	if address.get("emirate_code"):
		postal["CountrySubentityCode"] = address["emirate_code"]
	return postal


# IBR-173-AE checks CompanyID/@schemeAgencyID, not the English label.
_LEGAL_REGISTRATION_SCHEMES = {
	"CL": "TL",
	"CRN": "TL",
	"TL": "TL",
	"OTH": "TL",
	"Commercial/Trade license": "TL",
	"Emirates ID": "EID",
	"EID": "EID",
	"Passport": "PAS",
	"PAS": "PAS",
	"Cabinet decision": "CD",
	"CD": "CD",
}

# Complyance paymentMeansCode enum. The mapper emits the UNCL4461 code.
_GETS_PAYMENT_MEANS = {
	"1": "INSTRUMENT_NOT_DEFINED",
	"10": "IN_CASH",
	"20": "CHEQUE",
	"30": "CREDIT_TRANSFER",
	"42": "CREDIT_TRANSFER",
	"48": "CREDIT_CARD",
	"49": "DIRECT_DEBIT",
	"54": "CREDIT_CARD",
	"55": "DEBIT_CARD",
	"58": "CREDIT_TRANSFER",
}


def _legal_registration_scheme(raw: str | None) -> str:
	return _LEGAL_REGISTRATION_SCHEMES.get((raw or "").strip(), "TL")


def _party(party: dict[str, Any]) -> dict[str, Any]:
	result: dict[str, Any] = {
		"PartyName": {"Name": party["name"]},
		"PartyLegalEntity": {
			"RegistrationName": party["name"],
		},
	}

	if party.get("peppol_id"):
		result["EndpointID"] = {"schemeID": "0235", "value": party["peppol_id"]}

	legal_id = party.get("legal_registration_identifier") or party.get("trade_license_number")
	if legal_id:
		scheme = _legal_registration_scheme(party.get("legal_registration_identifier_type"))
		company_id = {
			"schemeID": scheme,
			"schemeAgencyID": scheme,
			"value": legal_id,
		}
		# BTAE-11 / BTAE-12. Required when the registration type is a trade licence.
		if party.get("licence_authority"):
			company_id["schemeAgencyName"] = party["licence_authority"]
		result["PartyLegalEntity"]["CompanyID"] = company_id

	if party.get("trn"):
		result["PartyTaxScheme"] = {
			"CompanyID": party["trn"],
			"TaxScheme": {"ID": "VAT"},
		}
		from taxmate.uae_e_invoicing.utils.mandate import vat_group_tin

		group_tin = party.get("vat_group_tin") or vat_group_tin(party["trn"])
		if group_tin:
			result["PartyIdentification"] = [{"ID": {"schemeID": "AE:VAT-GROUP", "value": group_tin}}]

	postal = _postal_address(party.get("address"))
	if postal:
		result["PostalAddress"] = postal

	contact = party.get("contact") or {}
	if any(contact.values()):
		result["Contact"] = {
			key: value
			for key, value in (
				("Name", contact.get("name")),
				("ElectronicMail", contact.get("email")),
				("Telephone", contact.get("phone")),
			)
			if value
		}

	return result


def _payment_means(entry: dict[str, Any]) -> dict[str, Any]:
	result: dict[str, Any] = {
		# GETS enum. Complyance emits the matching UNCL4461 code (IBR-CL-16).
		"PaymentMeansCode": {"value": _GETS_PAYMENT_MEANS.get(str(entry["code"]), entry["code"])},
	}
	account = entry.get("payee_financial_account")
	if account:
		result["PayeeFinancialAccount"] = {
			"ID": {"schemeID": account.get("scheme"), "value": account.get("id")},
			"Name": account.get("name"),
		}
		if account.get("branch"):
			result["PayeeFinancialAccount"]["FinancialInstitutionBranch"] = {"ID": account["branch"]}
	card = entry.get("card_account")
	if card:
		result["CardAccount"] = {"HolderName": card.get("holder_name")}
	return result


def _invoice_line(line: dict[str, Any], currency: str) -> dict[str, Any]:
	tax_category: dict[str, Any] = {
		"ID": line["vat_category_code"],
		"Percent": line["tax_rate"],
		"TaxScheme": {"ID": "VAT"},
	}
	if line.get("exemption_reason"):
		tax_category["TaxExemptionReason"] = line["exemption_reason"]

	result: dict[str, Any] = {
		"ID": line["id"],
		"InvoicedQuantity": {"value": line["qty"], "unitCode": line["uom"]},
		"LineExtensionAmount": {"value": line["net_amount"], "currencyID": currency},
		# BTAE-10: line amount payable in AED
		"LineExtensionAmountAED": line["base_net_amount"],
		"Item": {
			"Name": line["item_name"] or line["item_code"],
			"Description": line["description"],
			"ClassifiedTaxCategory": tax_category,
		},
		"Price": {
			"PriceAmount": {"value": line["rate"], "currencyID": currency},
			"GrossPrice": {"value": line["rate"], "currencyID": currency},
		},
		"TaxTotal": {
			"TaxAmount": {"value": line["tax_amount"], "currencyID": currency},
			# BTAE-08: VAT line amount in AED
			"TaxAmountAED": line["base_tax_amount"],
		},
	}

	# IBR-184-AE / IBR-185-AE: commodity classification scheme must be HS.
	# A service accounting code is a different identifier and must not use listID SAC.
	if line.get("hs_code"):
		# Repeating UBL element. Complyance maps the array path, and listID must be HS.
		result["Item"]["CommodityClassification"] = [
			{"ItemClassificationCode": {"listID": "HS", "value": line["hs_code"]}}
		]
	if line.get("sac_code"):
		result["Item"]["ServiceAccountingCode"] = {"schemeID": "SAC", "value": line["sac_code"]}
	if line.get("uae_item_type"):
		result["Item"]["ItemType"] = line["uae_item_type"]
	# FTA reverse-charge category. Omitted on ordinary tax invoices.
	if line.get("rcm_nature"):
		result["Item"]["RCMType"] = line["rcm_nature"]
	if line.get("item_code"):
		result["Item"]["SellersItemIdentification"] = {"ID": line["item_code"]}
	# IBT-157. Scheme is an ISO 6523 ICD (0160 = GS1 GTIN). Never derived from the HS code.
	if line.get("standard_item_id") and line.get("standard_item_scheme"):
		result["Item"]["StandardItemIdentification"] = {
			"ID": {"schemeID": line["standard_item_scheme"], "value": line["standard_item_id"]}
		}

	if line.get("discount_amount") and line.get("price_before_discount") is not None:
		# PriceAmount must be the pre-discount unit price when AllowanceCharge is present
		result["Price"] = {
			"PriceAmount": {
				"value": line["price_before_discount"],
				"currencyID": currency,
			},
			"GrossPrice": {
				"value": line["price_before_discount"],
				"currencyID": currency,
			},
		}
		result["AllowanceCharge"] = {
			"ChargeIndicator": False,
			"Amount": {"value": abs(float(line["discount_amount"])), "currencyID": currency},
			"AllowanceChargeReason": "Discount",
		}

	return result


def _tax_totals(data: dict[str, Any]) -> list[dict[str, Any]]:
	currency = data["currency"]
	totals = data["totals"]

	subtotals = []
	for entry in data["tax_breakdown"]:
		category: dict[str, Any] = {
			"ID": entry["vat_category_code"],
			"Percent": entry["tax_rate"],
			"TaxScheme": {"ID": "VAT"},
		}
		if entry.get("exemption_reason"):
			category["TaxExemptionReason"] = entry["exemption_reason"]
		subtotals.append(
			{
				"TaxableAmount": {"value": entry["taxable_amount"], "currencyID": currency},
				"TaxAmount": {"value": entry["tax_amount"], "currencyID": currency},
				"TaxCategory": category,
			}
		)

	tax_totals = [
		{
			"TaxAmount": {"value": totals["tax_total_amount"], "currencyID": currency},
			"TaxSubtotal": subtotals,
		}
	]

	# Second TaxTotal in AED (tax accounting currency, IBT-110/111 + BTAE-08)
	if currency != AED_CURRENCY:
		tax_totals.append(
			{
				"TaxAmount": {
					"value": totals["base_tax_total_amount"],
					"currencyID": AED_CURRENCY,
				}
			}
		)

	return tax_totals


def _legal_monetary_total(data: dict[str, Any]) -> dict[str, Any]:
	currency = data["currency"]
	totals = data["totals"]

	def amount(value):
		return {"value": value, "currencyID": currency}

	result = {
		"LineExtensionAmount": amount(totals["line_extension_amount"]),
		"TaxExclusiveAmount": amount(totals["tax_exclusive_amount"]),
		"TaxInclusiveAmount": amount(totals["tax_inclusive_amount"]),
		"AllowanceTotalAmount": amount(totals["allowance_total_amount"]),
		"ChargeTotalAmount": amount(totals["charge_total_amount"]),
		"PrepaidAmount": amount(totals["prepaid_amount"]),
		"PayableRoundingAmount": amount(totals["payable_rounding_amount"]),
		"PayableAmount": amount(totals["payable_amount"]),
	}

	# BTAE-20: gross amount payable in AED
	if currency != AED_CURRENCY:
		result["TaxInclusiveAmountAED"] = totals["base_tax_inclusive_amount"]
		result["PayableAmountAED"] = totals["base_payable_amount"]

	return result
