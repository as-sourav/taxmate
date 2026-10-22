"""UAE e-invoicing (PINT-AE) code lists and constants.

References:
- PINT-AE billing specification (docs.peppol.eu/poac/ae)
- FTA eInvoice Data Dictionary / Mandatory Fields (Feb 2026)
- UNCL1001 (document types), UNCL4461 (payment means)
"""

from __future__ import annotations

PINT_AE_CUSTOMIZATION_ID = "urn:peppol:pint:billing-1@ae-1"
PINT_AE_PROFILE_ID = "urn:peppol:bis:billing"

AED_CURRENCY = "AED"

# UNCL1001 document type codes used by the UAE mandate
SALES_DOCUMENT_TYPE_CODES = {
	"380": "Commercial Invoice",
	"381": "Credit Note (Taxable)",
	"480": "Out of Scope Invoice",
	"81": "Credit Note (Out of Scope)",
}

PURCHASE_DOCUMENT_TYPE_CODES = {
	"389": "Self-Billed Invoice",
	"361": "Self-Billed Credit Note",
}

# PEPPOL / PINT-AE VAT category codes, keyed by the labels used on
# Item Tax Template.uae_vat_category
VAT_CATEGORY_CODES = {
	"Standard": "S",
	"Zero Rated": "Z",
	"Exempt": "E",
	"Out of Scope": "O",
	"Reverse Charge": "AE",
	"Margin Scheme": "N",
}

# UNCL4461 subset approved for UAE e-invoicing (IBT-081)
APPROVED_PAYMENT_MEANS = {
	"1": "Instrument not defined",
	"10": "Cash",
	"20": "Cheque",
	"30": "Credit transfer",
	"31": "Debit transfer",
	"42": "Payment to bank account",
	"48": "Bank card",
	"49": "Direct debit",
	"54": "Credit card",
	"55": "Debit card",
	"58": "SEPA credit transfer",
}

PAYMENT_MEANS_SELECT_OPTIONS = "\n" + "\n".join(
	f"{code} - {label}" for code, label in APPROVED_PAYMENT_MEANS.items()
)

# Codes that require payee financial account details (IBT-084)
BANK_TRANSFER_PAYMENT_CODES = ("30", "58")
CARD_PAYMENT_CODES = ("48", "54", "55")

# PEPPOL country-subdivision codes for the seven emirates (IBT-054)
EMIRATE_SUBDIVISION_CODES = {
	"Abu Dhabi": "AUH",
	"Ajman": "AJM",
	"Dubai": "DXB",
	"Fujairah": "FUJ",
	"Ras Al Khaimah": "RAK",
	"Sharjah": "SHJ",
	"Umm Al Quwain": "UAQ",
}

# BTAE-02: 8-character bit-flag string describing UAE special transaction types.
# Position (0-based) -> meaning when set to "1".
TRANSACTION_TYPE_FLAGS = (
	"free_trade_zone",  # 0
	"deemed_supply",  # 1
	"margin_scheme",  # 2
	"summary_invoice",  # 3
	"continuous_supply",  # 4
	"disclosed_agent_billing",  # 5
	"e_commerce",  # 6
	"export",  # 7
)

DEFAULT_TRANSACTION_TYPE_CODE = "00000000"

# IBG-14 must be complete (start, end, frequency) when any of these BTAE-02 bits are set.
INVOICE_PERIOD_REQUIRED_FLAGS = ("deemed_supply", "summary_invoice", "continuous_supply")

# IBG-14 / InvoicePeriod description codes (frequency of billing)
BILLING_FREQUENCY_CODES = {
	"DLY": "Daily",
	"WKY": "Weekly",
	"Q15": "Every 15 days",
	"MTH": "Monthly",
	"Q45": "Every 45 days",
	"Q60": "Every 60 days",
	"QTR": "Quarterly",
	"HYR": "Half-yearly",
	"YRL": "Yearly",
	"OTH": "Other",
}

BILLING_FREQUENCY_SELECT_OPTIONS = "\n" + "\n".join(BILLING_FREQUENCY_CODES.keys())

# Item classification used for HS / SAC enforcement
ITEM_TYPE_GOODS = "Goods"
ITEM_TYPE_SERVICE = "Service"
ITEM_TYPE_BOTH = "Both"

# extensions.ae_creditNoteReasonCode. Complyance maps CreditNoteReasonCode to this enum.
# BTAE-03. VOLUME_DISCOUNT is the only reason that may omit a preceding invoice.
CREDIT_NOTE_REASON_CODES = {
	"SUPPLY_CANCELLED": "Supply cancelled",
	"TAX_TREATMENT_CHANGED": "Tax treatment changed",
	"CONSIDERATION_ALTERED": "Consideration altered",
	"GOODS_OR_SERVICES_RETURNED": "Goods or services returned",
	"TAX_APPLIED_IN_ERROR": "Tax applied in error",
	"VOLUME_DISCOUNT": "Volume discount",
}

# Phrases already stored on credit notes before the reason became a code.
_LEGACY_CREDIT_NOTE_REASONS = {
	"goods returned": "GOODS_OR_SERVICES_RETURNED",
	"pricing correction": "CONSIDERATION_ALTERED",
	"vd": "VOLUME_DISCOUNT",
	"volume discount": "VOLUME_DISCOUNT",
}


def credit_note_reason_code(raw: str | None) -> str | None:
	"""Return the GETS reason code, or None when the text is not a known reason."""
	text = (raw or "").strip()
	if not text:
		return None
	head = text.split(" - ", 1)[0].strip()
	if head in CREDIT_NOTE_REASON_CODES:
		return head
	return _LEGACY_CREDIT_NOTE_REASONS.get(text.lower())


# lineItems[].extensions.ae_rcmType. Required only on reverse-charge lines.
RCM_TYPE_CODES = (
	"ELECTRONIC_DEVICES",
	"GOLD_AND_DIAMONDS",
	"CRUDE_OR_REFINED_OIL",
	"UNPROCESSED_OR_PROCESSED_NATURAL_GAS",
	"PURE_HYDROCARBONS",
)

# E-invoice lifecycle statuses shared by log + invoice custom field
E_INVOICE_STATUSES = (
	"Draft",
	"Generated",
	"Queued",
	"Submitted",
	"Accepted",
	"Rejected",
	"Failed",
	"Cancelled",
)

# FTA transmission window: issue/submit → Accepted (calendar days)
TRANSMISSION_SLA_DAYS = 14

# Signed XML/PDF archive — keep accepted logs at least this long
ARCHIVE_RETENTION_YEARS = 5

# Contingency: report ASP/FTA downtime within this many days
CONTINGENCY_REPORT_DAYS = 2

# --- E-Invoicing mandate rollout --------------------------------------------
# Ministerial Decision 244/2025 as amended by Ministerial Resolution 66/2026.
# Not legal advice — confirm the live circular with the ASP or FTA.
EINVOICE_LARGE_BUSINESS_REVENUE_THRESHOLD_AED = 50_000_000

# MD 244 classifies on most-recent accounting-period *financial-statement*
# revenue (gross), not VAT 201 and not a TaxMate GL window. Empty band =
# Unclassified. TaxMate will not guess Large vs SME from the ledger.
EINVOICE_REVENUE_BAND_BELOW = "Below AED 50,000,000"
EINVOICE_REVENUE_BAND_AT_OR_ABOVE = "AED 50,000,000 or more"

# cohort -> {asp_deadline, go_live, label}. Pilot is never auto-assigned.
# Unclassified has no dates — set the FS revenue band or an override first.
EINVOICE_MANDATE_PHASES = {
	"Unclassified": {
		"asp_deadline": None,
		"go_live": None,
		"label": "Unclassified — set last accounting-period FS revenue or an override",
	},
	"Pilot": {
		"asp_deadline": None,
		"go_live": "2026-07-01",
		"label": "Pilot — selected early participants",
	},
	"Large": {
		"asp_deadline": "2026-10-30",
		"go_live": "2027-01-01",
		"label": "Large business — FS revenue ≥ AED 50,000,000",
	},
	"SME": {
		"asp_deadline": "2027-03-31",
		"go_live": "2027-07-01",
		"label": "SME — FS revenue < AED 50,000,000",
	},
	"Government": {
		"asp_deadline": "2027-03-31",
		"go_live": "2027-10-01",
		"label": "Government entities",
	},
}

EINVOICE_MANDATE_COHORTS = ("Pilot", "Large", "SME", "Government")

# Nudge this many days before ASP appointment *or* go-live (and after, until
# e-invoicing is enabled).
EINVOICE_MANDATE_REMINDER_WINDOW_DAYS = 60

EINVOICE_MANDATE_TODO_KEY = "tm-einvoice-mandate"
EINVOICE_CLASSIFY_TODO_KEY = "tm-einvoice-classify"

EINVOICE_MANDATE_DISCLAIMER = (
	"Dates follow Ministerial Decision 244/2025 as amended by Resolution 66/2026 "
	"(Large ASP appointment 30 Oct 2026). Confirm this company's cohort with the "
	"ASP or FTA — this is not legal or tax advice. Classification uses the "
	"revenue band you enter from the last accounting-period financial statements, "
	"not TaxMate's general ledger."
)
