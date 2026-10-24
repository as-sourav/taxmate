"""Submit / cancel / amend for allowlisted accounts documents."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.client import cancel as client_cancel

from taxmate.api.resource import _require_doc, assert_allowed_doctype, require_login
from taxmate.setup.spa_roles import STANDARD_ROLE_FOR_SPA, spa_role_of


def _holds_standard_role(spa: str | None) -> bool:
	"""Frontend role counts only when its standard Frappe role is on the user."""
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	if "System Manager" in roles:
		return True
	required = STANDARD_ROLE_FOR_SPA.get(spa or "")
	if not required:
		return False
	return required in roles


def _assert_can_submit() -> None:
	spa = spa_role_of()
	if spa == "viewer" or not _holds_standard_role(spa):
		frappe.throw(_("Viewers cannot submit"), frappe.PermissionError)


def _assert_can_cancel() -> None:
	spa = spa_role_of()
	if spa not in ("owner", "accountant") or not _holds_standard_role(spa):
		frappe.throw(_("Only an Owner or Accountant can cancel"), frappe.PermissionError)


@frappe.whitelist(methods=["POST", "PUT"])
def submit(doc):
	"""Submit by name. Reloads so clients need not send `modified`."""
	require_login()
	_assert_can_submit()
	doc = _require_doc(doc)
	name = doc.get("name")
	if not name:
		frappe.throw(_("name is required"))
	loaded = frappe.get_doc(doc["doctype"], name)
	loaded.check_permission("submit")
	loaded.submit()
	return loaded.as_dict()


@frappe.whitelist(methods=["POST", "PUT"])
def cancel(doctype, name):
	require_login()
	_assert_can_cancel()
	assert_allowed_doctype(doctype)
	return client_cancel(doctype, name)


@frappe.whitelist(methods=["POST"])
def amend(doctype: str, name: str):
	require_login()
	_assert_can_cancel()
	assert_allowed_doctype(doctype)
	source = frappe.get_doc(doctype, name)
	source.check_permission("amend")
	if source.docstatus != 2:
		frappe.throw(_("Only cancelled documents can be amended"))

	new_doc = frappe.copy_doc(source, ignore_no_copy=False)
	new_doc.docstatus = 0
	new_doc.amended_from = source.name
	new_doc.insert()
	return new_doc.as_dict()
