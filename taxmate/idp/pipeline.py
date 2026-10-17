# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""OCR-once extract → map → normalize for TaxMate Scans."""

from __future__ import annotations

import re
from typing import Any

import frappe

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def detect_language_from_text(text: str | None) -> str:
	if not text:
		return "en"
	sample = text[:4000]
	ar = len(_ARABIC_RE.findall(sample))
	return "ar" if ar >= max(12, int(0.08 * max(len(sample), 1))) else "en"


def extract_once(file_url: str, language: str | None = None) -> tuple[Any, str]:
	"""One extract_content call. Language for mapping is derived from OCR text."""
	from idp.extractors import extract_content

	lang = language or "en"
	extraction = extract_content(file_url, lang=lang)
	if not language:
		lang = detect_language_from_text(extraction.text)
	return extraction, lang


def map_from_extraction(
	extraction: Any,
	target: str,
	language: str,
	*,
	use_model: bool = True,
	file_sha256: str | None = None,
) -> dict[str, Any]:
	from idp.core.config import get_default_company
	from idp.core.exceptions import LLMError
	from idp.mappers import FieldMapper
	from idp.validators import validate_business_rules, validate_schema

	company = get_default_company()
	used_llm = False
	mapped = None

	if use_model:
		try:
			from idp.llm.client import LLMClient
			from idp.mappers.hybrid_mapper import HybridFieldMapper

			client = LLMClient.from_settings()
			mapper = HybridFieldMapper(FieldMapper(), client)
			mapped = mapper.map_fields(
				extraction,
				target,
				company=company,
				user=frappe.session.user,
				source_lang=language,
				output_language="English",
				file_sha256=file_sha256,
			)
			used_llm = any("llm fallback applied" in str(row) for row in (mapped.warnings or []))
		except LLMError:
			mapped = None
		except Exception:
			frappe.log_error(title="TaxMate IDP model map failed", message=frappe.get_traceback())
			mapped = None

	if mapped is None:
		mapped = FieldMapper().map_fields(
			extraction, target, company=company, source_lang=language
		)

	schema_result = validate_schema(mapped, company)
	biz_warnings = validate_business_rules(mapped, company)
	return {
		"success": True,
		"used_llm": used_llm,
		"ocr_language": language,
		"ocr_text": extraction.text or "",
		"confidence": extraction.confidence,
		"extracted_data": {
			"doctype": mapped.doctype,
			"header": mapped.header,
			"items": mapped.items,
		},
		"validation": {
			"is_valid": schema_result.is_valid,
			"errors": [
				{"field": e.field, "message": e.message, "severity": e.severity} for e in schema_result.errors
			],
			"warnings": [
				{"field": w.field, "message": w.message, "severity": w.severity}
				for w in schema_result.warnings
			]
			+ [{"field": "", "message": w, "severity": "warning"} for w in biz_warnings],
			"missing_masters": getattr(schema_result, "missing_masters", None) or [],
		},
	}


def normalize_mapped(extracted: dict[str, Any]) -> dict[str, Any]:
	from taxmate.idp.masters import (
		bind_parties_by_trn,
		normalize_extract,
		promote_unresolved_items,
		salvage_from_ocr_text,
	)
	from taxmate.idp.post_map import bind_known_items, refresh_validation
	from taxmate.idp.validators_uae import attach_confidence

	try:
		salvage_from_ocr_text(extracted, extracted.get("ocr_text"))
	except Exception:
		frappe.log_error(title="TaxMate IDP OCR salvage skipped", message=frappe.get_traceback())

	normalize_extract(extracted, promote_items=False)
	bind_known_items(extracted)
	items = (extracted.get("extracted_data") or {}).get("items")
	if isinstance(items, list):
		promote_unresolved_items(items)
	bind_parties_by_trn(extracted)
	refresh_validation(extracted)
	attach_confidence(extracted)
	return extracted


def read_once(
	file_url: str,
	target: str,
	*,
	use_model: bool = True,
	file_sha256: str | None = None,
) -> dict[str, Any]:
	from idp.core.exceptions import SecurityError
	from idp.core.security import assert_safe_file_url
	from taxmate.idp.post_map import file_gate

	try:
		assert_safe_file_url(file_url)
	except SecurityError:
		return {"success": False, "error_key": "idp.file"}
	gate = file_gate(file_url)
	if gate:
		return {"success": False, "error_key": gate}

	extraction, language = extract_once(file_url)
	extracted = map_from_extraction(
		extraction, target, language, use_model=use_model, file_sha256=file_sha256
	)
	return normalize_mapped(extracted)
