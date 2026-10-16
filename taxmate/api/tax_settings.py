"""UAE Tax Settings (ASP / e-invoicing) for the SPA.

Callers: frontend TaxSettings via get_catalog().
Methods: get_uae_tax_settings, save_uae_tax_settings.
Password fields never leave the server.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, cstr

from taxmate.api.resource import require_login
from taxmate.setup.spa_roles import require_spa_role

_DT = "UAE Tax Settings"
_PROVIDER = "Complyance"

# Non-secret fields the SPA may read and write.
_PUBLIC_FIELDS = (
	"sandbox_mode",
	"asp_provider",
	"base_url",
	"participant_id",
	"exclude_b2c_e_invoices",
	"auto_draft_incoming_pi",
	"sla_days",
	"archive_retention_years",
	"uae_storage_note",
	"webhook_subscription_id",
	"token_expiry",
	"participant_details",
)

_PASSWORD_FIELDS = ("client_secret", "auth_key", "webhook_secret")
_READ_ONLY = frozenset({"webhook_subscription_id", "token_expiry", "participant_details"})


def _has_password(fieldname: str) -> bool:
	"""True when __Auth holds a value — do not decrypt on every GET."""
	return bool(
		frappe.db.exists(
			"__Auth",
			{"doctype": _DT, "name": _DT, "fieldname": fieldname, "encrypted": 1},
		)
	)


def _public_payload(doc) -> dict[str, Any]:
	out: dict[str, Any] = {"name": _DT, "doctype": _DT}
	for field in _PUBLIC_FIELDS:
		if doc.meta.has_field(field):
			out[field] = doc.get(field)
	out["has_client_id"] = bool(cstr(doc.get("client_id") or "").strip())
	out["has_client_secret"] = _has_password("client_secret")
	out["has_auth_key"] = _has_password("auth_key")
	out["has_webhook_secret"] = _has_password("webhook_secret")
	# client_id is not a Password field — return for display/edit; not a secret in DocType.
	out["client_id"] = cstr(doc.get("client_id") or "")
	return out


def _assert_write() -> None:
	require_spa_role("owner", "accountant")
	if not frappe.has_permission(_DT, "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_uae_tax_settings() -> dict[str, Any]:
	"""Site-wide ASP settings for the SPA. Passwords never leave the server."""
	require_login()
	if not frappe.has_permission(_DT, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not frappe.db.exists("DocType", _DT):
		frappe.throw(_("UAE Tax Settings is not installed"))
	doc = frappe.get_single(_DT)
	return _public_payload(doc)


@frappe.whitelist(methods=["POST"])
def save_uae_tax_settings(doc: dict | str | None = None) -> dict[str, Any]:
	"""Update non-secret ASP fields; set passwords only when a new value is sent."""
	require_login()
	_assert_write()
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	if not isinstance(doc, dict):
		frappe.throw(_("doc is required"))

	settings = frappe.get_single(_DT)

	from taxmate.uae_e_invoicing.api_classes.complyance import (
		ComplyanceSourceError,
		parse_complyance_source,
	)

	try:
		parse_complyance_source(cstr(doc.get("participant_id", settings.participant_id)))
	except ComplyanceSourceError:
		frappe.throw(_("Complyance source must be name:version, for example taxmate:1.0."))

	sla = cint(doc.get("sla_days", settings.sla_days))
	if sla < 1:
		frappe.throw(_("Transmission SLA Days must be at least 1"))

	years = cint(doc.get("archive_retention_years", settings.archive_retention_years))
	# DocType validate enforces FTA minimum of 5 years.
	if years < 5:
		frappe.throw(_("Archive Retention (Years) must be at least 5"))

	for field in _PUBLIC_FIELDS:
		if field in _READ_ONLY or field not in doc:
			continue
		if not settings.meta.has_field(field):
			continue
		if field == "asp_provider":
			settings.asp_provider = _PROVIDER
		elif field == "sla_days":
			settings.sla_days = sla
		elif field == "archive_retention_years":
			settings.archive_retention_years = years
		elif field in ("sandbox_mode", "exclude_b2c_e_invoices", "auto_draft_incoming_pi"):
			settings.set(field, 1 if cint(doc.get(field)) else 0)
		else:
			settings.set(field, doc.get(field))

	if "client_id" in doc and settings.meta.has_field("client_id"):
		settings.client_id = cstr(doc.get("client_id") or "").strip()

	# Passwords: only replace when the client sent a non-empty new value.
	# get_single() does not hydrate Password fields; empty values on save would
	# delete __Auth rows (frappe.model.base_document._save_passwords). Ignore
	# every Password field we are not replacing — including access_token.
	password_updates: dict[str, str] = {}
	for field in _PASSWORD_FIELDS:
		if field not in doc or not settings.meta.has_field(field):
			continue
		raw = doc.get(field)
		if raw is None:
			continue
		value = cstr(raw).strip()
		if not value or value == "*****":
			continue
		password_updates[field] = value
		settings.set(field, value)

	ignore_pw = [
		df.fieldname
		for df in settings.meta.get("fields", {"fieldtype": ("=", "Password")})
		if df.fieldname not in password_updates
	]
	if ignore_pw:
		settings.flags.ignore_save_passwords = ignore_pw
	elif not password_updates:
		# No password fields on meta, or none to ignore — never clear Auth.
		settings.flags.ignore_save_passwords = True
	settings.save()

	frappe.clear_document_cache(_DT, _DT)
	return _public_payload(frappe.get_single(_DT))
