"""SPA team admin. User is not a catalog resource.

Invite, role, and enablement go through taxmate.api.users (see get_catalog).
Only TaxMate Owners invite/manage; Team list and detail are scoped to the
caller's active company via Company User Permission rows. SPA roles are owner,
accountant, clerk, and viewer mapped onto marker Roles. Users may hold multiple
markers; Frappe unions DocPerms. Optional POSNext add-ons are assignable when
those Role docs exist on the site.

Callers: frontend TeamList/TeamInvite, taxmate.api.get_catalog actions,
test_spa_users. Schema: User Has Role child rows (Frappe union of DocPerms).
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, random_string, validate_email_address

from taxmate.api.resource import require_login
from taxmate.setup.company_owner import (
	OWNER_FIELD,
	ensure_company_owner_field,
	is_app_provider,
	is_forbidden_owner_user,
)
from taxmate.setup.spa_roles import (
	ALL_MARKER_ROLE_NAMES,
	MARKER,
	SPA_ROLES,
	addon_roles_of,
	apply_spa_roles,
	available_addon_roles,
	ensure_marker_roles,
	spa_role_of,
	spa_roles_of,
)
from taxmate.utils.company import ACTIVE_COMPANY_KEY, can_use_company, get_default_company, user_companies

_SKIP_USERS = frozenset({"Guest", "Administrator"})


def _holds_taxmate_owner(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return MARKER["owner"] in frappe.get_roles(user)


def _require_owner() -> None:
	"""Only a real TaxMate Owner for the active company — never Administrator."""
	user = frappe.session.user
	if is_app_provider(user) or is_forbidden_owner_user(user):
		frappe.throw(_("Admins manage the team"), frappe.PermissionError)
	if not _holds_taxmate_owner(user):
		frappe.throw(_("Admins manage the team"), frappe.PermissionError)
	company = _active_company()
	if not _belongs_to_company(user, company):
		frappe.throw(_("Admins manage the team"), frappe.PermissionError)


def _require_team_read() -> None:
	"""Owner or accountant of the active company. Providers use onboard, not Team list."""
	user = frappe.session.user
	if is_app_provider(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	role = spa_role_of(user)
	if role not in ("owner", "accountant"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	company = _active_company()
	if not _belongs_to_company(user, company):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _require_provider() -> None:
	if not is_app_provider():
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _assert_taxmate_teammate(user: str) -> None:
	"""Reject Desk-only / unrelated Users — Team APIs are TaxMate-marker scoped."""
	held = set(frappe.get_roles(user))
	if not held.intersection(ALL_MARKER_ROLE_NAMES):
		frappe.throw(_("User not found"))


def _caller_unrestricted() -> bool:
	user = frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _company_permissions(user: str) -> list[str]:
	"""Company names from this user's Company User Permission rows only.

	Does not treat System Manager as “all companies” — Team isolation is always
	permission-row based so each company's roster stays distinct.
	"""
	return frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Company"},
		pluck="for_value",
	)


def _belongs_to_company(user: str, company: str) -> bool:
	"""True when the user has a Company User Permission for this company."""
	return bool(company) and company in _company_permissions(user)


def _active_company(*, invite: bool = False) -> str:
	"""Caller's active company — Team list, detail, and invites are scoped to it."""
	company = get_default_company()
	if not company or not can_use_company(company):
		frappe.throw(
			_("Choose a company before inviting someone")
			if invite
			else _("Choose a company before managing the team")
		)
	return company


def _can_manage_target(user: str) -> bool:
	"""True when every company on the target is one the caller owns.

	An accountant who also works for another business stays visible, but this
	company's owner cannot change a role that would affect the other business.
	Providers never manage teammates through Team APIs.
	"""
	if is_app_provider():
		return False
	mine = set(user_companies())
	theirs = set(user_companies(user))
	return bool(theirs) and theirs <= mine


def _assert_can_manage(user: str) -> None:
	_assert_taxmate_teammate(user)
	company = _active_company()
	if not _belongs_to_company(user, company):
		frappe.throw(_("User not found"))
	if not _can_manage_target(user):
		frappe.throw(_("That user belongs to another company"), frappe.PermissionError)


def _invite_company() -> str:
	return _active_company(invite=True)


def _grant_company(user: str, company: str, *, multi: bool) -> None:
	"""Frappe User Permission on Company. Accountants may hold more than one."""
	current = _company_permissions(user)
	if company in current:
		return
	if current and not multi:
		frappe.throw(_("That user already belongs to another company"))
	from frappe.permissions import add_user_permission

	add_user_permission(
		"Company",
		company,
		user,
		ignore_permissions=True,
		is_default=0 if current else 1,
	)


def _assert_mutable_user(user: str) -> None:
	if not user or user in _SKIP_USERS:
		frappe.throw(_("That user cannot be changed from TaxMate"))
	if "System Manager" in frappe.get_roles(user):
		frappe.throw(_("System managers cannot be changed from TaxMate"), frappe.PermissionError)


def _is_system_manager(user: str) -> bool:
	return bool(frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"}))


def _parse_spa_roles(
	spa_role: str | None = None,
	spa_roles: Any = None,
) -> list[str]:
	"""Accept spa_roles list/JSON/comma string, or legacy spa_role singular."""
	raw: Any = spa_roles
	if raw is None or raw == "" or raw == []:
		if spa_role:
			return [spa_role]
		frappe.throw(_("At least one role is required"))
	if isinstance(raw, str):
		text = raw.strip()
		if text.startswith("["):
			raw = frappe.parse_json(text)
		else:
			raw = [part.strip() for part in text.split(",") if part.strip()]
	if not isinstance(raw, (list, tuple)):
		frappe.throw(_("Unknown role"))
	out: list[str] = []
	for item in raw:
		name = str(item).strip()
		if not name:
			continue
		if name not in SPA_ROLES:
			frappe.throw(_("Unknown role"))
		if name not in out:
			out.append(name)
	if not out:
		frappe.throw(_("At least one role is required"))
	return out


def _parse_extra_roles(extra_roles: Any = None) -> list[str] | None:
	"""None means preserve existing add-ons; explicit list (incl. empty) replaces them."""
	if extra_roles is None:
		return None
	raw: Any = extra_roles
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			return []
		if text.startswith("["):
			raw = frappe.parse_json(text)
		else:
			raw = [part.strip() for part in text.split(",") if part.strip()]
	if not isinstance(raw, (list, tuple)):
		frappe.throw(_("Unknown role"))
	allowed = frozenset(available_addon_roles())
	out: list[str] = []
	for item in raw:
		name = str(item).strip()
		if not name:
			continue
		if name not in allowed:
			frappe.throw(_("Unknown role"))
		if name not in out:
			out.append(name)
	return out


def _as_user_row(name: str, *, company: str | None = None) -> dict[str, Any]:
	doc = frappe.get_doc("User", name)
	roles = spa_roles_of(doc.name)
	return {
		"name": doc.name,
		"email": doc.email or doc.name,
		"full_name": doc.full_name or doc.first_name or doc.name,
		"first_name": doc.first_name,
		"last_name": doc.last_name,
		"mobile_no": doc.mobile_no,
		"language": doc.language,
		"user_type": doc.user_type,
		"enabled": int(doc.enabled or 0),
		"spa_role": roles[0] if roles else (spa_role_of(doc.name) or "viewer"),
		"spa_roles": roles,
		"extra_roles": addon_roles_of(doc.name),
		"last_active": str(doc.last_active) if doc.last_active else None,
		"last_login": str(doc.last_login) if getattr(doc, "last_login", None) else None,
		"creation": str(doc.creation) if doc.creation else None,
		"can_manage": _can_manage_target(doc.name),
		"company": company,
	}


@frappe.whitelist()
def list_users() -> list[dict[str, Any]]:
	require_login()
	_require_team_read()
	ensure_marker_roles()
	company = _active_company()

	names = {
		row.parent
		for row in frappe.get_all(
			"Has Role",
			filters={"role": ["in", list(ALL_MARKER_ROLE_NAMES)], "parenttype": "User"},
			fields=["parent"],
		)
	}
	out: list[dict[str, Any]] = []
	for name in sorted(names):
		if name in _SKIP_USERS or _is_system_manager(name):
			continue
		if not frappe.db.exists("User", name):
			continue
		if not _belongs_to_company(name, company):
			continue
		out.append(_as_user_row(name, company=company))
	out.sort(key=lambda row: (0 if row.get("enabled") else 1, (row.get("full_name") or row["name"]).lower()))
	return out


@frappe.whitelist()
def get_user(user: str) -> dict[str, Any]:
	"""One teammate for the Team detail form (Frappe User fields + SPA roles)."""
	require_login()
	_require_team_read()
	ensure_marker_roles()
	company = _active_company()
	user = (user or "").strip()
	if not user or user in _SKIP_USERS or _is_system_manager(user):
		frappe.throw(_("User not found"))
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"))
	_assert_taxmate_teammate(user)
	if not _belongs_to_company(user, company):
		frappe.throw(_("User not found"))
	return _as_user_row(user, company=company)


@frappe.whitelist(methods=["POST"])
def update_user(
	user: str,
	first_name: str,
	last_name: str | None = None,
	mobile_no: str | None = None,
	language: str | None = None,
) -> dict[str, Any]:
	"""Owner edits teammate identity fields (email stays the User name)."""
	require_login()
	_require_owner()
	_assert_mutable_user(user)
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"))
	_assert_can_manage(user)

	first_name = (first_name or "").strip()
	if not first_name:
		frappe.throw(_("First name is required"))

	doc = frappe.get_doc("User", user)
	doc.first_name = first_name
	doc.last_name = (last_name or "").strip()
	doc.mobile_no = (mobile_no or "").strip()
	if language is not None:
		doc.language = (language or "").strip() or None
	doc.save(ignore_permissions=True)
	frappe.clear_cache(user=user)
	return _as_user_row(user, company=_active_company())


@frappe.whitelist(methods=["POST"])
def reset_user_password(user: str) -> dict[str, str]:
	"""Send Frappe password-reset email to a teammate."""
	require_login()
	_require_owner()
	_assert_mutable_user(user)
	if user == frappe.session.user:
		frappe.throw(_("Use Profile to change your own password"))
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"))
	_assert_can_manage(user)

	doc = frappe.get_doc("User", user)
	if not cint(doc.enabled):
		frappe.throw(_("Enable the user before resetting the password"))
	doc.validate_reset_password()
	doc._reset_password(send_email=True)
	return {"ok": "1"}


@frappe.whitelist(methods=["POST"])
def invite_user(
	email: str,
	first_name: str,
	spa_role: str | None = None,
	spa_roles: Any = None,
	extra_roles: Any = None,
	last_name: str | None = None,
	mobile_no: str | None = None,
	send_welcome_email: int | str = 1,
) -> dict[str, Any]:
	require_login()
	_require_owner()
	ensure_marker_roles()

	email = (email or "").strip().lower()
	first_name = (first_name or "").strip()
	if not first_name:
		frappe.throw(_("First name is required"))
	validate_email_address(email, throw=True)
	roles = _parse_spa_roles(
		spa_role=spa_role or ("clerk" if spa_roles is None else None), spa_roles=spa_roles
	)
	addons = _parse_extra_roles(extra_roles)
	company = _invite_company()
	if frappe.db.exists("User", email):
		# An accountant can be mapped to another company the owner already has.
		# Owner, clerk, and viewer stay on the one company they were given.
		held = spa_roles_of(email)
		if "accountant" in held and "owner" not in held:
			_grant_company(email, company, multi=True)
			return _as_user_row(email, company=company)
		frappe.throw(_("That user already exists"))

	welcome = cint(send_welcome_email)
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = first_name
	user.last_name = (last_name or "").strip()
	user.mobile_no = (mobile_no or "").strip()
	user.enabled = 1
	user.send_welcome_email = welcome
	user.redirect_url = "/taxmate"
	if hasattr(user, "default_app"):
		user.default_app = "taxmate"
	if not welcome:
		user.new_password = random_string(16)
		user.flags.no_welcome_mail = True
	user.insert(ignore_permissions=True)
	apply_spa_roles(user.name, roles, extra_roles=addons if addons is not None else [])
	frappe.defaults.set_user_default(ACTIVE_COMPANY_KEY, company, user.name)
	frappe.defaults.set_user_default("company", company, user.name)
	# Every company user, including the owner, is limited by a Frappe User
	# Permission. Only an accountant may later be granted further companies.
	_grant_company(user.name, company, multi="accountant" in roles and "owner" not in roles)
	return _as_user_row(user.name, company=company)


@frappe.whitelist(methods=["POST"])
def set_user_role(
	user: str,
	spa_role: str | None = None,
	spa_roles: Any = None,
	extra_roles: Any = None,
) -> dict[str, Any]:
	require_login()
	_require_owner()
	ensure_marker_roles()
	_assert_mutable_user(user)
	if user == frappe.session.user:
		frappe.throw(_("You cannot change your own role"))
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"))
	_assert_can_manage(user)

	roles = _parse_spa_roles(spa_role=spa_role, spa_roles=spa_roles)
	addons = _parse_extra_roles(extra_roles)
	if "owner" in roles:
		# An owner is one company. User Permission is the Frappe record of that,
		# and a role change must not leave the extra companies in place.
		held = _company_permissions(user)
		if len(held) > 1:
			frappe.throw(_("An owner belongs to one company"))
	apply_spa_roles(user, roles, extra_roles=addons)
	return _as_user_row(user, company=_active_company())


@frappe.whitelist(methods=["POST"])
def set_user_enabled(user: str, enabled: int | str = 0) -> dict[str, Any]:
	require_login()
	_require_owner()
	_assert_mutable_user(user)
	if user == frappe.session.user:
		frappe.throw(_("You cannot disable yourself"))
	if not frappe.db.exists("User", user):
		frappe.throw(_("User not found"))
	_assert_can_manage(user)

	doc = frappe.get_doc("User", user)
	doc.enabled = 1 if cint(enabled) else 0
	doc.save(ignore_permissions=True)
	frappe.clear_cache(user=user)
	return _as_user_row(user, company=_active_company())


@frappe.whitelist(methods=["POST"])
def onboard_company_owner(
	company: str,
	email: str,
	first_name: str,
	last_name: str | None = None,
	mobile_no: str | None = None,
	send_welcome_email: int | str = 1,
) -> dict[str, Any]:
	"""App provider assigns the primary TaxMate Owner for a company.

	Administrator is never the owner — this creates/links a client user, grants
	TaxMate Owner + Company User Permission, and sets Company.custom_taxmate_owner.
	"""
	require_login()
	_require_provider()
	ensure_marker_roles()
	ensure_company_owner_field()

	company = (company or "").strip()
	email = (email or "").strip().lower()
	first_name = (first_name or "").strip()
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Company not found"))
	if not first_name:
		frappe.throw(_("First name is required"))
	validate_email_address(email, throw=True)
	if is_forbidden_owner_user(email) or email == "administrator":
		frappe.throw(_("Administrator cannot be the TaxMate Owner of a company"))
	if frappe.db.exists("User", email) and is_forbidden_owner_user(email):
		frappe.throw(_("Administrator cannot be the TaxMate Owner of a company"))

	welcome = cint(send_welcome_email)
	created = False
	if frappe.db.exists("User", email):
		user_name = email
		if "System Manager" in frappe.get_roles(user_name):
			frappe.throw(_("System managers cannot be company owners"), frappe.PermissionError)
	else:
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = first_name
		user.last_name = (last_name or "").strip()
		user.mobile_no = (mobile_no or "").strip()
		user.enabled = 1
		user.send_welcome_email = welcome
		user.redirect_url = "/taxmate"
		if hasattr(user, "default_app"):
			user.default_app = "taxmate"
		if not welcome:
			user.new_password = random_string(16)
			user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user_name = user.name
		created = True

	apply_spa_roles(user_name, ["owner"], extra_roles=[])
	# Owner is one company — replace other Company UPs if any.
	for other in _company_permissions(user_name):
		if other == company:
			continue
		frappe.db.delete(
			"User Permission",
			{"user": user_name, "allow": "Company", "for_value": other},
		)
	_grant_company(user_name, company, multi=False)
	frappe.defaults.set_user_default(ACTIVE_COMPANY_KEY, company, user_name)
	frappe.defaults.set_user_default("company", company, user_name)

	frappe.db.set_value("Company", company, OWNER_FIELD, user_name, update_modified=True)
	frappe.clear_cache(doctype="Company")
	frappe.clear_cache(user=user_name)

	row = _as_user_row(user_name, company=company)
	row["company"] = company
	row["created"] = 1 if created else 0
	row[OWNER_FIELD] = user_name
	return row



def _as_profile(user: str) -> dict[str, Any]:
	doc = frappe.get_doc("User", user)
	roles = spa_roles_of(doc.name)
	return {
		"name": doc.name,
		"email": doc.email or doc.name,
		"first_name": doc.first_name,
		"last_name": doc.last_name,
		"full_name": doc.full_name or doc.first_name or doc.name,
		"mobile_no": doc.mobile_no,
		"spa_role": roles[0] if roles else (spa_role_of(doc.name) or "viewer"),
		"spa_roles": roles,
		"extra_roles": addon_roles_of(doc.name),
	}


@frappe.whitelist()
def get_profile() -> dict[str, Any]:
	require_login()
	return _as_profile(frappe.session.user)


@frappe.whitelist(methods=["POST"])
def update_profile(
	first_name: str,
	last_name: str | None = None,
	mobile_no: str | None = None,
) -> dict[str, Any]:
	require_login()
	user = frappe.session.user
	first_name = (first_name or "").strip()
	if not first_name:
		frappe.throw(_("First name is required"))

	doc = frappe.get_doc("User", user)
	doc.first_name = first_name
	doc.last_name = (last_name or "").strip()
	doc.mobile_no = (mobile_no or "").strip()
	doc.save(ignore_permissions=True)
	frappe.clear_cache(user=user)
	return _as_profile(user)


@frappe.whitelist(methods=["POST"])
def change_password(old_password: str, new_password: str) -> dict[str, str]:
	require_login()
	user = frappe.session.user
	old_password = old_password or ""
	new_password = new_password or ""
	if not old_password or not new_password:
		frappe.throw(_("Current and new password are required"))
	if old_password == new_password:
		frappe.throw(_("Choose a different password"))

	from frappe.auth import MAX_PASSWORD_SIZE
	from frappe.core.doctype.user.user import handle_password_test_fail, test_password_strength
	from frappe.utils.password import check_password, update_password

	if len(new_password) > MAX_PASSWORD_SIZE:
		frappe.throw(_("Password size exceeded the maximum allowed size."))
	feedback = test_password_strength(new_password).get("feedback")
	if feedback and not feedback.get("password_policy_validation_passed", False):
		handle_password_test_fail(feedback)

	try:
		check_password(user, old_password)
	except frappe.AuthenticationError:
		# 417, not 401: the mobile app treats any 401 as a dead device token.
		frappe.throw(_("Incorrect User or Password"), frappe.ValidationError)
	logout_all = cint(frappe.get_system_settings("logout_on_password_reset"))
	update_password(user, new_password, logout_all_sessions=logout_all)
	# update_password does not save the User doc, so User doc_events do not fire:
	# sign out other mobile devices here (keeps the device making this request).
	from taxmate.api.mobile_auth import current_device, revoke_user_devices

	revoke_user_devices(user, keep=current_device())
	return {"ok": "1"}
