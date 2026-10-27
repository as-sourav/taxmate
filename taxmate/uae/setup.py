"""Ensure ERPNext UAE regional fixtures and company readiness via TaxMate."""

from __future__ import annotations

import frappe

from taxmate.uae.constants import (
	UAE_BILINGUAL_PAYMENT,
	UAE_COUNTRY,
	UAE_TAX_PRINT_FORMATS,
	UAE_VAT_TAX_TEMPLATES,
)


def ensure_uae_regional_setup(company: str | None = None) -> None:
	"""Idempotently apply ERPNext UAE regional setup (fields, prints, permissions)."""
	from erpnext.regional.united_arab_emirates.setup import setup as erpnext_uae_setup

	erpnext_uae_setup(company=company, patch=True)


def ensure_uae_system_country() -> bool:
	"""Set System Settings country when a UAE install left it blank.

	ERPNext's regional overrides, including the reverse-charge VAT credit,
	read this through ``erpnext.get_region()``. The setup wizard writes it.
	``bench new-site`` plus ``install-app`` does not. An existing country is
	left alone.
	"""
	from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache

	current = frappe.db.get_single_value("System Settings", "country")
	if current:
		return False
	if not frappe.db.exists("Country", UAE_COUNTRY):
		return False

	# set_single_value does not run System Settings.on_update, so the global
	# default stays blank and boot / Desk still read an empty country.
	frappe.db.set_single_value("System Settings", "country", UAE_COUNTRY)
	frappe.db.set_default("country", UAE_COUNTRY)
	frappe.local.system_settings = None
	clear_system_settings_cache()
	return True


def ensure_company_uae_ready(company: str) -> None:
	"""Verify / complete UAE readiness for a company after ERPNext country fixtures."""
	if not company:
		return

	country = frappe.db.get_value("Company", company, "country")
	if country != UAE_COUNTRY:
		return

	ensure_uae_system_country()
	ensure_uae_regional_setup(company=company)
	_ensure_print_formats_enabled()
	_ensure_uae_vat_settings_shell(company)
	ensure_item_tax_template_vat_categories(company)


def _ensure_print_formats_enabled() -> None:
	for name in (*UAE_TAX_PRINT_FORMATS, UAE_BILINGUAL_PAYMENT):
		if frappe.db.exists("Print Format", name):
			frappe.db.set_value("Print Format", name, "disabled", 0)


def _ensure_uae_vat_settings_shell(company: str) -> None:
	"""Create UAE VAT Settings when VAT accounts can be inferred from the company COA."""
	if frappe.db.exists("UAE VAT Settings", company):
		return

	vat_accounts = _guess_vat_accounts(company)
	if not vat_accounts:
		return

	doc = frappe.get_doc(
		{
			"doctype": "UAE VAT Settings",
			"company": company,
			"uae_vat_accounts": [{"account": account} for account in vat_accounts],
		}
	)
	doc.insert(ignore_permissions=True)


def _guess_vat_accounts(company: str) -> list[str]:
	"""Find VAT-related accounts created from UAE tax templates for this company."""
	accounts: list[str] = []
	for title_prefix in ("VAT 5%", "VAT Zero", "VAT Exempted"):
		name = frappe.db.get_value(
			"Account",
			{"account_name": title_prefix, "company": company, "is_group": 0},
			"name",
		)
		if name and name not in accounts:
			accounts.append(name)
	return accounts


def bootstrap_existing_uae_companies() -> None:
	"""Run company readiness for every UAE company already on the site."""
	companies = frappe.get_all("Company", filters={"country": UAE_COUNTRY}, pluck="name")
	for company in companies:
		ensure_company_uae_ready(company)


# Map ERPNext UAE Item Tax Template titles → TaxMate uae_vat_category
_ITEM_TAX_CATEGORY_BY_TITLE = {
	"UAE VAT 5%": "Standard",
	"UAE VAT Zero": "Zero Rated",
	"UAE VAT Exempted": "Exempt",
}


def ensure_item_tax_template_vat_categories(company: str | None = None) -> int:
	"""Stamp TaxMate ``uae_vat_category`` on ERPNext UAE Item Tax Templates.

	ERPNext creates the templates; TaxMate owns the PINT-AE category field.
	Returns the number of templates updated.
	"""
	if not frappe.db.has_column("Item Tax Template", "uae_vat_category"):
		return 0

	filters: dict = {}
	if company:
		filters["company"] = company

	updated = 0
	for title, category in _ITEM_TAX_CATEGORY_BY_TITLE.items():
		rows = frappe.get_all(
			"Item Tax Template",
			filters={**filters, "title": title},
			fields=["name", "uae_vat_category"],
		)
		# Fallback: name may be "UAE VAT 5% - ABBR"
		if not rows:
			like_filters = {**filters, "name": ["like", f"{title}%"]}
			rows = frappe.get_all(
				"Item Tax Template",
				filters=like_filters,
				fields=["name", "uae_vat_category"],
			)
		for row in rows:
			if row.uae_vat_category == category:
				continue
			frappe.db.set_value("Item Tax Template", row.name, "uae_vat_category", category)
			updated += 1
	return updated


def company_has_uae_tax_templates(company: str) -> bool:
	"""True if standard UAE VAT Sales Taxes and Charges Templates exist for company."""
	for template in UAE_VAT_TAX_TEMPLATES:
		exists = frappe.db.exists(
			"Sales Taxes and Charges Template",
			{"title": template, "company": company},
		) or frappe.db.sql(
			"""
			select name from `tabSales Taxes and Charges Template`
			where company = %s and (title = %s or name like %s)
			limit 1
			""",
			(company, template, f"{template}%"),
		)
		if not exists:
			return False
	return True
