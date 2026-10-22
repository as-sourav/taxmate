"""Phase 9 fixture company: one unused FY 2026 period with every VAT 201 flavour.

Uses the existing UAE company (Ascra Technology LLP). Walk-in customer has no TRN so
B2C e-invoice exclusion keeps ASP jobs off these invoices. Documents are
meant to live inside a FrappeTestCase transaction and roll back.
"""

from __future__ import annotations

import csv
import io

import frappe
from frappe.utils import flt

from taxmate.uae.constants import UAE_COUNTRY
from taxmate.uae.validation import is_valid_uae_trn

COMPANY_NAME = "Ascra Technology LLP"
PERIOD_START = "2026-12-01"
PERIOD_END = "2026-12-31"
WALK_IN = "TM Prove Walk-in"
ZERO_ITEM = "TM-PROVE-ZERO"
EXEMPT_ITEM = "TM-PROVE-EXEMPT"
SERVICE_ITEM = "DEMO-VAT-CONSULTING"

# Ledger amounts posted by build_prove_set (AED). Box 1 includes the tourist
# supply; Box 2 then refunds that VAT. Credit note nets the standard invoice.
GOLDEN = {
	"1b": {"amount": 500.0, "vat_amount": 25.0},
	"2": {"amount": -500.0, "vat_amount": -25.0},
	"3": {"amount": 400.0, "vat_amount": 20.0},
	"4": {"amount": 200.0, "vat_amount": 0.0},
	"5": {"amount": 300.0, "vat_amount": 0.0},
	"6": {"amount": 800.0, "vat_amount": 40.0},
	"7": {"amount": 0.0, "vat_amount": 0.0},
	"8": {"vat_amount": 60.0},
	"9": {"amount": 0.0, "vat_amount": 0.0},
	"10": {"amount": 400.0, "vat_amount": 20.0},
	"11": {"vat_amount": 20.0},
	"12": {"vat_amount": 60.0},
	"13": {"vat_amount": 20.0},
	"14": {"vat_amount": 40.0},
}

PHASE_DOCTYPES = (
	"TaxMate Settings",
	"UAE VAT 201 Filing Log",
	"UAE VAT 201 Box Detail",
	"UAE Customs Declaration",
	"UAE Late Filing Notice",
	"UAE FTA Audit Pack",
	"UAE VAT Group",
	"UAE VAT Group Member",
	"UAE Establishment",
	"UAE VAT Audit Event",
	"UAE Excise Settings",
	"UAE Excise Filing Log",
	"UAE Capital Goods Record",
	"UAE Capital Goods Adjustment",
	"UAE Bad Debt Relief",
	"UAE E-Invoice Log",
	"UAE E-Invoice Contingency",
	"UAE Incoming Invoice",
	"UAE E-Invoice Webhook Log",
	"UAE Tax Settings",
	"UAE CT Settings",
	"UAE CT Filing Log",
	"UAE Related Party",
	"UAE CT Withholding Entry",
	"UAE UBO Register",
	"UAE ESR Filing",
	"UAE Shareholder Register",
	"UAE Compliance Settings",
)

PHASE_REPORTS = (
	"UAE Late Filing Status",
	"UAE Group VAT Status",
	"UAE Import VAT Explanation",
	"UAE E-Invoice Status",
	"UAE E-Invoice VAT 201 Reconciliation",
	"UAE Corporate Tax Worksheet",
	"UAE Compliance Status",
	"EmaraTax Export",
)

SUBMITTABLE_AFTER_MIGRATE = (
	"UAE VAT 201 Filing Log",
	"UAE CT Filing Log",
	"UAE ESR Filing",
	"UAE FTA Audit Pack",
	"UAE Customs Declaration",
	"UAE VAT Group",
	"UAE Excise Filing Log",
	"UAE Bad Debt Relief",
	"UAE Capital Goods Adjustment",
)


def uae_company() -> str | None:
	name = frappe.db.get_value("Company", {"country": UAE_COUNTRY}, "name")
	if name and is_valid_uae_trn(frappe.db.get_value("Company", name, "tax_id") or ""):
		return name
	return None


def require_prove_site() -> str:
	"""Return the UAE company or skip via exception for the caller to skipTest."""
	company = uae_company()
	if not company:
		raise frappe.DoesNotExistError("No UAE company with a 15-digit TRN")
	if not frappe.db.exists("Item", SERVICE_ITEM):
		raise frappe.DoesNotExistError(f"Missing service item {SERVICE_ITEM}")
	if not frappe.db.exists("Supplier", "Desert Supplies LLC"):
		raise frappe.DoesNotExistError("Missing supplier Desert Supplies LLC")
	if not frappe.db.exists("Fiscal Year", "2026"):
		raise frappe.DoesNotExistError("Fiscal Year 2026 is required for the prove-it period")
	if company != COMPANY_NAME:
		raise frappe.DoesNotExistError(f"Prove-it fixtures target company {COMPANY_NAME}")
	return company


def _ensure_walk_in():
	if frappe.db.exists("Customer", WALK_IN):
		return
	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": WALK_IN,
			"customer_type": "Individual",
			"customer_group": "Individual",
			"territory": "United Arab Emirates",
		}
	).insert()


def _ensure_item(code: str, **flags):
	if frappe.db.exists("Item", code):
		return
	tax_template = flags.pop("tax_template", None)
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"item_group": "Services",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"uae_item_type": "Service",
			"sac_code": "998311",
			**flags,
			"item_defaults": [
				{
					"company": COMPANY_NAME,
					"income_account": "Sales Account - TM",
					"expense_account": "Cost of Goods Sold in Trading - TM",
				}
			],
			"taxes": [{"item_tax_template": tax_template}] if tax_template else [],
		}
	).insert()


def _sales_invoice(company: str, item: str, rate: float, taxes: str, **kwargs) -> "frappe.Document":
	qty = kwargs.pop("qty", 1)
	posting_date = kwargs.pop("posting_date", PERIOD_START)
	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": company,
			"customer": WALK_IN,
			"posting_date": posting_date,
			"due_date": posting_date,
			"set_posting_time": 1,
			"currency": "AED",
			"conversion_rate": 1,
			"selling_price_list": "Standard Selling",
			"price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"vat_emirate": "Dubai",
			"taxes_and_charges": taxes,
			"items": [{"item_code": item, "qty": qty, "rate": rate}],
			**kwargs,
		}
	)
	doc.insert()
	doc.submit()
	return doc


def build_prove_set(company: str, period_start: str = PERIOD_START) -> dict:
	"""Post standard, zero, exempt, tourist, credit note, RCM, and import."""
	_ensure_walk_in()
	_ensure_item(ZERO_ITEM, is_zero_rated=1, tax_template="UAE VAT Zero - TM")
	_ensure_item(EXEMPT_ITEM, is_exempt=1, tax_template="UAE VAT Exempted - TM")

	standard = _sales_invoice(company, SERVICE_ITEM, 1000, "UAE VAT 5% - TM", posting_date=period_start)
	zero = _sales_invoice(company, ZERO_ITEM, 200, "UAE VAT Zero - TM", posting_date=period_start)
	exempt = _sales_invoice(company, EXEMPT_ITEM, 300, "UAE VAT Exempted - TM", posting_date=period_start)
	tourist = _sales_invoice(
		company, SERVICE_ITEM, 500, "UAE VAT 5% - TM", tourist_tax_return=25, posting_date=period_start
	)
	credit = _sales_invoice(
		company,
		SERVICE_ITEM,
		1000,
		"UAE VAT 5% - TM",
		qty=-1,
		is_return=1,
		return_against=standard.name,
		uae_credit_note_reason="GOODS_OR_SERVICES_RETURNED",
		posting_date=period_start,
	)

	rcm = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": "Desert Supplies LLC",
			"posting_date": period_start,
			"due_date": period_start,
			"set_posting_time": 1,
			"currency": "AED",
			"conversion_rate": 1,
			"buying_price_list": "Standard Buying",
			"price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"reverse_charge": "Y",
			"recoverable_reverse_charge": 100,
			"bill_no": f"TM-PROVE-RCM-{frappe.generate_hash(length=6)}",
			"bill_date": period_start,
			"update_stock": 0,
			"taxes_and_charges": "UAE VAT 5% - TM",
			"items": [{"item_code": SERVICE_ITEM, "qty": 1, "rate": 400}],
		}
	)
	rcm.insert()
	rcm.submit()

	customs = frappe.get_doc(
		{
			"doctype": "UAE Customs Declaration",
			"company": company,
			"posting_date": period_start,
			"declaration_number": f"TM-PROVE-IMP-{frappe.generate_hash(length=8)}",
			"taxable_amount": 800,
			"vat_amount": 40,
		}
	)
	customs.insert()
	customs.submit()

	return {
		"standard": standard,
		"zero": zero,
		"exempt": exempt,
		"tourist": tourist,
		"credit": credit,
		"rcm": rcm,
		"customs": customs,
	}


def boxes_by_no(result_or_doc) -> dict:
	rows = result_or_doc["boxes"] if isinstance(result_or_doc, dict) else result_or_doc.boxes
	out = {}
	for row in rows:
		box_no = row.box_no if hasattr(row, "box_no") else row["box_no"]
		out[box_no] = {
			"amount": flt(row.amount if hasattr(row, "amount") else row.get("amount")),
			"vat_amount": flt(row.vat_amount if hasattr(row, "vat_amount") else row.get("vat_amount")),
		}
	return out


def parse_boxes_csv(text: str) -> dict:
	seen_header = False
	out = {}
	for row in csv.reader(io.StringIO(text)):
		if not seen_header:
			if row[:1] == ["Box"]:
				seen_header = True
			continue
		if not row or not row[0] or row[0] == "Note":
			break
		out[row[0]] = {
			"amount": flt(row[2] if len(row) > 2 else 0),
			"vat_amount": flt(row[3] if len(row) > 3 else 0),
		}
	return out


def attached_file_content(doctype: str, name: str, prefix: str) -> str:
	file_name = frappe.db.get_value(
		"File",
		{"attached_to_doctype": doctype, "attached_to_name": name, "file_name": ("like", f"{prefix}%")},
		"name",
	)
	if not file_name:
		raise frappe.DoesNotExistError(f"No attached file starting {prefix} on {doctype} {name}")
	content = frappe.get_doc("File", file_name).get_content()
	if isinstance(content, bytes):
		return content.decode("utf-8")
	return content
