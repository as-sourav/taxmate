"""Whitelist for the dashboard IDP panel.

Login is checked here. Which job may run, and whether the result is a
draft, is decided in taxmate.idp.desk.
"""

from __future__ import annotations

import frappe

from taxmate.api.resource import require_login
from taxmate.idp.desk import (
	attach_item_codes,
	diffs_from_compare,
	diffs_from_update,
	draft_instructions,
	draft_only_error,
	file_read_error,
	finish_draft,
	header_updates,
	match_filters,
	matches_from_rows,
	plan_run,
	resolve_ocr_language,
	review_from_extract,
	search_arguments,
	submit_requested,
)
from taxmate.idp.desk import (
	get_surface as _get_surface,
)
from taxmate.utils.company import get_default_company

SURFACE_METHOD = "taxmate.api.idp_desk.get_surface"
UPLOAD_METHOD = "taxmate.api.idp_desk.upload"
RUN_METHOD = "taxmate.api.idp_desk.run"
SAVE_METHOD = "taxmate.api.idp_desk.save"


@frappe.whitelist()
def get_surface() -> dict:
	require_login()
	return _get_surface()


@frappe.whitelist()
def upload() -> dict:
	"""Accept a Scan file; normalize camera MIME quirks before IDP validates.

	Callers: CaptureDesk postFile → METHOD.idpUpload (catalog). Soft-fails with
	error_key instead of opaque 417 when MIME/size is wrong.
	User: foolproof Scan so upload does not show a generic read failure.
	"""
	require_login()
	from io import BytesIO

	from werkzeug.datastructures import FileStorage, ImmutableMultiDict

	from taxmate.idp.upload_prep import normalize_upload_headers

	if "file" not in (frappe.request.files or {}):
		return {"success": False, "error_key": "idp.emptyFile"}

	uploaded = frappe.request.files["file"]
	raw = uploaded.stream.read() if hasattr(uploaded, "stream") else uploaded.read()
	prep = normalize_upload_headers(
		frappe.utils.cstr(uploaded.filename or "document"),
		frappe.utils.cstr(uploaded.content_type or ""),
		raw or b"",
	)
	if not prep.get("ok"):
		return {"success": False, "error_key": prep.get("error_key") or "idp.file"}

	# Re-inject a clean FileStorage so IDP's MIME/size checks see the real type.
	frappe.request.files = ImmutableMultiDict(
		[
			(
				"file",
				FileStorage(
					stream=BytesIO(prep["content"]),
					filename=prep["file_name"],
					content_type=prep["content_type"],
				),
			)
		]
	)

	from idp.api.upload import upload_document

	try:
		return upload_document()
	except frappe.ValidationError as exc:
		msg = frappe.utils.cstr(exc).lower()
		if "size" in msg:
			return {"success": False, "error_key": "idp.tooLarge"}
		if "empty" in msg:
			return {"success": False, "error_key": "idp.emptyFile"}
		if "unsupported" in msg or "type" in msg:
			return {"success": False, "error_key": "idp.file"}
		return {"success": False, "error_key": "idp.readFailed", "detail": frappe.utils.cstr(exc)[:200]}
	except Exception:
		frappe.log_error(title="TaxMate IDP upload failed", message=frappe.get_traceback())
		return {"success": False, "error_key": "idp.readFailed"}


def _read(file_url: str, target: str, *, use_model: bool = False) -> dict:
	from idp.api.extract import extract_document
	from idp.core.exceptions import SecurityError
	from idp.core.security import assert_safe_file_url

	try:
		path = assert_safe_file_url(file_url)
	except SecurityError:
		return {"success": False, "error_key": "idp.file"}
	gate = _file_gate(file_url)
	if gate:
		return {"success": False, "error_key": gate}
	language = _ocr_language(path)
	extracted = None
	if use_model:
		extracted = _read_with_model(file_url, target, language)
	if not extracted:
		extracted = extract_document(file_url=file_url, target_doctype=target, language=language)
	if isinstance(extracted, dict):
		extracted["ocr_language"] = language
		from taxmate.idp.masters import (
			bind_parties_by_trn,
			normalize_extract,
			promote_unresolved_items,
			salvage_from_ocr_text,
		)

		try:
			from idp.extractors import extract_content

			salvage_from_ocr_text(extracted, extract_content(file_url, lang=language).text)
		except Exception:
			frappe.log_error(title="TaxMate IDP OCR salvage skipped", message=frappe.get_traceback())

		# Party/address first; item-code fill waits until name lookup runs.
		normalize_extract(extracted, promote_items=False)
		_bind_known_items(extracted)
		items = (extracted.get("extracted_data") or {}).get("items")
		if isinstance(items, list):
			promote_unresolved_items(items)
		bind_parties_by_trn(extracted)
		_refresh_validation(extracted)
	return extracted


def _read_with_model(file_url: str, target: str, language: str) -> dict | None:
	"""Rule map, then the IDP model when the rules leave required fields empty.

	Returns None when the model is not configured, so the caller stays on rules.
	"""
	from idp.core.config import get_default_company
	from idp.core.exceptions import LLMError
	from idp.extractors import extract_content
	from idp.llm.client import LLMClient
	from idp.mappers import FieldMapper
	from idp.mappers.hybrid_mapper import HybridFieldMapper
	from idp.validators import validate_business_rules, validate_schema

	company = get_default_company()
	try:
		client = LLMClient.from_settings()
		extraction = extract_content(file_url, lang=language)
		mapper = HybridFieldMapper(FieldMapper(), client)
		mapped = mapper.map_fields(
			extraction,
			target,
			company=company,
			user=frappe.session.user,
			source_lang=language,
			output_language="English",
		)
		schema_result = validate_schema(mapped, company)
		biz_warnings = validate_business_rules(mapped, company)
	except LLMError:
		return None
	except Exception:
		frappe.log_error(title="TaxMate IDP model read failed", message=frappe.get_traceback())
		return None
	used = any("llm fallback applied" in str(row) for row in (mapped.warnings or []))
	return {
		"success": True,
		"used_llm": used,
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
			"missing_masters": schema_result.missing_masters,
		},
	}


def _file_gate(file_url: str) -> str | None:
	"""The File row must exist and this user must be allowed to read it."""
	import frappe
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


def _ocr_language(path: str) -> str:
	"""Detect a real OCR code from the file on disk. Never pass ``auto`` to Paddle.

	Prefer ``detect_language_isolated`` (subprocess + timeout) when the installed
	IDP build exports it. Older IDP versions only have ``detect_language`` —
	UAT was crashing Scan with ImportError before any OCR ran.
	"""
	from idp.core.constants import OCR_LANGUAGES

	detected = ""
	try:
		from idp.ocr import engine as ocr_engine

		isolated = getattr(ocr_engine, "detect_language_isolated", None)
		detect = getattr(ocr_engine, "detect_language", None)
		if callable(isolated):
			detected = isolated(path) or ""
		elif callable(detect):
			detected = detect(path) or ""
	except Exception:
		detected = ""
	return resolve_ocr_language(detected, set(OCR_LANGUAGES))


def _plan(action: str, target_doctype: str | None, file_url: str | None, query: str | None) -> dict:
	return plan_run(
		_get_surface(),
		action=action,
		target=target_doctype,
		file_name=file_url,
		query=query,
	)


def _context(doctype: str, language: str):
	from idp.tools.base import ToolContext

	return ToolContext(
		conversation_id="dashboard",
		user=frappe.session.user,
		company=get_default_company(),
		target_doctype=doctype,
		ocr_language=language or "en",
	)


def _tool_error(result) -> dict:
	detail = getattr(result, "error", None) or ""
	return {"ok": False, "error_key": "idp.readFailed", "detail": str(detail)[:400] or None}


def _open_draft(doctype: str, name: str) -> dict | None:
	"""Return an error payload when the named document is missing, hidden, or not a draft."""
	try:
		doc = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		return {"ok": False, "error_key": "idp.missing"}
	except frappe.PermissionError:
		return {"ok": False, "error_key": "idp.denied"}
	blocked = draft_only_error(getattr(doc, "docstatus", 0))
	if blocked:
		return {"ok": False, "error_key": blocked}
	return None


@frappe.whitelist()
def run(
	action: str,
	target_doctype: str | None = None,
	file_url: str | None = None,
	query: str | None = None,
) -> dict:
	require_login()
	try:
		return _run(action, target_doctype, file_url, query)
	except Exception:
		frappe.log_error(title="TaxMate IDP run failed", message=frappe.get_traceback())
		return {
			"ok": False,
			"step": "review",
			"error_key": "idp.readFailed",
			"detail_key": "idp.readHint",
			"can_save": False,
		}


def _run(
	action: str,
	target_doctype: str | None = None,
	file_url: str | None = None,
	query: str | None = None,
) -> dict:
	planned = _plan(action, target_doctype, file_url, query)
	if not planned.get("ok"):
		return planned
	if action == "search":
		return _search(planned)
	if action == "delete":
		return _preview_delete(planned)
	extracted = _read(file_url or "", planned["doctype"], use_model=action == "create")
	if extracted.get("error_key"):
		return {"ok": False, "error_key": extracted["error_key"]}
	if action == "create":
		review = review_from_extract(extracted, route=planned.get("route"))
		review["file_url"] = file_url
		review["save_key"] = planned.get("save_key")
		review["used_llm"] = bool(extracted.get("used_llm"))
		_prefill_writes(review)
		return review
	if action == "compare":
		return _compare(planned, extracted, file_url)
	if action == "match":
		return _match(planned, extracted)
	if action == "update":
		return _preview_update(planned, extracted)
	return {"ok": False, "error_key": "idp.pending"}


@frappe.whitelist()
def save(
	action: str,
	target_doctype: str | None = None,
	file_url: str | None = None,
	query: str | None = None,
	fills: str | None = None,
	submit: str | None = None,
	proposals: str | None = None,
) -> dict:
	"""Apply the job the clerk confirmed. Submit runs only when they ask."""
	require_login()
	planned = _plan(action, target_doctype, file_url, query)
	if not planned.get("ok"):
		return planned
	if action == "create":
		return _save_create(planned, file_url or "", fills=fills, submit=submit, proposals=proposals)
	if action == "update":
		return _save_update(planned, file_url or "")
	if action == "delete":
		return _save_delete(planned)
	return {"ok": False, "error_key": "idp.pending"}


def _search(planned: dict) -> dict:
	from idp.tools.search_documents import search_documents

	ctx = _context(planned["doctype"], "en")
	result = search_documents(search_arguments(planned["doctype"], planned["query"]), ctx)
	if not result.success:
		return _tool_error(result)
	rows = (result.data or {}).get("rows") or []
	matches = matches_from_rows(rows, planned.get("route"))
	return {
		"ok": True,
		"step": "review",
		"matches": matches,
		"error_key": None if matches else "idp.none",
	}


def _compare(planned: dict, extracted: dict, file_url: str | None) -> dict:
	from idp.tools.compare_document import compare_document

	header = header_updates((extracted.get("extracted_data") or {}).get("header") or {})
	if not header:
		return {"ok": False, "error_key": "idp.invalid"}
	ctx = _context(planned["doctype"], extracted.get("ocr_language") or "en")
	result = compare_document(
		{
			"doctype": planned["doctype"],
			"name": planned["query"],
			"proposed": header,
			"file_id": file_url,
		},
		ctx,
	)
	if not result.success:
		return _tool_error(result)
	data = result.data or {}
	name = data.get("name")
	route = planned.get("route")
	return {
		"ok": True,
		"step": "review",
		"name": name,
		"route": f"{route}/{name}" if route and name else None,
		"diffs": diffs_from_compare(data.get("differences") or []),
	}


def _match(planned: dict, extracted: dict) -> dict:
	from idp.tools.find_matching_record import find_matching_record

	header = header_updates((extracted.get("extracted_data") or {}).get("header") or {})
	filters = match_filters(header)
	if not filters:
		return {"ok": False, "error_key": "idp.invalid"}
	ctx = _context(planned["doctype"], extracted.get("ocr_language") or "en")
	result = find_matching_record(
		{"doctype": planned["doctype"], "filters": filters, "fields": ["name"], "limit": 20},
		ctx,
	)
	if not result.success:
		return _tool_error(result)
	matches = matches_from_rows((result.data or {}).get("candidates") or [], planned.get("route"))
	return {
		"ok": True,
		"step": "review",
		"matches": matches,
		"error_key": None if matches else "idp.none",
	}


def _preview_update(planned: dict, extracted: dict) -> dict:
	from idp.tools.update_document import update_document

	blocked = _open_draft(planned["doctype"], planned["query"])
	if blocked:
		return blocked
	updates = header_updates((extracted.get("extracted_data") or {}).get("header") or {})
	if not updates:
		return {"ok": False, "error_key": "idp.invalid"}
	ctx = _context(planned["doctype"], extracted.get("ocr_language") or "en")
	result = update_document(
		{
			"doctype": planned["doctype"],
			"name": planned["query"],
			"updates": updates,
			"dry_run": True,
		},
		ctx,
	)
	if not result.success:
		return _tool_error(result)
	diffs = diffs_from_update((result.data or {}).get("diff") or (result.data or {}).get("rows") or [])
	# update_document keeps the diff on the card when data uses another key.
	if not diffs and result.card:
		diffs = diffs_from_update((result.card or {}).get("diff") or [])
	name = planned["query"]
	route = planned.get("route")
	return {
		"ok": True,
		"step": "review",
		"name": name,
		"route": f"{route}/{name}" if route else None,
		"diffs": diffs,
		"can_save": bool(diffs),
		"save_key": planned.get("save_key"),
		"error_key": None if diffs else "idp.same",
	}


def _preview_delete(planned: dict) -> dict:
	blocked = _open_draft(planned["doctype"], planned["query"])
	if blocked:
		return blocked
	name = planned["query"]
	route = planned.get("route")
	return {
		"ok": True,
		"step": "review",
		"name": name,
		"route": f"{route}/{name}" if route else None,
		"can_delete": True,
		"save_key": planned.get("save_key"),
		"lines": [{"label_key": "idp.query.doc", "value": name}],
	}


def _save_create(
	planned: dict,
	file_url: str,
	*,
	fills: str | None,
	submit: str | None,
	proposals: str | None = None,
) -> dict:
	from taxmate.idp.masters import (
		apply_created_links,
		build_proposals,
		create_confirmed,
		merge_proposal_values,
		proposals_complete,
		release_address_links,
		release_currency_company,
		split_missing,
	)

	extracted = _read(file_url, planned["doctype"], use_model=True)
	if extracted.get("error_key"):
		return {"ok": False, "error_key": extracted["error_key"]}
	release_currency_company(extracted)
	release_address_links(extracted)
	_creatable, blocked = split_missing((extracted.get("validation") or {}).get("missing_masters"))
	if blocked:
		named = []
		for row in blocked:
			kind = str(row.get("doctype") or "").strip()
			name = str(row.get("name") or "").strip()
			named.append(f"{kind}: {name}" if kind and name else (kind or name))
		return {
			"ok": False,
			"error_key": "idp.notice.masters",
			"detail": "; ".join(n for n in named if n) or None,
		}
	# Trust the clerk's confirmed cards from the panel. A second LLM read can
	# rename parties/items and break key-based merge, which looked like Save
	# doing nothing while returning needConsent.
	client_props = _coerce_proposal_defaults(_proposals(proposals))
	client_ready = bool(client_props) and proposals_complete(client_props)
	if client_ready:
		pending = client_props
	else:
		pending = merge_proposal_values(build_proposals(extracted), client_props)
	if pending:
		made = create_confirmed(pending)
		if not made.get("ok"):
			return {
				"ok": False,
				"error_key": made.get("error_key") or "idp.propose.failed",
				"detail": made.get("detail"),
			}
		apply_created_links(extracted, made.get("created") or {})
		_refresh_validation(extracted)
		release_address_links(extracted)
	# Re-read leftovers only block when the clerk did not send complete cards.
	# After create+stamp, draft_instructions keeps the confirmed cards so
	# ERPNext schema noise cannot soft-fail as idp.invalid.
	if build_proposals(extracted) and not client_ready:
		return {"ok": False, "error_key": "idp.propose.needConsent"}
	instructions = draft_instructions(
		extracted, proposals=client_props if client_ready else pending or []
	)
	if not instructions.get("ok"):
		return instructions
	header, items = finish_draft(
		instructions["header"],
		instructions.get("items") or [],
		_fills(fills),
		_draft_defaults(instructions.get("items") or []),
	)
	instructions["header"] = header
	instructions["items"] = items
	instructions["submit"] = False
	from idp.tools.create_document import create_document

	ctx = _context(instructions["doctype"], extracted.get("ocr_language") or "en")
	result = create_document(instructions, ctx)
	if not result.success:
		return _tool_error(result)
	name = (result.data or {}).get("name")
	route = planned.get("route")
	payload = {
		"ok": True,
		"step": "saved",
		"doctype": instructions["doctype"],
		"name": name,
		"route": f"{route}/{name}" if route and name else None,
		"docstatus": (result.data or {}).get("docstatus"),
	}
	if not submit_requested(submit) or not name:
		return payload
	# Draft must be visible to submit() in this same request before the auto-commit.
	frappe.db.commit()  # nosemgrep
	try:
		from taxmate.api.workflow import submit as submit_doc

		submitted = submit_doc({"doctype": instructions["doctype"], "name": name})
	except Exception as exc:
		payload["error_key"] = "idp.submitFailed"
		payload["detail"] = str(exc)
		return payload
	payload["step"] = "submitted"
	payload["docstatus"] = submitted.get("docstatus") if isinstance(submitted, dict) else payload["docstatus"]
	return payload


def _proposals(raw: str | None) -> list[dict]:
	import json

	if not raw:
		return []
	try:
		data = json.loads(raw)
	except (TypeError, ValueError):
		return []
	if not isinstance(data, list):
		return []
	return [row for row in data if isinstance(row, dict)]


def _coerce_proposal_defaults(proposals: list[dict]) -> list[dict]:
	"""Fill Type when the select was left blank — empty Type was blocking Save."""
	out: list[dict] = []
	for row in proposals:
		entry = dict(row)
		doctype = str(entry.get("doctype") or "")
		default_type = "Company"
		type_field = (
			"supplier_type" if doctype == "Supplier" else "customer_type" if doctype == "Customer" else None
		)
		if type_field:
			fields = []
			for field in entry.get("required_fields") or []:
				item = dict(field) if isinstance(field, dict) else field
				if isinstance(item, dict) and item.get("field") == type_field and not str(item.get("value") or "").strip():
					item["value"] = default_type
				fields.append(item)
			entry["required_fields"] = fields
		out.append(entry)
	return out


def _fills(raw: str | None) -> dict:
	import json

	if not raw:
		return {}
	try:
		data = json.loads(raw)
	except (TypeError, ValueError):
		return {}
	if not isinstance(data, dict):
		return {}
	return {str(key): value for key, value in data.items()}


def _bind_known_items(extracted: dict) -> None:
	"""Match a printed item name to an item that already exists. Then re-check the draft."""
	if not extracted.get("success"):
		return
	data = extracted.get("extracted_data") or {}
	items = data.get("items") or []

	def lookup(name: str) -> str | None:
		return frappe.db.get_value("Item", {"item_name": name}, "item_code")

	attach_item_codes(items, lookup)
	_refresh_validation(extracted)


def _refresh_validation(extracted: dict) -> None:
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


def _prefill_writes(review: dict) -> None:
	defaults = _draft_defaults([])
	for row in review.get("writes") or []:
		if row.get("value"):
			continue
		if row.get("field") == "cost_center" and defaults.get("cost_center"):
			row["value"] = defaults["cost_center"]
		if row.get("field") == "vat_emirate" and defaults.get("vat_emirate"):
			row["value"] = defaults["vat_emirate"]


def _draft_defaults(items: list) -> dict:
	from taxmate.utils.company import can_use_company

	company = get_default_company()
	if company and not can_use_company(company):
		company = None
	if not company:
		fallback = frappe.db.get_single_value("Global Defaults", "default_company")
		if fallback and can_use_company(fallback):
			company = fallback
	uoms = {}
	for row in items:
		if not isinstance(row, dict):
			continue
		code = row.get("item_code")
		if code and code not in uoms:
			uoms[code] = frappe.db.get_value("Item", code, "stock_uom") or ""
	return {
		"company": company or "",
		"cost_center": frappe.db.get_value("Company", company, "cost_center") if company else "",
		"income_account": frappe.db.get_value("Company", company, "default_income_account")
		if company
		else "",
		"selling_price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list") or "",
		"vat_emirate": _company_emirate(company or ""),
		"item_uom": uoms,
	}


def _company_emirate(company: str) -> str:
	if not company:
		return ""
	parents = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
		pluck="parent",
	)
	for name in parents:
		emirate = frappe.db.get_value("Address", name, "emirate")
		if emirate:
			return emirate
	return ""


def _save_update(planned: dict, file_url: str) -> dict:
	blocked = _open_draft(planned["doctype"], planned["query"])
	if blocked:
		return blocked
	extracted = _read(file_url, planned["doctype"])
	if extracted.get("error_key"):
		return {"ok": False, "error_key": extracted["error_key"]}
	updates = header_updates((extracted.get("extracted_data") or {}).get("header") or {})
	if not updates:
		return {"ok": False, "error_key": "idp.invalid"}
	from idp.tools.update_document import update_document

	ctx = _context(planned["doctype"], extracted.get("ocr_language") or "en")
	result = update_document(
		{
			"doctype": planned["doctype"],
			"name": planned["query"],
			"updates": updates,
			"dry_run": False,
		},
		ctx,
	)
	if not result.success:
		return _tool_error(result)
	name = planned["query"]
	route = planned.get("route")
	return {
		"ok": True,
		"step": "saved",
		"doctype": planned["doctype"],
		"name": name,
		"route": f"{route}/{name}" if route else None,
	}


def _save_delete(planned: dict) -> dict:
	blocked = _open_draft(planned["doctype"], planned["query"])
	if blocked:
		return blocked
	from idp.tools.delete_document import delete_document

	ctx = _context(planned["doctype"], "en")
	result = delete_document(
		{
			"doctype": planned["doctype"],
			"name": planned["query"],
			"confirm": True,
			"reason": "Deleted from the TaxMate dashboard",
		},
		ctx,
	)
	if not result.success:
		return _tool_error(result)
	return {"ok": True, "step": "deleted", "name": planned["query"]}
