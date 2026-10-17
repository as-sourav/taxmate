# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""Post-map helpers for Scan worker and desk (no import of idp_desk)."""

from __future__ import annotations

from typing import Any

import frappe

from taxmate.idp.desk import attach_item_codes, file_read_error


def refresh_validation(extracted: dict) -> None:
	from idp.core.config import get_default_company
	from idp.mappers.base import MappedDocument
	from idp.validators import validate_business_rules, validate_schema

	data = extracted.get("extracted_data") or {}
	mapped = MappedDocument(
		doctype=str(data.get("doctype") or ""),
		header=dict(data.get("header") or {}),
		items=list(data.get("items") or []),
	)
	company = get_default_company()
	schema_result = validate_schema(mapped, company or "")
	biz_warnings = validate_business_rules(mapped, company or "")
	extracted["validation"] = {
		"is_valid": schema_result.is_valid,
		"errors": [
			{"field": row.field, "message": row.message, "severity": row.severity}
			for row in schema_result.errors
		],
		"warnings": [
			{"field": row.field, "message": row.message, "severity": row.severity}
			for row in schema_result.warnings
		]
		+ [{"field": "", "message": row, "severity": "warning"} for row in biz_warnings],
		"missing_masters": schema_result.missing_masters,
	}


def bind_known_items(extracted: dict) -> None:
	if not extracted.get("success"):
		return
	items = (extracted.get("extracted_data") or {}).get("items") or []

	def lookup(name: str) -> str | None:
		return frappe.db.get_value("Item", {"item_name": name}, "item_code")

	attach_item_codes(items, lookup)
	refresh_validation(extracted)


def file_gate(file_url: str) -> str | None:
	from idp.core.exceptions import IDPPermissionError
	from idp.core.security import check_file_access

	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return file_read_error(found=False, allowed=False)
	try:
		check_file_access(frappe.get_doc("File", name))
	except IDPPermissionError:
		return file_read_error(found=True, allowed=False)
	return file_read_error(found=True, allowed=True)
