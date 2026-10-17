# Copyright (c) 2026, Ascra Technologies and contributors
"""Thin TaxMate catalog wrappers over idp.api.scan.

Callers: SPA METHOD.idpScan* (optional path alongside idp_desk create/poll).
"""

from __future__ import annotations

import frappe

from taxmate.api.resource import require_login


@frappe.whitelist()
def create_scan(
	file_url: str,
	target_doctype: str,
	company: str | None = None,
	idempotency_key: str | None = None,
):
	require_login()
	from idp.api import scan as idp_scan

	from taxmate.utils.company import get_default_company

	return idp_scan.create_scan(
		file_url,
		target_doctype,
		company or get_default_company(),
		idempotency_key,
	)


@frappe.whitelist()
def get_scan(name: str):
	require_login()
	from idp.api import scan as idp_scan

	return idp_scan.get_scan(name)


@frappe.whitelist()
def save_edits(name: str, edits, modified: str):
	require_login()
	from idp.api import scan as idp_scan

	return idp_scan.save_edits(name, edits, modified)


@frappe.whitelist()
def make_draft(name: str, modified: str):
	require_login()
	from idp.api import scan as idp_scan

	return idp_scan.make_draft(name, modified)


@frappe.whitelist()
def cancel_scan(name: str):
	require_login()
	from idp.api import scan as idp_scan

	return idp_scan.cancel_scan(name)
