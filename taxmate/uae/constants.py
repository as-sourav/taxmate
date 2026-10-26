"""UAE regional constants used by TaxMate orchestration and validation."""

UAE_COUNTRY = "United Arab Emirates"

UAE_EMIRATES = (
	"Abu Dhabi",
	"Ajman",
	"Dubai",
	"Fujairah",
	"Ras Al Khaimah",
	"Sharjah",
	"Umm Al Quwain",
)

# FTA TRN is a 15-digit numeric identifier
UAE_TRN_LENGTH = 15

# Tax template titles created by ERPNext for UAE companies
UAE_VAT_TAX_TEMPLATES = (
	"UAE VAT 5%",
	"UAE VAT Zero",
	"UAE VAT Exempted",
)

UAE_TAX_PRINT_FORMATS = (
	"Simplified Tax Invoice",
	"Detailed Tax Invoice",
	"Tax Invoice",
	"UAE Bilingual Tax Invoice",
	"UAE Bilingual Purchase Invoice",
)

# Payment receipt. Not part of the tax-invoice readiness check.
UAE_BILINGUAL_PAYMENT = "UAE Bilingual Payment"

# FTA Executive Regulations: simplified tax invoice allowed for B2C ≤ AED 10,000
SIMPLIFIED_TAX_INVOICE_THRESHOLD_AED = 10000.0
