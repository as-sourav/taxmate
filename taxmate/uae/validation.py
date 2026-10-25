"""TRN and Address validation for UAE parties."""

from __future__ import annotations

import re

import frappe
from frappe import _

from taxmate.uae.constants import UAE_COUNTRY, UAE_EMIRATES, UAE_TRN_LENGTH

# IBR-132-AE: 15 digits, starts with 1, ends with 03.
_TRN_RE = re.compile(rf"^1\d{{{UAE_TRN_LENGTH - 3}}}03$")


def get_taxmate_settings():
	"""Return TaxMate Settings if the DocType exists, else None."""
	if not frappe.db.exists("DocType", "TaxMate Settings"):
		return None
	return frappe.get_single("TaxMate Settings")


def setting_enabled(fieldname: str, default: int = 0) -> bool:
	"""Read a TaxMate Settings Check, using ``default`` when the row is missing.

	Frappe Check values are 0/1, never None, after the first Singles save. New
	Checks on an existing Single stay 0 until a patch writes the intended default.
	"""
	settings = get_taxmate_settings()
	if not settings or not settings.meta.has_field(fieldname):
		return bool(default)
	if not singles_field_is_set(fieldname):
		return bool(default)
	return bool(settings.get(fieldname))


def singles_field_is_set(fieldname: str) -> bool:
	"""True when TaxMate Settings already has a tabSingles row for ``fieldname``."""
	if not frappe.db.exists("DocType", "TaxMate Settings"):
		return False
	return bool(frappe.db.exists("Singles", {"doctype": "TaxMate Settings", "field": fieldname}))


def normalize_trn(trn: str | None) -> str | None:
	if trn is None:
		return None
	cleaned = re.sub(r"\s+", "", str(trn).strip())
	return cleaned or None


def is_valid_uae_trn(trn: str | None) -> bool:
	normalized = normalize_trn(trn)
	if not normalized:
		return False
	return bool(_TRN_RE.match(normalized))


def validate_trn(trn: str | None, label: str = "Tax ID"):
	"""Raise if TRN is set but not a valid 15-digit UAE TRN."""
	normalized = normalize_trn(trn)
	if not normalized:
		return
	if not is_valid_uae_trn(normalized):
		frappe.throw(
			_("{0} must be a 15-digit UAE TRN starting with 1 and ending with 03.").format(label),
			title=_("Invalid TRN"),
		)


def should_enforce_trn() -> bool:
	settings = get_taxmate_settings()
	return bool(settings and settings.enforce_trn_validation)


def should_require_emirate() -> bool:
	settings = get_taxmate_settings()
	return bool(settings and settings.require_emirate_on_address)


def _normalize_tax_id_on_doc(doc) -> None:
	"""Strip whitespace from tax_id so stored value matches validation."""
	if not doc.get("tax_id"):
		return
	doc.tax_id = normalize_trn(doc.tax_id)


def validate_company_trn(doc, method=None):
	if doc.country != UAE_COUNTRY:
		return
	_normalize_tax_id_on_doc(doc)
	if should_enforce_trn():
		validate_trn(doc.tax_id, _("Company Tax ID (TRN)"))


def _party_is_uae(doc) -> bool:
	"""True when the party is clearly UAE-scoped (not via default-company fallback alone)."""
	if doc.doctype == "Supplier" and getattr(doc, "country", None) == UAE_COUNTRY:
		return True

	# Customer (and Supplier without country): use linked Address country
	if doc.name and not doc.is_new():
		addresses = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": doc.doctype,
				"link_name": doc.name,
				"parenttype": "Address",
			},
			pluck="parent",
		)
		for address_name in addresses:
			if frappe.db.get_value("Address", address_name, "country") == UAE_COUNTRY:
				return True

	return False


def validate_party_trn(doc, method=None):
	"""Validate Customer / Supplier tax_id when TaxMate enforces TRN for UAE parties."""
	if not should_enforce_trn():
		return
	if not _party_is_uae(doc):
		return

	_normalize_tax_id_on_doc(doc)
	label = _("Customer Tax ID (TRN)") if doc.doctype == "Customer" else _("Supplier Tax ID (TRN)")
	validate_trn(doc.tax_id, label)


def validate_address_emirate(doc, method=None):
	"""Require Emirate on UAE addresses when TaxMate setting is enabled."""
	if not should_require_emirate():
		return
	if doc.country != UAE_COUNTRY:
		return

	emirate = doc.get("emirate")
	if not emirate:
		frappe.throw(
			_("Emirate is required on addresses in {0}.").format(UAE_COUNTRY),
			title=_("Missing Emirate"),
		)
	if emirate not in UAE_EMIRATES:
		frappe.throw(
			_("Emirate must be one of: {0}").format(", ".join(UAE_EMIRATES)),
			title=_("Invalid Emirate"),
		)
