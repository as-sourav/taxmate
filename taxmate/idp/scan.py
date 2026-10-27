# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""Frozen Scan helpers on IDP Document Log."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe

from taxmate.utils.company import get_default_company

PIPELINE_VERSION = 5  # bump: scanned pages are read by the configured vision model
SCAN_DOCTYPE = "IDP Document Log"
# Canonical machine (IDP brief); READY kept as alias for Review.
REVIEW = "Review"
READY = REVIEW
READING = "Reading"
EXTRACTING = READING
FAILED = "Failed"
CANCELLED = "Cancelled"
# Canonical Review plus legacy IDP Document Log values still in the wild.
REVIEW_READY = frozenset({REVIEW, "Ready", "Extracted"})


def file_sha256(file_url: str) -> str | None:
	"""Hash file bytes for idempotent re-read. Returns None if unreadable."""
	try:
		from idp.core.security import assert_safe_file_url

		path = assert_safe_file_url(file_url)
	except Exception:
		return None
	h = hashlib.sha256()
	with open(path, "rb") as fh:
		for chunk in iter(lambda: fh.read(1024 * 1024), b""):
			h.update(chunk)
	return h.hexdigest()


def find_ready_scan(
	*,
	file_sha256_hex: str,
	target_doctype: str,
	pipeline_version: int = PIPELINE_VERSION,
) -> str | None:
	"""Return this user's Ready scan for the same bytes, target, version, and company.

	Caller: idp_desk._run_create. Two clerks uploading the same file must not share a scan.
	"""
	try:
		filters: dict[str, Any] = {
			"file_sha256": file_sha256_hex,
			"target_doctype": target_doctype,
			"pipeline_version": pipeline_version,
			"status": READY,
			"user": frappe.session.user,
		}
		company = get_default_company()
		if company:
			filters["company"] = company
		name = frappe.db.get_value(SCAN_DOCTYPE, filters, "name")
	except Exception:
		# Schema may lag (missing Scan columns on an older IDP install).
		frappe.clear_last_message()
		return None
	return str(name) if name else None


def assert_scan_access(scan_id: str) -> Any:
	"""Load Scan; enforce owner + company."""
	if not scan_id or not frappe.db.exists(SCAN_DOCTYPE, scan_id):
		frappe.throw("Scan not found.", frappe.DoesNotExistError)
	doc = frappe.get_doc(SCAN_DOCTYPE, scan_id)
	if doc.user and doc.user != frappe.session.user and frappe.session.user != "Administrator":
		frappe.throw("Not allowed to access this Scan.", frappe.PermissionError)
	company = get_default_company()
	if doc.company and company and doc.company != company:
		frappe.throw("Scan belongs to another company.", frappe.PermissionError)
	return doc


def frozen_extracted(doc: Any) -> dict[str, Any]:
	"""Return the immutable extraction payload stored on the Scan."""
	data = doc.extraction_data
	if isinstance(data, str):
		try:
			data = json.loads(data) if data else {}
		except ValueError:
			data = {}
	if not isinstance(data, dict):
		return {}
	return data


def caller_may_store_scan(target_doctype: str | None) -> bool:
	"""A clerk who can create the invoice may store the scan that produces it.

	IDP Document Log create is limited to System Manager and IDP User in the
	DocType itself. Accounts clerks still need a scan row, so the invoice
	permission is enough. Guests and users who cannot create the target cannot.
	"""
	from taxmate.idp.desk import SCAN_DOCTYPES

	if target_doctype not in SCAN_DOCTYPES:
		return False
	user = frappe.session.user
	if user == "Administrator":
		return True
	if user == "Guest":
		return False
	if "System Manager" in frappe.get_roles(user):
		return True
	if frappe.has_permission(SCAN_DOCTYPE, "create", user=user):
		return True
	return bool(target_doctype and frappe.has_permission(target_doctype, "create", user=user))


def _scan_company() -> str | None:
	"""Company the signed-in user can actually use, never a stale default."""
	from taxmate.utils.company import can_use_company, user_companies

	company = get_default_company()
	if company and can_use_company(company):
		return company
	names = user_companies()
	return names[0] if names else None


def persist_scan(
	*,
	file_url: str,
	target_doctype: str,
	extracted: dict[str, Any],
	file_sha256_hex: str | None,
	ocr_text: str | None = None,
	path_taken: str | None = None,
	ocr_engine: str | None = None,
	error_key: str | None = None,
	status: str = READY,
	stage_timings: dict | None = None,
	field_confidence: dict | None = None,
) -> str:
	"""Insert a Scan row with frozen extraction. Returns scan name."""
	if not caller_may_store_scan(target_doctype):
		frappe.throw("Not allowed to create a Scan.", frappe.PermissionError)
	company = _scan_company()
	file_name = None
	try:
		from idp.core.security import assert_safe_file_url

		path = assert_safe_file_url(file_url)
		file_name = path.rsplit("/", 1)[-1]
	except Exception:
		pass

	doc = frappe.get_doc(
		{
			"doctype": SCAN_DOCTYPE,
			"file_url": file_url,
			"file_name": file_name,
			"target_doctype": target_doctype,
			"company": company,
			"user": frappe.session.user,
			"status": status,
			"file_sha256": file_sha256_hex,
			"pipeline_version": PIPELINE_VERSION,
			"ocr_engine": ocr_engine or "llm",
			"ocr_text": (ocr_text or "")[:200000],
			"path_taken": path_taken or ("hybrid" if extracted.get("used_llm") else "rule"),
			"error_key": error_key,
			"extraction_data": extracted,
			"ocr_language": extracted.get("ocr_language"),
			"ocr_confidence": extracted.get("confidence"),
			"field_confidence_json": field_confidence or {},
			"stage_timings_json": stage_timings or {},
			"mapper_source": "hybrid" if extracted.get("used_llm") else "rule",
		}
	)
	# TaxMate owns the OCR worker until IDP run_read adopts the same pipeline.
	doc.flags.skip_enqueue = True
	doc.flags.skip_file_check = True
	# The caller was already checked. The DocType's own create perm must not
	# block a clerk who is allowed to create the invoice.
	doc.insert(ignore_permissions=True)
	return doc.name


def mark_scan(scan_id: str, **fields: Any) -> None:
	"""Update Scan fields (status, error_key, cancel_requested, …)."""
	doc = assert_scan_access(scan_id)
	for key, value in fields.items():
		if hasattr(doc, key):
			setattr(doc, key, value)
	doc.save(ignore_permissions=False)


def scan_payload(doc: Any) -> dict[str, Any]:
	"""Public get_scan shape."""
	return {
		"ok": True,
		"scan_id": doc.name,
		"status": doc.status,
		"file_url": doc.file_url,
		"target_doctype": doc.target_doctype,
		"pipeline_version": doc.pipeline_version,
		"file_sha256": doc.file_sha256,
		"error_key": doc.error_key,
		"path_taken": doc.path_taken,
		"cancel_requested": bool(doc.cancel_requested),
		"stage_timings": doc.stage_timings_json or {},
		"field_confidence": doc.field_confidence_json or {},
		"extracted": frozen_extracted(doc) if doc.status in REVIEW_READY else None,
	}