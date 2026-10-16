"""Map SPA language/theme onto Frappe User.language and User.desk_theme.

Callers: get_session, update_ui_preferences; frontend SessionProvider + toggles.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from taxmate.api.resource import require_login

# SPA ↔ User.desk_theme (Frappe Desk options).
_THEME_TO_DESK = {"light": "Light", "dark": "Dark", "system": "Automatic"}
_DESK_TO_THEME = {v: k for k, v in _THEME_TO_DESK.items()}

_SPA_LANGS = frozenset({"en", "ar"})


def spa_lang_from_user(language: str | None) -> str | None:
	"""Return ``en`` / ``ar`` when User.language is one of those; else None."""
	code = (language or "").strip().lower()
	if not code:
		return None
	# Language Link may be ``ar`` or a longer code; Arabic scripts start with ar.
	if code == "en" or code.startswith("en"):
		return "en"
	if code == "ar" or code.startswith("ar"):
		return "ar"
	return None


def spa_theme_from_desk(desk_theme: str | None) -> str | None:
	"""Return ``light`` / ``dark`` / ``system`` when desk_theme is set."""
	raw = (desk_theme or "").strip()
	if not raw:
		return None
	return _DESK_TO_THEME.get(raw)


def desk_theme_from_spa(theme: str | None) -> str:
	key = (theme or "").strip().lower()
	if key not in _THEME_TO_DESK:
		frappe.throw(_("Theme must be light, dark, or system."))
	return _THEME_TO_DESK[key]


def language_from_spa(lang: str | None) -> str:
	code = (lang or "").strip().lower()
	if code not in _SPA_LANGS:
		frappe.throw(_("Language must be English (en) or Arabic (ar)."))
	if not frappe.db.exists("Language", code):
		frappe.throw(_("Language {0} is not installed.").format(code))
	return code


def read_ui_prefs(user: str | None = None) -> dict[str, Any]:
	"""Public prefs for session / preference saves."""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return {"language": None, "desk_theme": None, "lang": None, "theme": None}
	row = frappe.db.get_value("User", user, ["language", "desk_theme"], as_dict=True) or {}
	language = row.get("language")
	desk_theme = row.get("desk_theme")
	return {
		"language": language or None,
		"desk_theme": desk_theme or None,
		"lang": spa_lang_from_user(language),
		"theme": spa_theme_from_desk(desk_theme),
	}


@frappe.whitelist(methods=["POST"])
def update_ui_preferences(
	language: str | None = None,
	desk_theme: str | None = None,
	theme: str | None = None,
) -> dict[str, Any]:
	"""Persist SPA language and/or theme onto the logged-in User.

	Accepts Desk values (``Light``/``Dark``/``Automatic``) or SPA
	(``light``/``dark``/``system``) via ``desk_theme`` or ``theme``.
	"""
	require_login()
	user = frappe.session.user
	updates: dict[str, str] = {}

	if language is not None and str(language).strip() != "":
		updates["language"] = language_from_spa(language)

	raw_theme = desk_theme if desk_theme is not None else theme
	if raw_theme is not None and str(raw_theme).strip() != "":
		token = str(raw_theme).strip()
		if token in _THEME_TO_DESK:
			updates["desk_theme"] = _THEME_TO_DESK[token]
		elif token in _DESK_TO_THEME:
			updates["desk_theme"] = token
		else:
			frappe.throw(_("Theme must be light, dark, or system."))

	if not updates:
		frappe.throw(_("Nothing to update"))

	frappe.db.set_value("User", user, updates, update_modified=False)
	frappe.clear_cache(user=user)
	return read_ui_prefs(user)
