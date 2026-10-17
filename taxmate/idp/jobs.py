# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""Background Scan worker: OCR-once + realtime stage events."""

from __future__ import annotations

import time
from typing import Any

import frappe

from taxmate.idp import scan as scan_mod

QUEUE = "long"
TIMEOUT = 600


def _publish(scan_id: str, stage: str, status: str, **extra: Any) -> None:
	frappe.publish_realtime(
		event="taxmate_scan_progress",
		message={"scan_id": scan_id, "stage": stage, "status": status, **extra},
		doctype=scan_mod.SCAN_DOCTYPE,
		docname=scan_id,
		after_commit=True,
	)


def _cancelled(scan_id: str) -> bool:
	row = frappe.db.get_value(
		scan_mod.SCAN_DOCTYPE,
		scan_id,
		["cancel_requested", "status"],
		as_dict=True,
	)
	if not row:
		return True
	return bool(row.cancel_requested) or row.status == scan_mod.CANCELLED


def _json_value(value: Any) -> str:
	"""Encode dict/list for db.set_value — raw dicts break MariaDB on JSON columns."""
	if value is None:
		return "{}"
	if isinstance(value, str):
		return value
	return frappe.as_json(value)


def enqueue_scan(*, scan_id: str, file_url: str, target_doctype: str, user: str) -> None:
	frappe.enqueue(
		"taxmate.idp.jobs.run_scan_job",
		queue=QUEUE,
		timeout=TIMEOUT,
		job_name=f"taxmate-scan-{scan_id}",
		enqueue_after_commit=True,
		scan_id=scan_id,
		file_url=file_url,
		target_doctype=target_doctype,
		user=user,
	)


def run_scan_job(
	scan_id: str,
	file_url: str,
	target_doctype: str,
	user: str | None = None,
) -> None:
	if user:
		frappe.set_user(user)
	timings: dict[str, float] = {}
	t0 = time.perf_counter()

	def stage(name: str) -> None:
		timings[name] = round((time.perf_counter() - t0) * 1000.0, 1)
		# Timing write must never abort OCR — set_value + raw dict used to SQL-crash the job.
		try:
			frappe.db.set_value(
				scan_mod.SCAN_DOCTYPE,
				scan_id,
				{"stage_timings_json": _json_value(timings)},
				update_modified=False,
			)
			frappe.db.commit()
		except Exception:
			frappe.log_error(title="TaxMate scan stage timing write failed")
		_publish(scan_id, name, "active", timings=dict(timings))

	try:
		if _cancelled(scan_id):
			_publish(scan_id, "cancelled", "failed", error_key="cancelled")
			return

		stage("uploaded")
		digest = scan_mod.file_sha256(file_url)
		stage("ocr")
		from taxmate.idp.pipeline import extract_once, map_from_extraction, normalize_mapped

		extraction, language = extract_once(file_url)
		if _cancelled(scan_id):
			frappe.db.set_value(
				scan_mod.SCAN_DOCTYPE,
				scan_id,
				{"status": scan_mod.CANCELLED, "error_key": "cancelled", "cancel_requested": 1},
			)
			_publish(scan_id, "cancelled", "failed", error_key="cancelled")
			return

		stage("mapped")
		extracted = map_from_extraction(
			extraction, target_doctype, language, use_model=True, file_sha256=digest
		)
		stage("validated")
		extracted = normalize_mapped(extracted)

		# Cancel wins over Ready — never overwrite a cancelled Scan.
		if _cancelled(scan_id):
			frappe.db.set_value(
				scan_mod.SCAN_DOCTYPE,
				scan_id,
				{"status": scan_mod.CANCELLED, "error_key": "cancelled"},
			)
			_publish(scan_id, "cancelled", "failed", error_key="cancelled")
			return

		doc = frappe.get_doc(scan_mod.SCAN_DOCTYPE, scan_id)
		if doc.cancel_requested or doc.status == scan_mod.CANCELLED:
			_publish(scan_id, "cancelled", "failed", error_key="cancelled")
			return
		doc.extraction_data = extracted
		doc.ocr_text = (extracted.get("ocr_text") or "")[:200000]
		doc.ocr_language = extracted.get("ocr_language")
		doc.ocr_confidence = extracted.get("confidence")
		doc.path_taken = "hybrid" if extracted.get("used_llm") else "rule"
		doc.mapper_source = doc.path_taken
		doc.stage_timings_json = _json_value(timings)
		doc.field_confidence_json = _json_value(extracted.get("field_confidence") or {})
		doc.error_key = None
		# Same enrichment path as IDP run_read (in-memory before freeze).
		from taxmate.idp.hooks_idp import idp_after_extract

		try:
			idp_after_extract(doc)
		except Exception:
			frappe.log_error(title="TaxMate idp_after_extract failed")
		doc.status = scan_mod.REVIEW
		doc.save(ignore_permissions=False)
		frappe.db.commit()
		stage("review")
		_publish(scan_id, "review", "done", timings=dict(timings))
	except Exception as exc:
		frappe.log_error(title="TaxMate scan job failed", message=frappe.get_traceback())
		msg = str(exc).lower()
		if "timeout" in msg:
			error_key = "ocr_timeout"
		elif "paddle" in msg or "ocr" in msg:
			error_key = "idp.readFailed"
		else:
			error_key = "idp.readFailed"
		if not _cancelled(scan_id):
			frappe.db.set_value(
				scan_mod.SCAN_DOCTYPE,
				scan_id,
				{
					"status": scan_mod.FAILED,
					"error_key": error_key,
					"error_message": str(exc)[:500],
				},
			)
			frappe.db.commit()
		_publish(scan_id, "failed", "failed", error_key=error_key)
