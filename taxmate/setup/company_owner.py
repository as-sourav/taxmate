"""Company primary TaxMate Owner mapping (custom_taxmate_owner on Company).

Administrator / System Manager are app providers — they assign an owner, they
never are the company owner. Membership of all teammates stays on User Permission.
"""

from __future__ import annotations

import frappe
from frappe import _

from taxmate.setup.spa_roles import MARKER
from taxmate.utils.custom_fields import get_custom_fields_creator

OWNER_FIELD = "custom_taxmate_owner"

CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": OWNER_FIELD,
			"label": "TaxMate Owner",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "company_name",
			"description": "Primary TaxMate Owner for this company. Not Administrator.",
		},
	],
}

create_custom_fields = get_custom_fields_creator("TaxMate")


def ensure_company_owner_field() -> None:
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)


def has_taxmate_marker(user: str) -> bool:
	roles = set(frappe.get_roles(user))
	return bool(roles.intersection(MARKER.values()))


def is_app_provider(user: str | None = None) -> bool:
	"""TaxMate SaaS operator — not a client company owner."""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	if "System Manager" in frappe.get_roles(user) and not has_taxmate_marker(user):
		return True
	return False


def is_forbidden_owner_user(user: str) -> bool:
	"""Administrator and System Manager must never be a company TaxMate Owner."""
	if not user or user == "Administrator":
		return True
	if "System Manager" in frappe.get_roles(user):
		return True
	return False


def validate_company_owner(doc) -> None:
	"""Company.validate — refuse forbidden users on custom_taxmate_owner."""
	owner = (doc.get(OWNER_FIELD) or "").strip()
	if not owner:
		return
	if not frappe.db.exists("User", owner):
		frappe.throw(_("TaxMate Owner {0} does not exist").format(owner))
	if is_forbidden_owner_user(owner):
		frappe.throw(_("Administrator cannot be the TaxMate Owner of a company"))
	roles = set(frappe.get_roles(owner))
	if MARKER["owner"] not in roles:
		frappe.throw(_("TaxMate Owner must hold the TaxMate Owner role"))
