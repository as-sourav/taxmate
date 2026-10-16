"""TaxMate install / bootstrap hooks."""

from __future__ import annotations

import frappe


def after_install():
	"""Ensure UAE regional fixtures exist before the first company is onboarded."""
	from frappe.installer import add_module_defs

	from taxmate.uae.setup import (
		bootstrap_existing_uae_companies,
		ensure_uae_regional_setup,
		ensure_uae_system_country,
	)
	from taxmate.uae_vat.overrides.purchase_invoice import _bind_reverse_charge_region

	add_module_defs("taxmate", ignore_if_duplicate=True)
	# Blank System Settings country skips ERPNext's UAE reverse-charge credit.
	ensure_uae_system_country()
	_bind_reverse_charge_region()
	ensure_uae_regional_setup()
	_setup_vat_uae()
	_setup_e_invoicing_uae()
	_setup_ct_uae()
	bootstrap_existing_uae_companies()
	_setup_compliance_uae()
	_ensure_taxmate_settings_defaults()
	_ensure_product_branding()
	from taxmate.search import configure_global_search
	from taxmate.setup.desk_app import ensure_taxmate_desktop_icon
	from taxmate.setup.company_owner import ensure_company_owner_field
	from taxmate.setup.spa_roles import ensure_spa_roles
	from taxmate.setup.workspaces import ensure_product_workspaces

	configure_global_search()
	ensure_product_workspaces()
	ensure_spa_roles()
	ensure_company_owner_field()
	ensure_taxmate_desktop_icon()


def after_migrate():
	"""Re-apply UAE fixtures after migrate so SaaS sites stay current."""
	after_install()


def _setup_vat_uae():
	try:
		from taxmate.uae_vat.setup import setup as vat_uae_setup

		vat_uae_setup()
	except Exception:
		frappe.log_error(
			title="TaxMate UAE VAT setup failed",
			message=frappe.get_traceback(),
		)
		raise


def _setup_e_invoicing_uae():
	try:
		from taxmate.uae_e_invoicing.setup import setup as e_invoicing_setup

		e_invoicing_setup()
	except Exception:
		frappe.log_error(
			title="TaxMate UAE E-Invoicing setup failed",
			message=frappe.get_traceback(),
		)
		raise


def _setup_ct_uae():
	try:
		from taxmate.uae_corporate_tax.setup import setup as ct_uae_setup

		ct_uae_setup()
	except Exception:
		frappe.log_error(
			title="TaxMate UAE Corporate Tax setup failed",
			message=frappe.get_traceback(),
		)
		raise


def _setup_compliance_uae():
	try:
		from taxmate.uae_compliance.setup import (
			bootstrap_existing_uae_companies as bootstrap_compliance,
		)
		from taxmate.uae_compliance.setup import ensure_compliance_settings_defaults

		ensure_compliance_settings_defaults()
		bootstrap_compliance()
	except Exception:
		frappe.log_error(
			title="TaxMate UAE Compliance setup failed",
			message=frappe.get_traceback(),
		)
		raise


def _ensure_taxmate_settings_defaults():
	if not frappe.db.exists("DocType", "TaxMate Settings"):
		return

	from taxmate.uae.constants import UAE_COUNTRY
	from taxmate.uae.validation import singles_field_is_set

	settings = frappe.get_single("TaxMate Settings")
	changed = False
	if not settings.default_country:
		settings.default_country = UAE_COUNTRY
		changed = True
	if settings.enforce_trn_validation is None:
		settings.enforce_trn_validation = 1
		changed = True
	if settings.require_emirate_on_address is None:
		settings.require_emirate_on_address = 1
		changed = True
	for field, default in (
		("enforce_credit_note_reference", 1),
		("require_vat_emirate_on_invoice", 1),
		("block_e_invoice_until_ready", 1),
		("block_invoices_in_filed_vat_period", 1),
		("prefer_uae_hosted_files", 1),
	):
		if hasattr(settings, field) and not singles_field_is_set(field):
			setattr(settings, field, default)
			changed = True
	if hasattr(settings, "vat_201_reminder_days") and not singles_field_is_set("vat_201_reminder_days"):
		settings.vat_201_reminder_days = 7
		changed = True
	if hasattr(settings, "data_residency_note") and not singles_field_is_set("data_residency_note"):
		settings.data_residency_note = (
			"FTA record-keeping is 5+ years. Host this site in the UAE. "
			"Signed XML/PDF stay as private File records. TaxMate does not e-file."
		)
		changed = True
	notes = settings.onboarding_notes or ""
	if "ERPNext" in notes:
		settings.onboarding_notes = notes.replace("ERPNext", "TaxMate")
		changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()


def _ensure_product_branding():
	"""Show TaxMate (not Frappe/ERPNext) as the product name in Desk/browser chrome."""
	for doctype, field, value in (
		("System Settings", "app_name", "TaxMate"),
		("Website Settings", "app_name", "TaxMate"),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		current = frappe.db.get_single_value(doctype, field)
		if current in (None, "", "Frappe", "ERPNext", "frappe", "erpnext"):
			frappe.db.set_single_value(doctype, field, value)

	# ERPNext Settings is replaced by TaxMate Settings workspace (setup/workspaces.py)
	if frappe.db.exists("Workspace", "ERPNext Settings"):
		frappe.db.set_value(
			"Workspace",
			"ERPNext Settings",
			{"is_hidden": 1, "public": 0},
			update_modified=False,
		)

	if frappe.db.exists("DocType", "Navbar Item"):
		for label in frappe.get_all(
			"Navbar Item",
			filters={"item_label": ("in", ["Frappe Support", "ERPNext Support"])},
			pluck="name",
		):
			frappe.db.set_value("Navbar Item", label, "item_label", "TaxMate Support", update_modified=False)
