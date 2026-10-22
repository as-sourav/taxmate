"""TaxMate-owned custom fields for UAE VAT / e-invoicing.

Do NOT redefine ERPNext UAE regional fields (emirate, tax_code, is_zero_rated,
is_exempt, vat_emirate, company_trn, reverse_charge, permit_no, etc.).
"""

from __future__ import annotations

from taxmate.uae.constants import UAE_EMIRATES
from taxmate.uae_e_invoicing.constants import (
	BILLING_FREQUENCY_SELECT_OPTIONS,
	PAYMENT_MEANS_SELECT_OPTIONS,
)

PARTY_LEGAL_FIELDS = [
	{
		"fieldname": "uae_legal_section",
		"label": "UAE Legal Identifiers",
		"fieldtype": "Section Break",
		"insert_after": "tax_id",
		"collapsible": 1,
	},
	{
		"fieldname": "trade_license_number",
		"label": "Trade License Number",
		"fieldtype": "Data",
		"insert_after": "uae_legal_section",
		"translatable": 0,
	},
	{
		"fieldname": "legal_registration_identifier_type",
		"label": "Legal Registration Identifier Type",
		"fieldtype": "Select",
		"options": "\nTL\nEID\nPAS\nCD",
		"insert_after": "trade_license_number",
		"translatable": 0,
	},
	{
		"fieldname": "legal_registration_identifier",
		"label": "Legal Registration Identifier",
		"fieldtype": "Data",
		"insert_after": "legal_registration_identifier_type",
		"translatable": 0,
	},
	{
		"fieldname": "uae_licence_authority",
		"label": "Licence Authority",
		"fieldtype": "Data",
		"insert_after": "legal_registration_identifier",
		"description": "Authority that issued the trade licence. Required on the e-invoice when the registration type is TL.",
		"translatable": 0,
	},
	{
		"fieldname": "uae_peppol_id",
		"label": "Peppol Participant ID",
		"fieldtype": "Data",
		"insert_after": "uae_licence_authority",
		"description": "Peppol endpoint identifier used for e-invoice exchange",
		"translatable": 0,
	},
	{
		"fieldname": "uae_fz_beneficiary_id",
		"label": "FZ Beneficiary ID",
		"fieldtype": "Data",
		"insert_after": "uae_peppol_id",
		"description": (
			"BTAE-01 / IBR-007-ae: Free Zone beneficiary identifier for this party. "
			"E-invoice requires it on the buyer (Customer on sales; Company on self-billed purchases)."
		),
		"translatable": 0,
	},
]

PARTY_ZONE_FIELDS = [
	{
		"fieldname": "uae_in_designated_zone",
		"label": "In Designated Zone",
		"fieldtype": "Check",
		"insert_after": "uae_fz_beneficiary_id",
		"description": "Party is in a UAE Designated Zone. Goods remaining in-zone may be out of scope of VAT.",
		"default": "0",
	},
]

INVOICE_E_INVOICE_FIELDS = [
	{
		"fieldname": "uae_e_invoice_section",
		"label": "UAE E-Invoicing",
		"fieldtype": "Section Break",
		"insert_after": "tourist_tax_return",
		"collapsible": 1,
	},
	{
		"fieldname": "uae_document_type_code",
		"label": "UAE Document Type Code",
		"fieldtype": "Select",
		"options": "\n380\n381\n480\n81",
		"insert_after": "uae_e_invoice_section",
		"description": (
			"UNCL 1001: 380=Commercial Invoice, 381=Credit Note, "
			"480=Out of Scope Invoice, 81=Out of Scope Credit Note. "
			"Leave blank to derive automatically."
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_transaction_type_code",
		"label": "UAE Transaction Type Code",
		"fieldtype": "Data",
		"default": "00000000",
		"insert_after": "uae_document_type_code",
		"description": (
			"BTAE-02: 8-digit flag string — positions: 1 Free Trade Zone, 2 Deemed supply, "
			"3 Margin scheme, 4 Summary invoice, 5 Continuous supply, "
			"6 Disclosed agent billing, 7 E-commerce, 8 Export"
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_principal_trn",
		"label": "Principal TRN",
		"fieldtype": "Data",
		"insert_after": "uae_transaction_type_code",
		"depends_on": 'eval:(doc.uae_transaction_type_code || "").charAt(5) == "1"',
		"mandatory_depends_on": 'eval:(doc.uae_transaction_type_code || "").charAt(5) == "1"',
		"description": (
			"BTAE-14. UAE TRN of the principal on a disclosed-agent invoice. "
			"Must differ from the seller TRN (IBR-176-AE)."
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_billing_frequency",
		"label": "Billing Frequency",
		"fieldtype": "Select",
		"options": BILLING_FREQUENCY_SELECT_OPTIONS,
		"insert_after": "uae_transaction_type_code",
		"description": (
			"IBG-14 InvoicePeriod description code. Required for Deemed Supply, Summary Invoice, "
			"or Continuous Supply (BTAE-02). Not required merely because a Payment Due Date is set."
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_payment_means_code",
		"label": "UAE Payment Means",
		"fieldtype": "Select",
		"options": PAYMENT_MEANS_SELECT_OPTIONS,
		"default": "30 - Credit transfer",
		"insert_after": "uae_billing_frequency",
		"description": "IBT-081 (UNCL 4461). POS payments use the Mode of Payment code instead.",
		"depends_on": "eval:!doc.is_return",
		"translatable": 0,
	},
	{
		"fieldname": "uae_credit_note_reason",
		"label": "UAE Credit Note Reason",
		"fieldtype": "Small Text",
		"insert_after": "uae_payment_means_code",
		"depends_on": "eval:doc.is_return",
		"mandatory_depends_on": "eval:doc.is_return",
		"description": (
			"BTAE-03. Sent as CreditNoteReasonCode. Use SUPPLY_CANCELLED, "
			"TAX_TREATMENT_CHANGED, CONSIDERATION_ALTERED, GOODS_OR_SERVICES_RETURNED, "
			"TAX_APPLIED_IN_ERROR, or VOLUME_DISCOUNT."
		),
	},
	{
		"fieldname": "uae_return_against_external",
		"label": "External Return Against",
		"fieldtype": "Data",
		"insert_after": "uae_credit_note_reason",
		"depends_on": "eval:doc.is_return && !doc.return_against",
		"description": (
			"IBT-025: number of the original invoice when it was issued outside "
			"this system (pre-go-live or another ERP)"
		),
		"no_copy": 1,
		"translatable": 0,
	},
	{
		"fieldname": "uae_e_invoice_column",
		"fieldtype": "Column Break",
		"insert_after": "uae_return_against_external",
	},
	{
		"fieldname": "uae_e_invoice_status",
		"label": "UAE E-Invoice Status",
		"fieldtype": "Select",
		"options": "\nDraft\nGenerated\nQueued\nSubmitted\nAccepted\nRejected\nFailed\nCancelled",
		"insert_after": "uae_e_invoice_column",
		"read_only": 1,
		"allow_on_submit": 1,
		"no_copy": 1,
		"in_standard_filter": 1,
		"translatable": 0,
	},
	{
		"fieldname": "uae_e_invoice_log",
		"label": "UAE E-Invoice Log",
		"fieldtype": "Link",
		"options": "UAE E-Invoice Log",
		"insert_after": "uae_e_invoice_status",
		"read_only": 1,
		"allow_on_submit": 1,
		"no_copy": 1,
	},
]

PURCHASE_VAT_OPS_FIELDS = [
	{
		"fieldname": "uae_box_9_manual",
		"label": "Manual Box 9 Amount",
		"fieldtype": "Check",
		"insert_after": "recoverable_standard_rated_expenses",
		"description": "When checked, TaxMate will not recalculate Recoverable Standard Rated Expenses.",
		"default": "0",
	},
	{
		"fieldname": "uae_box_9_taxable_amount",
		"label": "Box 9 Taxable Amount (AED)",
		"fieldtype": "Currency",
		"insert_after": "uae_box_9_manual",
		"description": "Taxable consideration for VAT 201 Box 9 (lines with recoverable input tax only).",
		"read_only_depends_on": "eval:!doc.uae_box_9_manual",
	},
	{
		"fieldname": "uae_credit_note_reason",
		"label": "UAE Credit Note Reason",
		"fieldtype": "Small Text",
		"insert_after": "uae_box_9_taxable_amount",
		"depends_on": "eval:doc.is_return",
		"mandatory_depends_on": "eval:doc.is_return",
		"description": (
			"BTAE-03. Sent as CreditNoteReasonCode. Use SUPPLY_CANCELLED, "
			"TAX_TREATMENT_CHANGED, CONSIDERATION_ALTERED, GOODS_OR_SERVICES_RETURNED, "
			"TAX_APPLIED_IN_ERROR, or VOLUME_DISCOUNT."
		),
	},
	{
		"fieldname": "uae_return_against_external",
		"label": "External Return Against",
		"fieldtype": "Data",
		"insert_after": "uae_credit_note_reason",
		"depends_on": "eval:doc.is_return && !doc.return_against",
		"description": "Number of the original invoice when it was issued outside this system.",
		"no_copy": 1,
		"translatable": 0,
	},
]

PURCHASE_INVOICE_E_INVOICE_FIELDS = [
	{
		"fieldname": "uae_e_invoice_section",
		"label": "UAE E-Invoicing (Self-Billed)",
		"fieldtype": "Section Break",
		"insert_after": "recoverable_reverse_charge",
		"collapsible": 1,
	},
	{
		"fieldname": "uae_submit_to_fta",
		"label": "Submit as Self-Billed E-Invoice",
		"fieldtype": "Check",
		"insert_after": "uae_e_invoice_section",
		"description": "Generate a self-billed e-invoice (389/361) for this purchase",
		"default": "0",
	},
	{
		"fieldname": "uae_document_type_code",
		"label": "UAE Document Type Code",
		"fieldtype": "Select",
		"options": "\n389\n361",
		"insert_after": "uae_submit_to_fta",
		"description": "UNCL 1001: 389=Self-Billed Invoice, 361=Self-Billed Credit Note. Leave blank to derive.",
		"depends_on": "uae_submit_to_fta",
		"translatable": 0,
	},
	{
		"fieldname": "uae_transaction_type_code",
		"label": "UAE Transaction Type Code",
		"fieldtype": "Data",
		"default": "00000000",
		"insert_after": "uae_document_type_code",
		"depends_on": "uae_submit_to_fta",
		"description": (
			"BTAE-02: 8-digit flag string — positions: 1 Free Trade Zone, 2 Deemed supply, "
			"3 Margin scheme, 4 Summary invoice, 5 Continuous supply, "
			"6 Disclosed agent billing, 7 E-commerce, 8 Export"
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_principal_trn",
		"label": "Principal TRN",
		"fieldtype": "Data",
		"insert_after": "uae_transaction_type_code",
		"depends_on": (
			"eval:doc.uae_submit_to_fta && "
			'(doc.uae_transaction_type_code || "").charAt(5) == "1"'
		),
		"mandatory_depends_on": (
			"eval:doc.uae_submit_to_fta && "
			'(doc.uae_transaction_type_code || "").charAt(5) == "1"'
		),
		"description": (
			"BTAE-14. UAE TRN of the principal on a disclosed-agent invoice. "
			"Must differ from the seller TRN (IBR-176-AE)."
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_billing_frequency",
		"label": "Billing Frequency",
		"fieldtype": "Select",
		"options": BILLING_FREQUENCY_SELECT_OPTIONS,
		"insert_after": "uae_transaction_type_code",
		"depends_on": "uae_submit_to_fta",
		"description": (
			"IBG-14 InvoicePeriod description code. Required for Deemed Supply, Summary Invoice, "
			"or Continuous Supply (BTAE-02). Not required merely because a Payment Due Date is set."
		),
		"translatable": 0,
	},
	{
		"fieldname": "uae_payment_means_code",
		"label": "UAE Payment Means",
		"fieldtype": "Select",
		"options": PAYMENT_MEANS_SELECT_OPTIONS,
		"default": "30 - Credit transfer",
		"insert_after": "uae_billing_frequency",
		"depends_on": "uae_submit_to_fta",
		"translatable": 0,
	},
	{
		"fieldname": "uae_e_invoice_column",
		"fieldtype": "Column Break",
		"insert_after": "uae_payment_means_code",
	},
	{
		"fieldname": "uae_e_invoice_status",
		"label": "UAE E-Invoice Status",
		"fieldtype": "Select",
		"options": "\nDraft\nGenerated\nQueued\nSubmitted\nAccepted\nRejected\nFailed\nCancelled",
		"insert_after": "uae_e_invoice_column",
		"read_only": 1,
		"allow_on_submit": 1,
		"no_copy": 1,
		"in_standard_filter": 1,
		"translatable": 0,
	},
	{
		"fieldname": "uae_e_invoice_log",
		"label": "UAE E-Invoice Log",
		"fieldtype": "Link",
		"options": "UAE E-Invoice Log",
		"insert_after": "uae_e_invoice_status",
		"read_only": 1,
		"allow_on_submit": 1,
		"no_copy": 1,
	},
]

INVOICE_ITEM_FIELDS = [
	{
		"fieldname": "uae_item_type",
		"label": "UAE Item Type",
		"fieldtype": "Select",
		"options": "\nGoods\nService\nBoth",
		"insert_after": "item_code",
		"fetch_from": "item_code.uae_item_type",
		"fetch_if_empty": 1,
		"print_hide": 1,
		"translatable": 0,
	},
	{
		"fieldname": "hs_code",
		"label": "HS Code",
		"fieldtype": "Data",
		"insert_after": "uae_item_type",
		"fetch_from": "item_code.hs_code",
		"fetch_if_empty": 1,
		"depends_on": "eval:in_list(['Goods','Both'], doc.uae_item_type)",
		"print_hide": 1,
		"translatable": 0,
	},
	{
		"fieldname": "sac_code",
		"label": "SAC Code",
		"fieldtype": "Data",
		"insert_after": "hs_code",
		"fetch_from": "item_code.sac_code",
		"fetch_if_empty": 1,
		"depends_on": "eval:in_list(['Service','Both'], doc.uae_item_type)",
		"print_hide": 1,
		"translatable": 0,
	},
	{
		"fieldname": "uae_excise_category",
		"label": "UAE Excise Category",
		"fieldtype": "Select",
		"options": "\nTobacco and tobacco products\nCarbonated drinks\nEnergy drinks\nSweetened drinks\nElectronic smoking devices\nLiquids used in electronic smoking devices",
		"insert_after": "sac_code",
		"fetch_from": "item_code.uae_excise_category",
		"fetch_if_empty": 1,
		"print_hide": 1,
		"translatable": 0,
	},
	{
		"fieldname": "uae_is_margin_scheme",
		"label": "Margin Scheme",
		"fieldtype": "Check",
		"insert_after": "uae_excise_category",
		"fetch_from": "item_code.uae_is_margin_scheme",
		"fetch_if_empty": 1,
		"default": "0",
		"print_hide": 1,
	},
	{
		"fieldname": "uae_purchase_price",
		"label": "Margin Scheme Purchase Price (AED)",
		"fieldtype": "Currency",
		"options": "AED",
		"insert_after": "uae_is_margin_scheme",
		"depends_on": "eval:doc.uae_is_margin_scheme",
		"description": "Line purchase consideration. On a credit note, scale this to the returned quantity.",
		"print_hide": 1,
	},
	{
		"fieldname": "uae_margin_amount",
		"label": "Taxable Margin (AED)",
		"fieldtype": "Currency",
		"options": "AED",
		"insert_after": "uae_purchase_price",
		"read_only": 1,
		"depends_on": "eval:doc.uae_is_margin_scheme",
		"print_hide": 1,
	},
	{
		"fieldname": "uae_margin_vat",
		"label": "VAT on Margin (AED)",
		"fieldtype": "Currency",
		"options": "AED",
		"insert_after": "uae_margin_amount",
		"read_only": 1,
		"depends_on": "eval:doc.uae_is_margin_scheme",
		"print_hide": 1,
	},
]

CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "uae_e_invoicing_section",
			"label": "UAE E-Invoicing",
			"fieldtype": "Section Break",
			"insert_after": "tax_id",
			"collapsible": 1,
		},
		{
			"fieldname": "uae_e_invoice_enabled",
			"label": "Enable UAE E-Invoicing",
			"fieldtype": "Check",
			"insert_after": "uae_e_invoicing_section",
			"default": "0",
		},
		{
			"fieldname": "trade_license_number",
			"label": "Trade License Number",
			"fieldtype": "Data",
			"insert_after": "uae_e_invoice_enabled",
			"translatable": 0,
		},
		{
			"fieldname": "legal_registration_identifier_type",
			"label": "Legal Registration Identifier Type",
			"fieldtype": "Select",
			"options": "\nTL\nEID\nPAS\nCD",
			"insert_after": "trade_license_number",
			"translatable": 0,
		},
		{
			"fieldname": "legal_registration_identifier",
			"label": "Legal Registration Identifier",
			"fieldtype": "Data",
			"insert_after": "legal_registration_identifier_type",
			"translatable": 0,
		},
		{
			"fieldname": "uae_licence_authority",
			"label": "Licence Authority",
			"fieldtype": "Data",
			"insert_after": "legal_registration_identifier",
			"description": "Authority that issued the trade licence. Required on the e-invoice when the registration type is TL.",
			"translatable": 0,
		},
		{
			"fieldname": "uae_peppol_id",
			"label": "Peppol Participant ID",
			"fieldtype": "Data",
			"insert_after": "uae_licence_authority",
			"description": "Company's Peppol endpoint identifier registered with the ASP",
			"translatable": 0,
		},
		{
			"fieldname": "uae_fz_beneficiary_id",
			"label": "FZ Beneficiary ID",
			"fieldtype": "Data",
			"insert_after": "uae_peppol_id",
			"description": (
				"BTAE-01 / IBR-007-ae: buyer FZ identifier when this company is the "
				"AccountingCustomerParty (self-billed Purchase Invoice)."
			),
			"translatable": 0,
		},
		{
			"fieldname": "uae_in_designated_zone",
			"label": "In Designated Zone",
			"fieldtype": "Check",
			"insert_after": "uae_fz_beneficiary_id",
			"description": "Company establishment is in a UAE Designated Zone for VAT place-of-supply rules.",
			"default": "0",
		},
		{
			"fieldname": "taxmate_practice_section",
			"label": "TaxMate Practice",
			"fieldtype": "Section Break",
			"insert_after": "uae_in_designated_zone",
			"collapsible": 1,
		},
		{
			"fieldname": "taxmate_vat_filing_frequency",
			"label": "VAT Return Frequency",
			"fieldtype": "Select",
			"options": "\nMonthly\nQuarterly",
			"insert_after": "taxmate_practice_section",
			"description": (
				"How often this company files VAT 201. Used to work out the next return period and its 28th-of-month due date when no UAE VAT 201 Filing Log exists yet. Leave empty to show the period only when a filing log is present."
			),
		},
		{
			"fieldname": "taxmate_vat_first_period_start",
			"label": "VAT Period Start (Stagger)",
			"fieldtype": "Date",
			"insert_after": "taxmate_vat_filing_frequency",
			"depends_on": "eval:doc.taxmate_vat_filing_frequency=='Quarterly'",
			"description": (
				"First day of any one known quarterly VAT period, so the FTA stagger can be derived. Monthly filers do not need it."
			),
		},
		{
			"fieldname": "taxmate_assigned_accountant",
			"label": "Assigned Accountant",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "taxmate_vat_first_period_start",
			"description": (
				"Who in the practice is responsible for this client. This is ownership, not access: who may SEE a company is decided by User Permission on Company."
			),
		},
	],
	"Customer": PARTY_LEGAL_FIELDS + PARTY_ZONE_FIELDS,
	"Supplier": PARTY_LEGAL_FIELDS + PARTY_ZONE_FIELDS,
	"Item": [
		{
			"fieldname": "uae_classification_section",
			"label": "UAE Classification",
			"fieldtype": "Section Break",
			"insert_after": "is_exempt",
			"collapsible": 1,
		},
		{
			"fieldname": "uae_item_type",
			"label": "UAE Item Type",
			"fieldtype": "Select",
			"options": "\nGoods\nService\nBoth",
			"insert_after": "uae_classification_section",
			"translatable": 0,
		},
		{
			"fieldname": "hs_code",
			"label": "HS Code",
			"fieldtype": "Data",
			"insert_after": "uae_item_type",
			"depends_on": "eval:in_list(['Goods','Both'], doc.uae_item_type)",
			"translatable": 0,
		},
		{
			"fieldname": "sac_code",
			"label": "SAC Code",
			"fieldtype": "Data",
			"insert_after": "hs_code",
			"depends_on": "eval:in_list(['Service','Both'], doc.uae_item_type)",
			"translatable": 0,
		},
		{
			"fieldname": "uae_excise_category",
			"label": "UAE Excise Category",
			"fieldtype": "Select",
			"options": "\nTobacco and tobacco products\nCarbonated drinks\nEnergy drinks\nSweetened drinks\nElectronic smoking devices\nLiquids used in electronic smoking devices",
			"insert_after": "sac_code",
			"description": "Set only if this item is an excise good. Leave blank if the tenant does not sell excise products.",
			"translatable": 0,
		},
		{
			"fieldname": "uae_is_margin_scheme",
			"label": "Margin Scheme Item",
			"fieldtype": "Check",
			"insert_after": "uae_excise_category",
			"default": "0",
			"description": "Used goods sold under the VAT margin scheme. VAT 201 reports the margin, not full consideration.",
		},
	],
	"Item Tax Template": [
		{
			"fieldname": "uae_vat_section",
			"label": "UAE VAT",
			"fieldtype": "Section Break",
			"insert_after": "taxes",
			"collapsible": 1,
		},
		{
			"fieldname": "uae_vat_category",
			"label": "UAE VAT Category",
			"fieldtype": "Select",
			"options": "\nStandard\nZero Rated\nExempt\nOut of Scope\nReverse Charge\nMargin Scheme",
			"insert_after": "uae_vat_section",
			"translatable": 0,
		},
		{
			"fieldname": "uae_exemption_reason",
			"label": "UAE Exemption Reason",
			"fieldtype": "Small Text",
			"insert_after": "uae_vat_category",
			"depends_on": "eval:in_list(['Zero Rated','Exempt','Out of Scope'], doc.uae_vat_category)",
		},
		{
			"fieldname": "uae_rcm_nature",
			"label": "UAE RCM Type",
			"fieldtype": "Select",
			"options": (
				"\nELECTRONIC_DEVICES\nGOLD_AND_DIAMONDS\nCRUDE_OR_REFINED_OIL"
				"\nUNPROCESSED_OR_PROCESSED_NATURAL_GAS\nPURE_HYDROCARBONS"
			),
			"insert_after": "uae_exemption_reason",
			"depends_on": "eval:doc.uae_vat_category=='Reverse Charge'",
			"description": "FTA reverse-charge category. Sent as Reverse Charge Mechanism Type.",
			"translatable": 0,
		},
		{
			"fieldname": "uae_blocked_input_tax",
			"label": "Blocked Input Tax",
			"fieldtype": "Check",
			"insert_after": "uae_rcm_nature",
			"description": "When checked, VAT on purchases using this template is not recoverable (Box 9 = 0 for those lines). Use for entertainment, motor vehicles, and non-business spend.",
			"default": "0",
		},
		{
			"fieldname": "uae_input_tax_block_reason",
			"label": "Blocked Input Tax Reason",
			"fieldtype": "Select",
			"options": "\nEntertainment\nMotor Vehicle\nNon-business\nOther",
			"insert_after": "uae_blocked_input_tax",
			"depends_on": "eval:doc.uae_blocked_input_tax || doc.uae_input_tax_block_reason",
			"description": "FTA blocked categories: entertainment, motor vehicles, non-business use.",
			"translatable": 0,
		},
		{
			"fieldname": "uae_input_tax_recovery_percent",
			"label": "Input Tax Recovery %",
			"fieldtype": "Percent",
			"insert_after": "uae_input_tax_block_reason",
			"description": "Share of input VAT recoverable on this template (100 = full recovery). Ignored when Blocked Input Tax is set.",
			"default": "100",
			"depends_on": "eval:!doc.uae_blocked_input_tax && !doc.uae_input_tax_block_reason",
		},
	],
	"Mode of Payment": [
		{
			"fieldname": "uae_payment_means_code",
			"label": "UAE Payment Means Code",
			"fieldtype": "Select",
			"options": PAYMENT_MEANS_SELECT_OPTIONS,
			"insert_after": "type",
			"description": "UNCL 4461 payment means used on UAE e-invoices (IBT-081)",
			"translatable": 0,
		},
	],
	"Sales Invoice": [
		*INVOICE_E_INVOICE_FIELDS,
		{
			"fieldname": "uae_establishment",
			"label": "UAE Establishment",
			"fieldtype": "Link",
			"options": "UAE Establishment",
			"insert_after": "company",
			"description": "Mainland / Free Zone / Designated Zone establishment that made this supply.",
		},
	],
	"Purchase Invoice": [
		*PURCHASE_VAT_OPS_FIELDS,
		*PURCHASE_INVOICE_E_INVOICE_FIELDS,
		{
			"fieldname": "uae_customs_declaration",
			"label": "UAE Customs Declaration",
			"fieldtype": "Link",
			"options": "UAE Customs Declaration",
			"insert_after": "bill_no",
			"description": "Import bill that feeds VAT 201 Box 6/7 for this purchase.",
		},
		{
			"fieldname": "uae_establishment",
			"label": "UAE Establishment",
			"fieldtype": "Link",
			"options": "UAE Establishment",
			"insert_after": "company",
			"description": "Mainland / Free Zone / Designated Zone establishment that received this purchase.",
		},
	],
	"Sales Invoice Item": INVOICE_ITEM_FIELDS,
	"Purchase Invoice Item": INVOICE_ITEM_FIELDS,
	# Same Select as erpnext/regional/united_arab_emirates/setup.py sales_invoice_fields.
	# fetch_if_empty: Desk fetch_from runs in _validate_links and overwrites a
	# typed value (blank company-address emirate clears it). Keep a chosen
	# emirate; fill only when the quotation does not have one yet.
	"Quotation": [
		{
			"fieldname": "vat_emirate",
			"label": "VAT Emirate",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(UAE_EMIRATES),
			"insert_after": "taxes_and_charges",
			"fetch_from": "company_address.emirate",
			"fetch_if_empty": 1,
			"translatable": 0,
		},
	],
	"Landed Cost Voucher": [
		{
			"fieldname": "uae_customs_declaration",
			"label": "UAE Customs Declaration",
			"fieldtype": "Link",
			"options": "UAE Customs Declaration",
			"insert_after": "company",
		},
	],
}
