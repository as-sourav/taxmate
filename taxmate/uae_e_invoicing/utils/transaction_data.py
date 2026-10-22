"""Extract and validate PINT-AE transaction data from a Sales Invoice.

All monetary math uses Decimal with ROUND_HALF_UP per FTA guidance.
Validation raises a single consolidated error listing every violated
business rule (IBR-*) so users can fix an invoice in one pass.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from taxmate.uae.constants import UAE_COUNTRY
from taxmate.uae.validation import is_valid_uae_trn
from taxmate.uae_e_invoicing.constants import (
	AED_CURRENCY,
	APPROVED_PAYMENT_MEANS,
	BANK_TRANSFER_PAYMENT_CODES,
	BILLING_FREQUENCY_CODES,
	CARD_PAYMENT_CODES,
	DEFAULT_TRANSACTION_TYPE_CODE,
	EMIRATE_SUBDIVISION_CODES,
	INVOICE_PERIOD_REQUIRED_FLAGS,
	ITEM_TYPE_BOTH,
	ITEM_TYPE_GOODS,
	ITEM_TYPE_SERVICE,
	RCM_TYPE_CODES,
	TRANSACTION_TYPE_FLAGS,
	VAT_CATEGORY_CODES,
	credit_note_reason_code,
)
from taxmate.uae_e_invoicing.utils.rounding import r2, r6, to_decimal


def _needs_full_invoice_period(flags: dict[str, bool]) -> bool:
	return any(flags.get(name) for name in INVOICE_PERIOD_REQUIRED_FLAGS)


def invoice_period_is_required(flags: dict[str, bool], frequency: str | None) -> bool:
	"""True when IBG-14 must appear: explicit frequency or deemed / summary / continuous."""
	if (frequency or "").strip():
		return True
	return _needs_full_invoice_period(flags)


def invoice_period_validation_messages(
	flags: dict[str, bool],
	frequency: str | None,
	posting_date: date | str | None,
	due_date: date | str | None,
	has_notes: bool,
) -> list[str]:
	"""IBG-14 / IBT-022 checks. Does not require frequency merely because a due date exists."""
	msgs: list[str] = []
	freq = (frequency or "").strip()
	if freq and freq not in BILLING_FREQUENCY_CODES:
		msgs.append(_("Billing Frequency {0} is not a valid IBG-14 description code.").format(freq))
	if _needs_full_invoice_period(flags):
		if not freq:
			msgs.append(
				_(
					"Billing Frequency is required for Deemed Supply, Summary Invoice, or "
					"Continuous Supply (IBG-14)."
				)
			)
		if not posting_date:
			msgs.append(_("Invoice Period start date (posting date) is required (IBG-14)."))
		if not due_date:
			msgs.append(
				_(
					"Invoice Period end date (Payment Due Date) is required for Deemed Supply, "
					"Summary Invoice, or Continuous Supply (IBG-14)."
				)
			)
	if freq == "OTH" and not has_notes:
		msgs.append(_("Invoice Note / Remarks (IBT-022) is required when Billing Frequency is OTH."))
	return msgs


_REGISTRATION_TYPES_WITHOUT_AUTHORITY = {
	"EID",
	"PAS",
	"CD",
	"Emirates ID",
	"Passport",
	"Cabinet decision",
}

# ISO 6523 ICD 0160 (GS1 GTIN). IBR-CL-21 rejects scheme HS on this identifier.
_GTIN_LENGTHS = (8, 12, 13, 14)
STANDARD_ITEM_SCHEME_GTIN = "0160"


def gtin_barcode(raw: str | None) -> str | None:
	"""Return a GTIN barcode, or None when the value is not an 8/12/13/14 digit code."""
	code = (raw or "").strip()
	if code.isdigit() and len(code) in _GTIN_LENGTHS:
		return code
	return None


def credit_note_reason_validation_messages(is_return: int | bool, reason: str | None) -> list[str]:
	"""BTAE-03: the e-invoice reason must be a GETS credit-note code."""
	if not is_return:
		return []
	if credit_note_reason_code(reason):
		return []
	return [
		_(
			"UAE Credit Note Reason must be an FTA code (BTAE-03): SUPPLY_CANCELLED, "
			"TAX_TREATMENT_CHANGED, CONSIDERATION_ALTERED, GOODS_OR_SERVICES_RETURNED, "
			"TAX_APPLIED_IN_ERROR, or VOLUME_DISCOUNT."
		)
	]


def principal_trn_validation_messages(
	flags: dict[str, bool], principal: str | None, seller_trn: str | None
) -> list[str]:
	"""BTAE-14 / IBR-137-AE / IBR-176-AE. Only disclosed-agent invoices carry a principal."""
	if not flags.get("disclosed_agent_billing"):
		return []
	value = (principal or "").strip()
	if not value:
		return [_("Disclosed-agent invoices require the principal TRN (BTAE-14).")]
	if not is_valid_uae_trn(value):
		return [
			_("Principal TRN must be 15 digits, starting with 1 and ending with 03 (IBR-132-AE).")
		]
	if seller_trn and value == str(seller_trn).strip():
		return [_("Principal TRN must differ from the seller TRN (IBR-176-AE).")]
	return []


def licence_authority_validation_messages(party_label: str, party: dict[str, Any], rule: str) -> list[str]:
	"""IBR-172-AE / IBR-191-AE: a trade licence needs the issuing authority name."""
	legal_id = (
		party.get("legal_registration_identifier") or party.get("trade_license_number") or ""
	).strip()
	if not legal_id:
		return []
	kind = (party.get("legal_registration_identifier_type") or "").strip()
	if kind in _REGISTRATION_TYPES_WITHOUT_AUTHORITY:
		return []
	if (party.get("licence_authority") or "").strip():
		return []
	return [
		_("{0} licence authority is required when the registration type is a trade licence ({1}).").format(
			party_label, rule
		)
	]


def buyer_fz_validation_messages(flags: dict[str, bool], fz_beneficiary_id: str | None) -> list[str]:
	"""BTAE-01 / IBR-007-ae: FZ ID lives on the buyer (Customer, or Company when self-billed)."""
	if flags.get("free_trade_zone") and not (fz_beneficiary_id or "").strip():
		return [
			_(
				"FZ Beneficiary ID (BTAE-01 / IBR-007-ae) is mandatory on the buyer "
				"for Free Trade Zone transactions."
			)
		]
	return []


class UAETransactionData:
	"""Build the ASP-agnostic transaction model for a Sales Invoice."""

	def __init__(self, doc):
		self.doc = doc
		self.company = frappe.get_cached_doc("Company", doc.company)
		self.customer = frappe.get_cached_doc("Customer", doc.customer) if doc.customer else None
		self.errors: list[str] = []

	# ------------------------------------------------------------------
	# Public API
	# ------------------------------------------------------------------

	def validate(self):
		"""Run all readiness checks; throw one consolidated error."""
		self.errors = []
		self._check_company()
		self._check_currency()
		self._check_parties()
		self._check_disclosed_agent()
		self._check_lines()
		self._check_credit_note()
		self._check_due_date()
		self._check_discount_mode()
		self._check_invoice_period()
		self._check_margin_scheme()
		self._get_payment_means(collect_only=True)

		if self.errors:
			frappe.throw(
				"<br>".join(self.errors),
				title=_("UAE E-Invoice Readiness"),
			)

	def get_data(self) -> dict[str, Any]:
		"""Validated, structured transaction data."""
		self.validate()

		lines = self._get_lines()
		tax_breakdown = self._get_tax_breakdown(lines)
		totals = self._get_totals(lines, tax_breakdown)

		return {
			"invoice_number": self.doc.name,
			"issue_date": str(getdate(self.doc.posting_date)),
			"issue_time": self._get_issue_time(),
			"due_date": self._get_due_date(),
			"document_type_code": self.get_document_type_code(),
			"currency": self.doc.currency,
			"tax_currency": AED_CURRENCY,
			"exchange_rate": self._get_exchange_rate(),
			"buyer_reference": self.doc.get("po_no") or self.doc.name,
			"transaction_type_code": self.get_transaction_type_code(),
			"transaction_flags": self.get_transaction_flags(),
			"credit_note": self._get_credit_note_details(),
			"principal_trn": self._principal_trn(),
			"invoice_period": self._get_invoice_period(),
			# BT-7 equals the issue date in ERPNext; PINT-AE wants it only when different
			"tax_point_date": None,
			"notes": self._get_notes(),
			"document_allowance": self._get_document_allowance(),
			"supplier": self._get_supplier(),
			"customer": self._get_customer(),
			"payment_means": self._get_payment_means(),
			"lines": lines,
			"tax_breakdown": tax_breakdown,
			"totals": totals,
			"vat_emirate": self.doc.get("vat_emirate"),
		}

	# ------------------------------------------------------------------
	# Header helpers
	# ------------------------------------------------------------------

	def get_document_type_code(self) -> str:
		explicit = self.doc.get("uae_document_type_code")
		if explicit:
			return explicit

		out_of_scope = self._all_lines_out_of_scope()
		if self.doc.get("is_return"):
			return "81" if out_of_scope else "381"
		return "480" if out_of_scope else "380"

	def get_transaction_type_code(self) -> str:
		raw = (self.doc.get("uae_transaction_type_code") or "").strip()
		if not raw:
			return DEFAULT_TRANSACTION_TYPE_CODE
		return raw.ljust(8, "0")[:8]

	def get_transaction_flags(self) -> dict[str, bool]:
		code = self.get_transaction_type_code()
		return {flag: code[position] == "1" for position, flag in enumerate(TRANSACTION_TYPE_FLAGS)}

	def _get_issue_time(self) -> str | None:
		posting_time = self.doc.get("posting_time")
		if not posting_time:
			return None
		# posting_time is a timedelta on saved docs
		total_seconds = int(getattr(posting_time, "total_seconds", lambda: 0)())
		if total_seconds:
			return "{:02d}:{:02d}:{:02d}".format(
				total_seconds // 3600, (total_seconds % 3600) // 60, total_seconds % 60
			)
		return str(posting_time)[:8]

	def _get_due_date(self) -> str | None:
		if self.doc.get("is_return"):
			return None
		if self.doc.get("due_date"):
			return str(getdate(self.doc.due_date))
		return None

	def _get_exchange_rate(self) -> float | None:
		"""Exchange rate to AED; None when invoice is already in AED."""
		if self.doc.currency == AED_CURRENCY:
			return None
		return r6(self.doc.conversion_rate)

	def _get_credit_note_details(self) -> dict[str, Any] | None:
		if not self.doc.get("is_return"):
			return None

		reference = None
		if self.doc.get("return_against"):
			original_posting_date = frappe.db.get_value(
				"Sales Invoice", self.doc.return_against, "posting_date"
			)
			reference = {
				"id": self.doc.return_against,
				"issue_date": str(getdate(original_posting_date)) if original_posting_date else None,
			}
		elif self.doc.get("uae_return_against_external"):
			# Original invoice issued outside this system (pre-go-live / other ERP)
			reference = {"id": self.doc.uae_return_against_external, "issue_date": None}

		return {
			"reference": reference,
			"reason": self.doc.get("uae_credit_note_reason"),
		}

	def _principal_trn(self) -> str | None:
		if not self.get_transaction_flags().get("disclosed_agent_billing"):
			return None
		return (self.doc.get("uae_principal_trn") or "").strip() or None

	def _check_disclosed_agent(self):
		self.errors.extend(
			principal_trn_validation_messages(
				self.get_transaction_flags(),
				self.doc.get("uae_principal_trn"),
				self._get_supplier().get("trn"),
			)
		)

	def _get_notes(self) -> list[str]:
		"""IBT-022 invoice note — required when billing frequency is OTH."""
		remarks = (self.doc.get("remarks") or "").strip()
		if remarks and remarks != "No Remarks":
			return [remarks]
		return []

	def _get_document_allowance(self) -> dict[str, Any] | None:
		"""Document-level AllowanceCharge for Net Total discounts.

		ERPNext writes the discount into each line via
		``distributed_discount_amount`` and reduces ``net_amount``. We rebuild
		pre-discount line extensions in ``_get_lines`` so LineExtension +
		AllowanceCharge = TaxExclusive without double-counting.

		Allowance amount uses ``sum(distributed)`` (not header discount_amount)
		so rounding adjustments stay consistent with rebuilt line extensions.
		"""
		header = abs(to_decimal(self.doc.get("discount_amount") or 0))
		if header <= 0:
			return None
		if self.doc.get("apply_discount_on") != "Net Total":
			return None

		distributed = sum(
			abs(to_decimal(row.get("distributed_discount_amount") or 0)) for row in (self.doc.items or [])
		)
		if distributed <= 0:
			# Cannot rebuild pre-discount extensions safely
			return None

		return {
			"amount": r2(distributed),
			"reason": _("Discount"),
		}

	def _emits_document_allowance(self) -> bool:
		return self._get_document_allowance() is not None

	def _get_invoice_period(self) -> dict[str, Any] | None:
		"""IBG-14 InvoicePeriod — deemed / summary / continuous, or explicit frequency."""
		flags = self.get_transaction_flags()
		frequency = (self.doc.get("uae_billing_frequency") or "").strip() or None
		if not invoice_period_is_required(flags, frequency):
			return None

		start = getdate(self.doc.posting_date) if self.doc.posting_date else None
		end = getdate(self.doc.due_date) if self.doc.get("due_date") else start
		if not start and not end:
			return None

		return {
			"start_date": str(start) if start else None,
			"end_date": str(end) if end else None,
			"description_code": frequency,
		}

	# ------------------------------------------------------------------
	# Parties
	# ------------------------------------------------------------------

	def _get_supplier(self) -> dict[str, Any]:
		address = self._get_address(self.doc.get("company_address")) or self._get_linked_address(
			"Company", self.doc.company
		)
		from taxmate.uae_e_invoicing.utils.mandate import vat_group_tin

		return {
			"name": self.company.company_name or self.company.name,
			"trn": self.company.tax_id,
			"vat_group_tin": vat_group_tin(self.company.tax_id),
			"peppol_id": self.company.get("uae_peppol_id"),
			"trade_license_number": self.company.get("trade_license_number"),
			"legal_registration_identifier_type": self.company.get("legal_registration_identifier_type"),
			"legal_registration_identifier": self.company.get("legal_registration_identifier"),
			"licence_authority": self.company.get("uae_licence_authority"),
			"address": address,
			"contact": {
				"name": self.company.company_name,
				"email": self.company.get("email"),
				"phone": self.company.get("phone_no"),
			},
		}

	def _get_customer(self) -> dict[str, Any]:
		party = self.customer
		address = self._get_address(self.doc.get("customer_address"))
		if not address and party and party.get("customer_primary_address"):
			address = self._get_address(party.customer_primary_address)
		if not address:
			address = self._get_linked_address("Customer", self.doc.customer)

		from taxmate.uae_e_invoicing.utils.mandate import vat_group_tin

		return {
			"name": self.doc.customer_name or self.doc.customer,
			"trn": party.tax_id if party else None,
			"vat_group_tin": vat_group_tin(party.tax_id) if party else None,
			"peppol_id": party.get("uae_peppol_id") if party else None,
			"fz_beneficiary_id": party.get("uae_fz_beneficiary_id") if party else None,
			"trade_license_number": party.get("trade_license_number") if party else None,
			"legal_registration_identifier_type": (
				party.get("legal_registration_identifier_type") if party else None
			),
			"legal_registration_identifier": (party.get("legal_registration_identifier") if party else None),
			"licence_authority": party.get("uae_licence_authority") if party else None,
			"address": address,
			"contact": {
				"name": self.doc.get("contact_display") or self.doc.customer_name,
				"email": self.doc.get("contact_email") or (address or {}).get("email"),
				"phone": self.doc.get("contact_mobile") or (address or {}).get("phone"),
			},
		}

	def _get_address(self, address_name: str | None) -> dict[str, Any] | None:
		if not address_name:
			return None
		address = frappe.get_cached_doc("Address", address_name)
		emirate = address.get("emirate")
		country = address.get("country")
		return {
			"line1": address.address_line1,
			"line2": address.address_line2,
			"city": address.city,
			"postal_zone": address.pincode,
			"emirate": emirate,
			"emirate_code": EMIRATE_SUBDIVISION_CODES.get(emirate),
			"country": country,
			"country_code": self._get_country_code(country),
			"email": address.email_id,
			"phone": address.phone,
		}

	def _get_linked_address(self, doctype: str, name: str | None) -> dict[str, Any] | None:
		if not name:
			return None
		address_name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": doctype, "link_name": name, "parenttype": "Address"},
			"parent",
		)
		return self._get_address(address_name)

	@staticmethod
	def _get_country_code(country: str | None) -> str:
		if not country:
			return "AE"
		code = frappe.db.get_value("Country", country, "code")
		return (code or "AE").upper()

	# ------------------------------------------------------------------
	# Lines and taxes
	# ------------------------------------------------------------------

	def _get_lines(self) -> list[dict[str, Any]]:
		item_wise_tax = self._get_item_wise_tax_map()
		rebuild_pre_discount = self._emits_document_allowance()
		conversion = to_decimal(self.doc.conversion_rate or 1)
		lines = []

		for idx, row in enumerate(self.doc.items or [], start=1):
			category_label, exemption_reason, rcm_nature = self._get_line_vat_meta(row)
			category_code = VAT_CATEGORY_CODES.get(category_label or "Standard", "S")

			# Post-document-discount net (what ERPNext taxed)
			taxable_net = abs(to_decimal(row.net_amount if row.net_amount is not None else row.amount))
			distributed = abs(to_decimal(row.get("distributed_discount_amount") or 0))
			# LineExtensionAmount is pre-document-discount when we emit AllowanceCharge
			line_extension = taxable_net + distributed if rebuild_pre_discount else taxable_net
			base_taxable = abs(
				to_decimal(row.base_net_amount if row.base_net_amount is not None else row.amount)
			)
			base_line_extension = (
				base_taxable + (distributed * conversion) if rebuild_pre_discount else base_taxable
			)

			tax_rate, tax_amount = self._get_line_tax(row, item_wise_tax, taxable_net)
			gtin = self._gtin_by_item().get(row.item_code) if row.item_code else None
			# N (margin scheme): VAT is due on the margin and must not be
			# disclosed per line to the buyer
			if category_code in ("Z", "E", "O", "AE", "N"):
				tax_rate, tax_amount = Decimal("0"), Decimal("0")

			lines.append(
				{
					"id": str(idx),
					"item_row": row.name,
					"item_code": row.item_code,
					"item_name": row.item_name,
					"description": row.description or row.item_name,
					"qty": abs(float(to_decimal(row.qty))),
					"uom": row.uom or "C62",
					"rate": r2(row.rate),
					"price_before_discount": r2(
						row.get("price_list_rate")
						or row.get("rate_with_margin")
						or (to_decimal(row.rate) + to_decimal(row.get("discount_amount") or 0))
					)
					if row.get("discount_amount")
					else None,
					# LineExtensionAmount (pre document allowance when applicable)
					"net_amount": r2(line_extension),
					"base_net_amount": r2(base_line_extension),
					# Taxable base after document allowance (matches ERPNext VAT)
					"taxable_amount": r2(taxable_net),
					"discount_amount": r2(abs(to_decimal(row.get("discount_amount")) * to_decimal(row.qty))),
					"uae_item_type": row.get("uae_item_type"),
					"hs_code": row.get("hs_code"),
					"sac_code": row.get("sac_code"),
					"vat_category_code": category_code,
					"tax_rate": r2(tax_rate),
					"tax_amount": r2(abs(tax_amount)),
					"base_tax_amount": r2(abs(tax_amount) * conversion),
					"exemption_reason": exemption_reason,
					"rcm_nature": rcm_nature,
					"standard_item_id": gtin,
					"standard_item_scheme": STANDARD_ITEM_SCHEME_GTIN if gtin else None,
				}
			)
		return lines

	def _gtin_by_item(self) -> dict[str, str]:
		"""First GTIN barcode on each item. HS codes are not used here (IBR-CL-21)."""
		cached = getattr(self, "_gtin_cache", None)
		if cached is not None:
			return cached
		codes = list({row.item_code for row in (self.doc.items or []) if row.get("item_code")})
		found: dict[str, str] = {}
		if codes:
			for row in frappe.get_all(
				"Item Barcode",
				filters={"parent": ["in", codes], "parenttype": "Item"},
				fields=["parent", "barcode"],
			):
				if row.parent in found:
					continue
				code = gtin_barcode(row.barcode)
				if code:
					found[row.parent] = code
		self._gtin_cache = found
		return found

	def _get_line_vat_meta(self, row) -> tuple[str | None, str | None, str | None]:
		"""VAT category label + exemption/RCM metadata from the Item Tax Template."""
		if row.get("item_tax_template"):
			template = frappe.get_cached_doc("Item Tax Template", row.item_tax_template)
			return (
				template.get("uae_vat_category"),
				template.get("uae_exemption_reason"),
				template.get("uae_rcm_nature"),
			)

		if row.get("is_exempt"):
			return "Exempt", None, None
		if row.get("is_zero_rated"):
			return "Zero Rated", None, None
		return "Standard", None, None

	def _is_vat_tax_row(self, tax_row) -> bool:
		"""True for VAT / tax-account rows; false for freight and other charges."""
		if tax_row.get("category") == "Valuation":
			return False
		account_head = tax_row.get("account_head")
		if account_head:
			account_type = frappe.get_cached_value("Account", account_head, "account_type")
			if account_type == "Tax":
				return True
			if account_type and account_type != "Tax":
				return False
		# No account type: treat percentage-based rows as VAT, Actual as charge
		return tax_row.get("charge_type") != "Actual"

	def _get_vat_tax_row_names(self) -> set[str]:
		return {row.name for row in (self.doc.taxes or []) if row.name and self._is_vat_tax_row(row)}

	def _get_item_wise_tax_map(self) -> dict[str, Decimal]:
		"""Aggregate VAT amounts keyed by item row ``name`` (not item_code)."""
		tax_map: dict[str, Decimal] = {}
		vat_rows = self._get_vat_tax_row_names()

		# Preferred: Item Wise Tax Detail child table (ERPNext v16+)
		details = self.doc.get("item_wise_tax_details") or []
		if details:
			for detail in details:
				item_row = detail.get("item_row")
				tax_row = detail.get("tax_row")
				if not item_row:
					continue
				if vat_rows and tax_row and tax_row not in vat_rows:
					continue
				tax_map[item_row] = tax_map.get(item_row, Decimal("0")) + to_decimal(
					detail.get("amount") or 0
				)
			return tax_map

		# Legacy: JSON on each tax row — only safe with unique item codes
		for tax_row in self.doc.taxes or []:
			if not self._is_vat_tax_row(tax_row):
				continue
			detail = tax_row.get("item_wise_tax_detail")
			if not detail:
				continue
			try:
				parsed = json.loads(detail) if isinstance(detail, str) else detail
			except (ValueError, TypeError):
				continue
			for item_code, rate_amount in parsed.items():
				amount = rate_amount[1] if isinstance(rate_amount, (list, tuple)) else rate_amount
				if isinstance(amount, dict):
					amount = amount.get("tax_amount", 0)
				tax_map[item_code] = tax_map.get(item_code, Decimal("0")) + to_decimal(amount)
		return tax_map

	def _get_line_tax(
		self, row, item_wise_tax: dict[str, Decimal], net_amount: Decimal
	) -> tuple[Decimal, Decimal]:
		"""(rate, amount) for one line — actuals first, computed fallback."""
		rate = None
		if row.get("item_tax_template"):
			template = frappe.get_cached_doc("Item Tax Template", row.item_tax_template)
			if template.taxes:
				rate = to_decimal(template.taxes[0].tax_rate)
		if rate is None:
			vat_taxes = [t for t in (self.doc.taxes or []) if self._is_vat_tax_row(t)]
			first_tax = vat_taxes[0] if vat_taxes else None
			rate = to_decimal(first_tax.rate) if first_tax else Decimal("0")

		# Prefer child-row name (handles duplicate item codes)
		if row.name and row.name in item_wise_tax:
			return rate, item_wise_tax[row.name]

		key = row.item_code or row.item_name
		unique_codes = len(self.doc.items) == len({r.item_code or r.item_name for r in self.doc.items})
		if key in item_wise_tax and unique_codes:
			return rate, item_wise_tax[key]

		return rate, net_amount * rate / Decimal("100")

	def _get_non_vat_charge_total(self) -> Decimal:
		"""Document-level non-VAT charges (freight etc.) for ChargeTotalAmount."""
		total = Decimal("0")
		for tax_row in self.doc.taxes or []:
			if self._is_vat_tax_row(tax_row):
				continue
			if tax_row.get("category") == "Valuation":
				continue
			amount = to_decimal(
				tax_row.get("tax_amount_after_discount_amount")
				if tax_row.get("tax_amount_after_discount_amount") is not None
				else tax_row.get("tax_amount") or 0
			)
			if tax_row.get("add_deduct_tax") == "Deduct":
				amount = -amount
			total += amount
		return total

	def _get_tax_breakdown(self, lines: list[dict]) -> list[dict[str, Any]]:
		"""Aggregate TaxSubtotal per (category, rate) — IBT-116/117/118/119."""
		buckets: dict[tuple[str, float], dict[str, Decimal]] = {}
		for line in lines:
			key = (line["vat_category_code"], line["tax_rate"])
			bucket = buckets.setdefault(key, {"taxable": Decimal("0"), "tax": Decimal("0")})
			# TaxableAmount is post document-allowance (matches ERPNext VAT base)
			bucket["taxable"] += to_decimal(line.get("taxable_amount", line["net_amount"]))
			bucket["tax"] += to_decimal(line["tax_amount"])

		conversion = to_decimal(self.doc.conversion_rate or 1)
		breakdown = []
		for (category, rate), bucket in sorted(buckets.items()):
			entry = {
				"vat_category_code": category,
				"tax_rate": rate,
				"taxable_amount": r2(bucket["taxable"]),
				"tax_amount": r2(bucket["tax"]),
				"base_taxable_amount": r2(bucket["taxable"] * conversion),
				"base_tax_amount": r2(bucket["tax"] * conversion),
			}
			if category == "E":
				entry["exemption_reason"] = self._first_line_value(lines, category, "exemption_reason")
			if category == "AE":
				entry["rcm_nature"] = self._first_line_value(lines, category, "rcm_nature")
			breakdown.append(entry)
		return breakdown

	@staticmethod
	def _first_line_value(lines: list[dict], category: str, field: str):
		for line in lines:
			if line["vat_category_code"] == category and line.get(field):
				return line[field]
		return None

	def _get_totals(self, lines: list[dict], tax_breakdown: list[dict]) -> dict[str, Any]:
		line_extension = sum(to_decimal(line["net_amount"]) for line in lines)
		tax_total = sum(to_decimal(entry["tax_amount"]) for entry in tax_breakdown)

		allowance = to_decimal(0)
		doc_allowance = self._get_document_allowance()
		if doc_allowance:
			allowance = to_decimal(doc_allowance["amount"])

		charge = self._get_non_vat_charge_total()
		tax_exclusive = line_extension - allowance
		tax_inclusive = tax_exclusive + tax_total + charge

		prepaid = to_decimal(self.doc.get("total_advance") or 0)

		rounded_total = to_decimal(self.doc.rounded_total or self.doc.grand_total)
		grand_total = to_decimal(self.doc.grand_total)
		payable_rounding = rounded_total - grand_total if self.doc.rounded_total else Decimal("0")
		payable = tax_inclusive + payable_rounding - prepaid

		conversion = to_decimal(self.doc.conversion_rate or 1)
		return {
			"line_extension_amount": r2(line_extension),
			"allowance_total_amount": r2(allowance),
			"charge_total_amount": r2(charge),
			"tax_exclusive_amount": r2(tax_exclusive),
			"tax_total_amount": r2(tax_total),
			"tax_inclusive_amount": r2(tax_inclusive),
			"prepaid_amount": r2(prepaid),
			"payable_rounding_amount": r2(payable_rounding),
			"payable_amount": r2(payable),
			# BTAE-08 / BTAE-20: AED equivalents (tax accounting currency)
			"base_tax_total_amount": r2(tax_total * conversion),
			"base_tax_inclusive_amount": r2(tax_inclusive * conversion),
			"base_payable_amount": r2(payable * conversion),
		}

	# ------------------------------------------------------------------
	# Payment means (IBT-081)
	# ------------------------------------------------------------------

	def _get_payment_means(self, collect_only: bool = False) -> list[dict[str, Any]] | None:
		if self.doc.get("is_return"):
			return None

		entries: list[dict[str, Any]] = []

		# POS payments carry explicit modes of payment
		for payment_row in self.doc.get("payments") or []:
			code_option = frappe.db.get_value(
				"Mode of Payment", payment_row.mode_of_payment, "uae_payment_means_code"
			)
			entry = self._build_payment_means_entry(code_option)
			if entry:
				entries.append(entry)

		if not entries:
			entry = self._build_payment_means_entry(self.doc.get("uae_payment_means_code"))
			if entry:
				entries.append(entry)

		if not entries and collect_only:
			self.errors.append(
				_(
					"Payment means type code (IBT-081) is required — set it on the invoice "
					"or on the Mode of Payment."
				)
			)
		return entries or None

	def _build_payment_means_entry(self, code_option: str | None) -> dict[str, Any] | None:
		if not code_option:
			return None
		code = str(code_option).split(" - ")[0].strip()
		if code not in APPROVED_PAYMENT_MEANS:
			self.errors.append(
				_("Payment means code {0} is not in the approved UNCL4461 subset.").format(code)
			)
			return None

		entry: dict[str, Any] = {
			"code": code,
			"name": APPROVED_PAYMENT_MEANS[code],
		}

		if code in BANK_TRANSFER_PAYMENT_CODES:
			account = self._get_company_bank_account()
			if not account:
				self.errors.append(
					_(
						"A company Bank Account with IBAN is required for credit-transfer "
						"payment means ({0}). Create one for {1} with 'Is Company Account' enabled."
					).format(code, self.doc.company)
				)
			else:
				entry["payee_financial_account"] = account

		if code in CARD_PAYMENT_CODES:
			entry["card_account"] = {"holder_name": self.doc.customer_name}

		return entry

	def _get_company_bank_account(self) -> dict[str, Any] | None:
		account = frappe.db.get_value(
			"Bank Account",
			{"company": self.doc.company, "is_company_account": 1, "is_default": 1},
			["name", "bank_account_no", "iban", "account_name", "branch_code", "bank"],
			as_dict=True,
		)
		if not account:
			account = frappe.db.get_value(
				"Bank Account",
				{"company": self.doc.company, "is_company_account": 1},
				["name", "bank_account_no", "iban", "account_name", "branch_code", "bank"],
				as_dict=True,
			)
		if not account or not (account.iban or account.bank_account_no):
			return None
		return {
			"id": account.iban or account.bank_account_no,
			"scheme": "IBAN" if account.iban else "OTH",
			"name": account.account_name,
			"branch": account.branch_code,
		}

	# ------------------------------------------------------------------
	# Validation checks
	# ------------------------------------------------------------------

	def _check_company(self):
		if self.company.default_currency != AED_CURRENCY:
			self.errors.append(
				_("Company currency must be AED for UAE e-invoicing (found {0}).").format(
					self.company.default_currency
				)
			)
		if not is_valid_uae_trn(self.company.tax_id):
			self.errors.append(
				_("Company Tax ID must be 15 digits, starting with 1 and ending with 03 (IBR-132-AE).")
			)
		if not self.company.get("uae_peppol_id"):
			self.errors.append(
				_("Company Peppol Participant ID (IBT-034) is required — set it on Company {0}.").format(
					self.doc.company
				)
			)

	def _check_currency(self):
		if self.doc.currency != AED_CURRENCY and not self.doc.conversion_rate:
			self.errors.append(_("Exchange rate to AED is mandatory when invoice currency is not AED."))

	def _check_parties(self):
		supplier = self._get_supplier()
		if not supplier["address"]:
			self.errors.append(
				_(
					"Company address is required: link an Address to {0} or set Company Address "
					"on the invoice."
				).format(self.doc.company)
			)
		else:
			self._check_address(supplier["address"], _("Company address"))

		customer = self._get_customer()
		if not customer["name"]:
			self.errors.append(_("Customer legal name (IBT-044) is required."))
		if not customer["address"]:
			self.errors.append(
				_("Customer address (IBT-050/052/055) is required — set Customer Address on the invoice.")
			)
		else:
			self._check_address(customer["address"], _("Customer address"))
			if not customer["address"].get("postal_zone"):
				self.errors.append(_("Customer address: Postal Zone is required (IBT-053)."))

		if not (customer["contact"] or {}).get("email"):
			self.errors.append(
				_(
					"Customer email is required — set a Contact Email on the invoice or an email on the customer address."
				)
			)

		flags = self.get_transaction_flags()
		if not flags["export"]:
			if not customer["peppol_id"]:
				self.errors.append(
					_(
						"Customer Peppol Participant ID (IBT-049) is required for domestic "
						"invoices — set it on the Customer (use Verify Peppol ID to confirm registration)."
					)
				)
			if not customer["trn"] and not customer["trade_license_number"]:
				self.errors.append(
					_("Customer must have a TRN or Trade License Number for domestic invoices (IBR-135-ae).")
				)
			elif customer["trn"] and not is_valid_uae_trn(customer["trn"]):
				self.errors.append(
					_("Customer TRN must be 15 digits, starting with 1 and ending with 03 (IBR-132-AE).")
				)

		self.errors.extend(buyer_fz_validation_messages(flags, customer.get("fz_beneficiary_id")))
		self.errors.extend(
			licence_authority_validation_messages(_("Company"), supplier, "IBR-172-AE")
		)
		self.errors.extend(
			licence_authority_validation_messages(_("Customer"), customer, "IBR-191-AE")
		)

		if self.doc.get("is_return") and not customer["trade_license_number"] and not customer["trn"]:
			self.errors.append(_("Customer legal identifier is mandatory for Credit Notes (IBR-136-ae)."))

	def _check_address(self, address: dict, label: str):
		if not address.get("line1"):
			self.errors.append(_("{0}: Address Line 1 is required (IBT-050).").format(label))
		if not address.get("city"):
			self.errors.append(_("{0}: City is required (IBT-052).").format(label))
		if not address.get("country"):
			self.errors.append(_("{0}: Country is required (IBT-055).").format(label))
		if address.get("country") == UAE_COUNTRY and not address.get("emirate_code"):
			self.errors.append(_("{0}: Emirate is required for UAE addresses (IBT-054).").format(label))

	def _check_lines(self):
		if not self.doc.items:
			self.errors.append(_("Invoice must have at least one item line."))
			return

		for row in self.doc.items:
			if not self.doc.get("is_return") and to_decimal(row.qty) <= 0:
				self.errors.append(
					_("Row #{0}: Invoiced quantity must be greater than zero.").format(row.idx)
				)
			item_type = row.get("uae_item_type")
			if not item_type:
				self.errors.append(
					_("Row #{0}: UAE Item Type (Goods / Service / Both) is required.").format(row.idx)
				)
			elif item_type == ITEM_TYPE_GOODS and not row.get("hs_code"):
				self.errors.append(_("Row #{0}: HS Code is required for Goods.").format(row.idx))
			elif item_type == ITEM_TYPE_SERVICE and not row.get("sac_code"):
				self.errors.append(_("Row #{0}: SAC Code is required for Services.").format(row.idx))
			elif item_type == ITEM_TYPE_BOTH:
				if not row.get("hs_code"):
					self.errors.append(
						_("Row #{0}: HS Code is required for Both (Goods + Service).").format(row.idx)
					)
				if not row.get("sac_code"):
					self.errors.append(
						_("Row #{0}: SAC Code is required for Both (Goods + Service).").format(row.idx)
					)

			if row.get("item_tax_template"):
				template = frappe.get_cached_doc("Item Tax Template", row.item_tax_template)
				category = template.get("uae_vat_category")
				if category == "Exempt" and not template.get("uae_exemption_reason"):
					self.errors.append(
						_("Row #{0}: Exemption reason is required on Item Tax Template {1}.").format(
							row.idx, row.item_tax_template
						)
					)
				rcm_type = template.get("uae_rcm_nature")
				if category == "Reverse Charge" and not rcm_type:
					self.errors.append(
						_("Row #{0}: Reverse charge type is required on Item Tax Template {1}.").format(
							row.idx, row.item_tax_template
						)
					)
				elif rcm_type and rcm_type not in RCM_TYPE_CODES:
					self.errors.append(
						_("Row #{0}: Reverse charge type {1} is not an FTA category.").format(
							row.idx, rcm_type
						)
					)
				if category == "Reverse Charge" and not self._gtin_by_item().get(row.item_code):
					self.errors.append(
						_(
							"Row #{0}: reverse charge requires a GTIN barcode on Item {1} "
							"(standard item identifier, scheme 0160)."
						).format(row.idx, row.item_code or row.item_name)
					)

	def _check_credit_note(self):
		if not self.doc.get("is_return"):
			return
		if not self.doc.get("return_against") and not self.doc.get("uae_return_against_external"):
			self.errors.append(
				_(
					"Credit Notes must reference the original invoice (IBT-025) — set Return "
					"Against, or External Return Against for invoices issued outside this system."
				)
			)
		self.errors.extend(
			credit_note_reason_validation_messages(True, self.doc.get("uae_credit_note_reason"))
		)

	def _check_due_date(self):
		if self.doc.get("is_return"):
			return
		outstanding = to_decimal(self.doc.get("outstanding_amount"))
		if outstanding > 0 and not self.doc.get("due_date"):
			self.errors.append(
				_("Payment Due Date (IBT-009) is mandatory when there is an outstanding amount.")
			)
		if self.doc.get("due_date") and getdate(self.doc.due_date) < getdate(self.doc.posting_date):
			self.errors.append(_("Payment Due Date must be on or after the Issue Date."))

	def _check_discount_mode(self):
		if to_decimal(self.doc.get("discount_amount")) and self.doc.get("apply_discount_on") == "Grand Total":
			self.errors.append(
				_(
					"Apply additional discounts on Net Total for UAE e-invoices — "
					"post-tax discounts cannot be represented in PINT-AE."
				)
			)

	def _check_invoice_period(self):
		self.errors.extend(
			invoice_period_validation_messages(
				self.get_transaction_flags(),
				self.doc.get("uae_billing_frequency"),
				self.doc.posting_date,
				self.doc.get("due_date"),
				bool(self._get_notes()),
			)
		)

	def _check_margin_scheme(self):
		"""BTAE-02 bit 3 (margin scheme) must agree with N-category lines."""
		flags = self.get_transaction_flags()
		has_margin_lines = any(
			VAT_CATEGORY_CODES.get(self._get_line_vat_meta(row)[0] or "Standard", "S") == "N"
			for row in (self.doc.items or [])
		)
		if has_margin_lines and not flags["margin_scheme"]:
			self.errors.append(
				_(
					"Margin Scheme items require the margin scheme flag (position 3) in the "
					"UAE Transaction Type Code."
				)
			)
		if flags["margin_scheme"] and not has_margin_lines:
			self.errors.append(
				_(
					"Transaction Type Code declares Margin Scheme, but no item line uses a "
					"Margin Scheme Item Tax Template."
				)
			)

	def _all_lines_out_of_scope(self) -> bool:
		if not self.doc.items:
			return False
		for row in self.doc.items:
			label, _reason, _rcm = self._get_line_vat_meta(row)
			if VAT_CATEGORY_CODES.get(label or "Standard", "S") != "O":
				return False
		return True
