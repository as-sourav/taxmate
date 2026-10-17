# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""IDP Scan hooks — UAE / TaxMate rules stay out of apps/idp."""

from __future__ import annotations

import json
from typing import Any


def _as_dict(data: Any) -> dict[str, Any]:
	if isinstance(data, str):
		try:
			data = json.loads(data) if data else {}
		except ValueError:
			data = {}
	return data if isinstance(data, dict) else {}


def idp_after_extract(doc: Any) -> None:
	"""Enrich frozen extraction in memory. Caller saves once after this returns."""
	from taxmate.idp.post_map import bind_known_items, refresh_validation
	from taxmate.idp.validators_uae import attach_confidence

	extracted = _as_dict(doc.extraction_data)
	if not extracted:
		return
	bind_known_items(extracted)
	attach_confidence(extracted)
	refresh_validation(extracted)
	doc.extraction_data = extracted


def idp_before_make_draft(doc: Any) -> None:
	"""Block draft when non-creatable masters are still missing."""
	import frappe

	data = _as_dict(doc.extraction_data)
	missing = (data.get("validation") or {}).get("missing_masters") or data.get("missing_masters") or []
	blocked = [m for m in missing if not m.get("creatable")]
	if blocked:
		frappe.throw("Missing masters block draft", frappe.ValidationError)
