"""Four TaxMate SPA roles. Marker Role.role_name only — no ERPNext Desk roles.

spa_role is owner, accountant, clerk, or viewer. Marker Roles have desk_access=0.
Display names: Owner, Accountant, Accounts User (clerk), Auditor (viewer).
The Frappe Administrator user keeps System Manager and Desk. SPA Admin is TaxMate Owner.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

SPA_ROLES: tuple[str, ...] = ("owner", "accountant", "clerk", "viewer")

MARKER: dict[str, str] = {
	"owner": "TaxMate Owner",
	"accountant": "TaxMate Accountant",
	"clerk": "TaxMate Accounts User",
	"viewer": "TaxMate Auditor",
}

# Older marker names → current (rename on migrate).
_LEGACY_MARKER_RENAMES: dict[str, str] = {
	"TaxMate Clerk": "TaxMate Accounts User",
	"TaxMate Accounts Officer": "TaxMate Accounts User",
	"TaxMate Viewer": "TaxMate Auditor",
}

# Current + legacy Role names (list_users Has Role lookup during transition).
ALL_MARKER_ROLE_NAMES: tuple[str, ...] = tuple(
	dict.fromkeys([*MARKER.values(), *_LEGACY_MARKER_RENAMES.keys()])
)

# Legacy Role.role_name → spa key (for session gates before rename finishes).
_LEGACY_SPA_KEYS: dict[str, str] = {
	"TaxMate Clerk": "clerk",
	"TaxMate Accounts Officer": "clerk",
	"TaxMate Viewer": "viewer",
}

# SPA bundles are marker-only. Desk ERPNext roles are listed so apply_spa_role strips them.
BUNDLE: dict[str, tuple[str, ...]] = {spa: (name,) for spa, name in MARKER.items()}

# POSNext add-ons — assigned via Team multi-select when those Role docs exist.
ADDON_ROLES: tuple[str, ...] = ("POSNext Cashier", "Nexus POS Manager")

LEGACY_DESK_ROLES: frozenset[str] = frozenset(
	{
		"Accounts Manager",
		"Accounts User",
		"Sales Manager",
		"Sales User",
		"Purchase Manager",
		"Purchase User",
		"UAE Tax Manager",
	}
)

# Desk roles spa_roles_of already treats as TaxMate roles. Custom DocPerm
# follows that map. ERPNext does not give Accounts Manager a Quotation row,
# so the sidebar list fails with Insufficient Permission.
_DESK_SPA: dict[str, str] = {
	"Accounts Manager": "accountant",
	"UAE Tax Manager": "accountant",
	"Accounts User": "clerk",
}

# Sidebar documents the search catalog does not name. Same DocPerm sync.
_SPA_BOOKS: tuple[str, ...] = (
	"Lead",
	"Supplier Quotation",
	"BOM",
	"Work Order",
	"Pick List",
	"POS Invoice",
	"POS Profile",
	"Loyalty Program",
	"Loyalty Point Entry",
	"Asset Category",
	"Currency Exchange",
)

MANAGED_ROLES: frozenset[str] = frozenset(
	(*MARKER.values(), *_LEGACY_MARKER_RENAMES.keys(), *LEGACY_DESK_ROLES)
)
READ_ONLY_DOCTYPES: frozenset[str] = frozenset({
	"GL Entry",
	"Fiscal Year",
	"IDP Extraction Template",
	"IDP Extraction Correction",
})
SETTINGS_DOCTYPES: frozenset[str] = frozenset(
	{
		"Company",
		"TaxMate Settings",
		"UAE Tax Settings",
		"Accounts Settings",
		"Selling Settings",
		"Buying Settings",
		"UAE VAT Settings",
	}
)

VIEWER_READ_DOCTYPES: tuple[str, ...] = (
	"Sales Invoice",
	"Sales Order",
	"Delivery Note",
	"Purchase Invoice",
	"Purchase Order",
	"Purchase Receipt",
	"Payment Entry",
	"Journal Entry",
	"Account",
	"Customer",
	"Supplier",
	"Item",
	"Warehouse",
	"Sales Taxes and Charges Template",
	"Purchase Taxes and Charges Template",
	"Item Tax Template",
	"Tax Category",
	"Payment Terms Template",
	"Terms and Conditions",
	"Brand",
	"UOM",
	"Customer Group",
	"Supplier Group",
	"Item Group",
	"Territory",
	"Cost Center",
	"Bank Account",
	"Fiscal Year",
	"Currency",
	"Item Price",
	"ToDo",
	"Mode of Payment",
	"Address",
	"Contact",
	"Company",
	"GL Entry",
	"TaxMate Settings",
	"Accounts Settings",
	"Selling Settings",
	"Buying Settings",
	"UAE Tax Settings",
	"UAE E-Invoice Log",
	"UAE VAT 201 Filing Log",
	"UAE CT Filing Log",
	"UAE ESR Filing",
	"UAE UBO Register",
	"UAE Late Filing Notice",
	"UAE Incoming Invoice",
)

_PERM_FLAGS: tuple[str, ...] = (
	"select",
	"read",
	"write",
	"create",
	"submit",
	"cancel",
	"amend",
	"delete",
	"print",
	"email",
	"report",
	"export",
	"share",
)


def website_user_home_page(user: str | None = None) -> str | None:
	"""Everyone except Administrator lands on /taxmate after login."""
	user = user or frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return None
	return "taxmate"


def _role_grants_desk(role: str) -> bool:
	if not role or not frappe.db.exists("Role", role):
		return False
	return bool(cint(frappe.db.get_value("Role", role, "desk_access")))


def ensure_marker_roles() -> None:
	"""Create TaxMate roles with desk_access=0. Zero desk on known SPA add-ons too."""
	_rename_legacy_markers()
	for name in MARKER.values():
		if frappe.db.exists("Role", name):
			if cint(frappe.db.get_value("Role", name, "desk_access")):
				frappe.db.set_value("Role", name, "desk_access", 0)
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": name,
				"desk_access": 0,
			}
		).insert(ignore_permissions=True)
	for name in ADDON_ROLES:
		if frappe.db.exists("Role", name) and cint(frappe.db.get_value("Role", name, "desk_access")):
			frappe.db.set_value("Role", name, "desk_access", 0)


def _rename_legacy_markers() -> None:
	"""TaxMate Clerk / Accounts Officer → Accounts User; Viewer → Auditor."""
	for old, new in _LEGACY_MARKER_RENAMES.items():
		if not frappe.db.exists("Role", old):
			continue
		if frappe.db.exists("Role", new):
			# Move Has Role rows then drop the legacy Role.
			frappe.db.sql(
				"""
				update `tabHas Role`
				set role = %s
				where role = %s
				and name not in (
					select name from (
						select name from `tabHas Role` where role = %s
					) t
				)
				""",
				(new, old, new),
			)
			frappe.db.sql(
				"""
				update `tabCustom DocPerm`
				set role = %s
				where role = %s
				and name not in (
					select name from (
						select name from `tabCustom DocPerm` where role = %s
					) t
				)
				""",
				(new, old, new),
			)
			frappe.delete_doc("Role", old, force=True, ignore_permissions=True)
			continue
		frappe.rename_doc("Role", old, new, force=True, merge=False)


def ensure_spa_roles() -> None:
	"""Create marker roles, books DocPerms, and lock non-Admin users to the SPA."""
	ensure_marker_roles()
	_ensure_books_perms()
	_ensure_scan_perms()
	_allow_reports()
	_strip_desk_roles_from_spa_users()
	_lock_non_admin_users_to_spa()


def available_addon_roles() -> list[str]:
	"""Return add-on Role names that exist on this site (e.g. after installing pos_next)."""
	return [name for name in ADDON_ROLES if frappe.db.exists("Role", name)]


def addon_roles_of(user: str | None = None) -> list[str]:
	"""Installed add-on roles currently assigned to the user."""
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	return [name for name in ADDON_ROLES if name in roles]


def spa_roles_of(user: str | None = None) -> list[str]:
	"""All TaxMate SPA markers on the user, highest first. System Manager → owner only."""
	user = user or frappe.session.user
	# Administrator is always the app provider — never a company SPA role,
	# even if TaxMate markers were wrongly assigned on the User.
	if user == "Administrator":
		return []
	roles = set(frappe.get_roles(user))
	found: list[str] = []
	for key in SPA_ROLES:
		if MARKER[key] in roles:
			found.append(key)
	for legacy, spa in _LEGACY_SPA_KEYS.items():
		if legacy in roles and spa not in found:
			found.append(spa)
	if found:
		# Keep SPA_ROLES priority order.
		return [key for key in SPA_ROLES if key in found]
	# App provider (Administrator / System Manager) is not a company SPA role.
	if user == "Administrator" or "System Manager" in roles:
		return []
	if "Accounts Manager" in roles or "UAE Tax Manager" in roles:
		return ["accountant"]
	# ERPNext Desk "Accounts User" (not TaxMate Accounts User) → clerk.
	if "Accounts User" in roles:
		return ["clerk"]
	return ["viewer"]


def spa_role_of(user: str | None = None) -> str | None:
	"""Highest SPA client role, or None for app providers with no TaxMate markers."""
	roles = spa_roles_of(user)
	return roles[0] if roles else None


def require_spa_role(*allowed: str) -> None:
	"""Reject the call unless the user holds one of these SPA roles.

	Administrator and System Manager pass. They are the product operators and
	stay on Frappe's own bypass, not a second TaxMate rule.
	"""
	user = frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return
	if spa_role_of(user) not in allowed:
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)


def apply_spa_role(user: str, spa_role: str) -> None:
	"""Assign a single TaxMate marker (preserves existing add-on roles)."""
	apply_spa_roles(user, [spa_role], extra_roles=None)


def apply_spa_roles(
	user: str,
	spa_roles: list[str] | tuple[str, ...] | None,
	extra_roles: list[str] | tuple[str, ...] | None = None,
) -> None:
	"""Assign one or more TaxMate markers plus optional add-ons. Frappe unions DocPerms."""
	if not spa_roles:
		frappe.throw(frappe._("At least one role is required"))
	normalized: list[str] = []
	for spa_role in spa_roles:
		if spa_role not in SPA_ROLES:
			frappe.throw(frappe._("Unknown role"))
		if spa_role not in normalized:
			normalized.append(spa_role)
	if user in ("Administrator", "Guest"):
		frappe.throw(frappe._("That user cannot be changed from TaxMate"))
	if "System Manager" in frappe.get_roles(user):
		frappe.throw(frappe._("System managers cannot be changed from TaxMate"), frappe.PermissionError)

	doc = frappe.get_doc("User", user)
	addon_set = frozenset(ADDON_ROLES)
	keep = []
	for row in doc.roles:
		role = row.role
		if role in MANAGED_ROLES or role == "System Manager" or role in addon_set:
			continue
		if _role_grants_desk(role):
			continue
		keep.append(role)
	if extra_roles is None:
		extras = [row.role for row in doc.roles if row.role in addon_set]
	else:
		allowed = frozenset(available_addon_roles())
		extras = []
		for role in extra_roles:
			if role in allowed and role not in extras:
				extras.append(role)

	markers = [MARKER[spa] for spa in normalized]
	wanted = tuple(dict.fromkeys([*keep, *markers, *extras]))
	current = tuple(row.role for row in doc.roles)
	needs_home = (doc.redirect_url or "") != "/taxmate" or getattr(doc, "default_app", None) != "taxmate"
	if doc.meta.has_field("default_workspace") and doc.get("default_workspace"):
		needs_home = True
	needs_website = doc.user_type != "Website User" and not doc.has_desk_access()
	if current == wanted and not needs_home and not needs_website:
		return

	if current != wanted:
		doc.set("roles", [])
		for role in wanted:
			if role and frappe.db.exists("Role", role):
				doc.append("roles", {"role": role})
	doc.redirect_url = "/taxmate"
	if hasattr(doc, "default_app"):
		doc.default_app = "taxmate"
	if doc.meta.has_field("default_workspace"):
		doc.default_workspace = None
	# Recompute after role rewrite — Website User cannot open /desk by URL.
	if not any(_role_grants_desk(row.role) for row in doc.roles):
		doc.user_type = "Website User"
	doc.save(ignore_permissions=True)
	frappe.clear_cache(user=user)


def _catalog_names() -> list[str]:
	try:
		from taxmate.api import catalog_doctypes

		return list(catalog_doctypes())
	except Exception:
		return list(VIEWER_READ_DOCTYPES)


def _perm_values(spa: str, doctype: str) -> dict[str, int]:
	read = {
		"select": 1,
		"read": 1,
		"print": 1,
		"email": 1,
		"report": 1,
		"export": 1,
		"share": 1,
		"write": 0,
		"create": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"delete": 0,
	}
	if spa == "viewer":
		return read
	settings = doctype in SETTINGS_DOCTYPES or doctype.endswith(" Settings")
	if doctype in READ_ONLY_DOCTYPES or (settings and spa == "clerk"):
		return read
	if settings and spa in ("owner", "accountant"):
		return {**read, "write": 1}
	submittable = False
	try:
		submittable = bool(frappe.get_meta(doctype).is_submittable)
	except Exception:
		submittable = False
	if spa == "clerk":
		flags = {**read, "write": 1, "create": 1}
		if submittable:
			flags["submit"] = 1
		return flags
	flags = {**read, "write": 1, "create": 1}
	if submittable:
		flags["submit"] = 1
		flags["cancel"] = 1
		flags["amend"] = 1
	return flags


def _books_perms_ready() -> bool:
	clerk = MARKER["clerk"]
	viewer = MARKER["viewer"]
	return (
		cint(
			frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "Sales Invoice", "role": clerk, "permlevel": 0},
				"create",
			)
		)
		== 1
		and cint(
			frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "Journal Entry", "role": clerk, "permlevel": 0},
				"submit",
			)
		)
		== 1
		and cint(
			frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "Sales Invoice", "role": viewer, "permlevel": 0},
				"write",
			)
		)
		== 0
	)


def _role_can_read(doctype: str, role: str) -> bool:
	"""True when this role can read the DocType under Frappe's perm rule.

	Any Custom DocPerm on the DocType replaces DocPerm. A row with if_owner
	does not let the role list the company books.
	"""
	custom = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": doctype, "permlevel": 0},
		fields=["role", "read", "if_owner"],
		limit=500,
	)
	rows = custom or frappe.get_all(
		"DocPerm",
		filters={"parent": doctype, "permlevel": 0},
		fields=["role", "read", "if_owner"],
		limit=500,
	)
	return any(row.role == role and cint(row.read) and not cint(row.if_owner) for row in rows)


def _ensure_books_perms() -> None:
	"""Sync Custom DocPerms for catalog DocTypes and the desk roles the SPA maps.

	``_books_perms_ready`` only samples Sales Invoice / Journal Entry. New
	catalog DocTypes must still get rows even when that sample already looks
	correct. Accounts Manager is an accountant in the SPA but ERPNext does
	not grant Quotation, so that role gets the accountant flags where it
	cannot already read.
	"""
	from frappe.permissions import setup_custom_perms

	refresh_flags = not _books_perms_ready()
	names = list(dict.fromkeys([*_catalog_names(), *VIEWER_READ_DOCTYPES, *_SPA_BOOKS]))
	changed = False
	for doctype in names:
		if not frappe.db.exists("DocType", doctype):
			continue
		try:
			if frappe.get_meta(doctype).istable:
				continue
		except Exception:
			continue
		try:
			setup_custom_perms(doctype)
		except Exception:
			frappe.log_error(title=f"TaxMate perms copy failed: {doctype}")
			continue
		for spa, role in MARKER.items():
			if not frappe.db.exists("Role", role):
				continue
			flags = _perm_values(spa, doctype)
			existing = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			)
			try:
				if existing:
					# Refresh when the sample SI/JE check fails, or when a row
					# exists but has no read (broken / partial seed), or when the
					# DocType is marked read-only for SPA markers (IDP templates).
					needs_update = (
						refresh_flags
						or doctype in READ_ONLY_DOCTYPES
						or not cint(
							frappe.db.get_value("Custom DocPerm", existing, "read")
						)
					)
					if needs_update:
						frappe.db.set_value("Custom DocPerm", existing, flags, update_modified=False)
						changed = True
				else:
					frappe.get_doc(
						{
							"doctype": "Custom DocPerm",
							"parent": doctype,
							"parenttype": "DocType",
							"parentfield": "permissions",
							"role": role,
							"permlevel": 0,
							"if_owner": 0,
							**flags,
						}
					).insert(ignore_permissions=True)
					changed = True
			except Exception:
				frappe.log_error(title=f"TaxMate perm failed: {role} / {doctype}")
		for role, spa in _DESK_SPA.items():
			if not frappe.db.exists("Role", role):
				continue
			if _role_can_read(doctype, role):
				continue
			flags = _perm_values(spa, doctype)
			existing = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			)
			try:
				if existing:
					frappe.db.set_value("Custom DocPerm", existing, flags, update_modified=False)
				else:
					frappe.get_doc(
						{
							"doctype": "Custom DocPerm",
							"parent": doctype,
							"parenttype": "DocType",
							"parentfield": "permissions",
							"role": role,
							"permlevel": 0,
							"if_owner": 0,
							**flags,
						}
					).insert(ignore_permissions=True)
				changed = True
			except Exception:
				frappe.log_error(title=f"TaxMate desk perm failed: {role} / {doctype}")
	if changed or refresh_flags:
		frappe.clear_cache()


# People who can create an invoice may store the scan that produced it.
# if_owner keeps each person on their own log. Create stays available:
# Frappe does not require ownership for a new row.
_SCAN_LOG = "IDP Document Log"
_SCAN_ROLES: tuple[str, ...] = (
	"TaxMate Owner",
	"TaxMate Accountant",
	"TaxMate Accounts User",
	"Accounts Manager",
	"Accounts User",
	"Purchase Manager",
	"Purchase User",
	"Sales Manager",
	"Sales User",
)


def _ensure_scan_perms() -> None:
	"""Let invoice roles create and update their own IDP Document Log rows."""
	if not frappe.db.exists("DocType", _SCAN_LOG):
		return
	from frappe.permissions import setup_custom_perms

	try:
		setup_custom_perms(_SCAN_LOG)
	except Exception:
		frappe.log_error(title="TaxMate scan perm copy failed")
	flags = {
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"report": 0,
		"export": 0,
		"import": 0,
		"share": 0,
		"print": 0,
		"email": 0,
	}
	changed = False
	for role in _SCAN_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		existing = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": _SCAN_LOG, "role": role, "permlevel": 0, "if_owner": 1},
		)
		try:
			if existing:
				if not cint(frappe.db.get_value("Custom DocPerm", existing, "create")):
					frappe.db.set_value("Custom DocPerm", existing, flags, update_modified=False)
					changed = True
			else:
				frappe.get_doc(
					{
						"doctype": "Custom DocPerm",
						"parent": _SCAN_LOG,
						"parenttype": "DocType",
						"parentfield": "permissions",
						"role": role,
						"permlevel": 0,
						"if_owner": 1,
						**flags,
					}
				).insert(ignore_permissions=True)
				changed = True
		except Exception:
			frappe.log_error(title=f"TaxMate scan perm failed: {role}")
	if changed:
		frappe.clear_cache()


def _allow_reports() -> None:
	"""Grant TaxMate marker roles on every SPA catalog report.

	Frappe ``Report.is_permitted`` prefers a ``Custom Role`` row for the report
	when one exists, and that list *replaces* ``Report.roles``. ERPNext UAE
	seeds often leave Custom Role with only Desk roles (Accounts User / Manager),
	which blocks Website-User SPA accountants. Keep Desk roles and add markers.
	"""
	from taxmate.setup.financial_reports import CORE_REPORT_LINKS, TAXMATE_REPORT_LINKS

	names = [name for _, name in (*CORE_REPORT_LINKS, *TAXMATE_REPORT_LINKS)]
	marker_roles = tuple(MARKER.values())
	for report in names:
		if not frappe.db.exists("Report", report):
			continue
		for role in marker_roles:
			if frappe.db.exists("Has Role", {"parent": report, "parenttype": "Report", "role": role}):
				continue
			try:
				frappe.get_doc(
					{
						"doctype": "Has Role",
						"parent": report,
						"parenttype": "Report",
						"parentfield": "roles",
						"role": role,
					}
				).insert(ignore_permissions=True)
			except Exception:
				frappe.log_error(title=f"TaxMate Report Has Role failed: {report} / {role}")
		_ensure_report_custom_roles(report, marker_roles)


def _ensure_report_custom_roles(report: str, marker_roles: tuple[str, ...]) -> None:
	"""Add TaxMate markers to Custom Role for ``report`` when that override exists."""
	if not frappe.db.exists("DocType", "Custom Role"):
		return
	custom_name = frappe.db.get_value("Custom Role", {"report": report}, "name")
	if not custom_name:
		return
	doc = frappe.get_doc("Custom Role", custom_name)
	have = {row.role for row in doc.roles}
	missing = [role for role in marker_roles if role not in have and frappe.db.exists("Role", role)]
	if not missing:
		return
	try:
		for role in missing:
			doc.append("roles", {"role": role})
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"TaxMate Custom Role report roles failed: {report}")


def _strip_desk_roles_from_spa_users() -> None:
	parents = {
		row.parent
		for row in frappe.get_all(
			"Has Role",
			filters={"role": ["in", list(MARKER.values())], "parenttype": "User"},
			fields=["parent"],
		)
	}
	strip = LEGACY_DESK_ROLES
	for user in parents:
		if user in ("Administrator", "Guest"):
			continue
		roles = set(frappe.get_roles(user))
		if "System Manager" in roles:
			continue
		if not (roles & strip):
			continue
		apply_spa_roles(user, spa_roles_of(user), extra_roles=None)


def _lock_non_admin_users_to_spa() -> None:
	"""Except Administrator: no Desk roles, home = /taxmate."""
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ["Administrator", "Guest"]]},
		pluck="name",
	)
	for user in users:
		_lock_user_to_spa(user)


def _lock_user_to_spa(user: str) -> None:
	if user in ("Administrator", "Guest"):
		return

	doc = frappe.get_doc("User", user)
	roles_now = [row.role for row in doc.roles]
	spa = spa_roles_of(user)
	# spa_roles_of maps System Manager → owner; after we strip SM they need a marker.
	if "System Manager" in roles_now and not any(r in MARKER.values() for r in roles_now):
		spa = ["owner"]
	if not spa:
		spa = ["viewer"]

	extras = [r for r in roles_now if r in ADDON_ROLES]
	try:
		apply_spa_roles(user, spa, extra_roles=extras)
	except frappe.PermissionError:
		# apply_spa_roles refuses System Manager — strip SM first then retry.
		doc = frappe.get_doc("User", user)
		doc.set("roles", [{"role": r} for r in roles_now if r != "System Manager"])
		doc.save(ignore_permissions=True)
		frappe.clear_cache(user=user)
		apply_spa_roles(user, spa, extra_roles=extras)

	doc = frappe.get_doc("User", user)
	if doc.has_desk_access():
		# Last resort: drop any remaining desk-granting roles.
		kept = [row.role for row in doc.roles if not _role_grants_desk(row.role)]
		if not any(r in MARKER.values() for r in kept):
			kept.append(MARKER[spa[0]])
		doc.set("roles", [])
		for role in dict.fromkeys(kept):
			if role and frappe.db.exists("Role", role):
				doc.append("roles", {"role": role})
		doc.redirect_url = "/taxmate"
		if hasattr(doc, "default_app"):
			doc.default_app = "taxmate"
		if doc.meta.has_field("default_workspace"):
			doc.default_workspace = None
		if not doc.has_desk_access():
			doc.user_type = "Website User"
		doc.save(ignore_permissions=True)
		frappe.clear_cache(user=user)
