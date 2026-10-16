"""Complyance ASP adapter (UAE / PINT AE via Unify).

The Developer portal integration maps this site's own invoice JSON to GETS.
TaxMate's source payload is the PINT-AE document ``build_pint_ae_payload``
already stores. Create the integration for country AE against that JSON, map
the fields, pass the testbed, and link the source before ``purpose=invoicing``.

Request shape: https://docs.complyance.io/api-reference/unify/submit-and-retrieve/
Document types: https://docs.complyance.io/api-reference/gets/document-types/
Status: https://docs.complyance.io/api-reference/unify/documents/
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urljoin

import frappe
import requests
from frappe import _

from taxmate.uae_e_invoicing.api_classes.base import BaseAPI
from taxmate.uae_e_invoicing.constants import TRANSACTION_TYPE_FLAGS

# Same host for sandbox and production; the API key and ``environment`` select it.
DEFAULT_BASE_URL = "https://prod.gets.complyance.io"

# UNCL 1001 as TaxMate stores it → GETS base + modifiers.
# 361 is TaxMate's self-billed credit note; Complyance's UAE selection for that
# document is credit_note + self_billed (their type code 261).
_DOCUMENT_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
	"380": ("tax_invoice", ()),
	"381": ("credit_note", ()),
	"480": ("tax_invoice", ("out_of_scope",)),
	"81": ("credit_note", ("out_of_scope",)),
	"389": ("tax_invoice", ("self_billed",)),
	"361": ("credit_note", ("self_billed",)),
	"261": ("credit_note", ("self_billed",)),
}

# BTAE-02 flag name → Unify modifier. ``summary_invoice`` is GETS ``summary``.
_FLAG_MODIFIERS = {
	"free_trade_zone": "free_trade_zone",
	"deemed_supply": "deemed_supply",
	"margin_scheme": "margin_scheme",
	"summary_invoice": "summary",
	"continuous_supply": "continuous_supply",
	"disclosed_agent_billing": "disclosed_agent",
	"e_commerce": "e_commerce",
	"export": "export",
}

# Non-terminal states stay Submitted so the poller keeps checking and the
# retry job does not POST a second invoice.
_STATE_STATUS = {
	"submitted": "Submitted",
	"processing": "Submitted",
	"delivery_success": "Submitted",
	"delivery_failed": "Submitted",
	"final_valid": "Accepted",
	"final_invalid": "Rejected",
	"rejected": "Rejected",
}


class ComplyanceSourceError(ValueError):
	pass


class ComplyanceDocumentTypeError(ValueError):
	pass


def parse_complyance_source(value: str | None) -> str:
	"""Return ``name:version``. Complyance splits the source on the last colon."""
	raw = (value or "").strip()
	name, sep, version = raw.rpartition(":")
	if not sep or not name or not version or any(ch.isspace() for ch in raw):
		raise ComplyanceSourceError(raw)
	return raw


def document_type_for(payload: dict[str, Any]) -> dict[str, Any]:
	"""GETS ``documentType`` for a PINT-AE payload. Modifiers follow the UAE table."""
	code = str(payload.get("InvoiceTypeCode") or "").strip()
	try:
		base, fixed = _DOCUMENT_TYPES[code]
	except KeyError as exc:
		raise ComplyanceDocumentTypeError(code) from exc

	modifiers: list[str] = list(fixed)
	flags = str(payload.get("InvoiceTransactionTypeCode") or "")
	for index, flag_name in enumerate(TRANSACTION_TYPE_FLAGS):
		if index < len(flags) and flags[index] == "1":
			modifier = _FLAG_MODIFIERS[flag_name]
			if modifier not in modifiers:
				modifiers.append(modifier)
	return {"base": base, "modifiers": modifiers}


def build_unify_request(
	payload: dict[str, Any],
	*,
	source: str | None,
	environment: str,
	purpose: str,
) -> dict[str, Any]:
	"""Unify envelope. ``payload`` stays in TaxMate's PINT-AE shape."""
	if environment not in ("sandbox", "production"):
		raise ValueError(environment)
	if purpose not in ("invoicing", "validate", "mapping"):
		raise ValueError(purpose)

	body: dict[str, Any] = {
		"country": "AE",
		"environment": environment,
		"purpose": purpose,
		"documentType": document_type_for(payload),
		"payload": payload,
	}
	# Required for invoicing and validate. Sent for mapping when the source is known
	# so Payload Manager can associate the sample with that source.
	if purpose != "mapping" or (source or "").strip():
		body["source"] = parse_complyance_source(source)
	return body


def taxmate_status_for_state(state: str | None) -> str | None:
	"""Map a Complyance ``data.state`` onto a TaxMate e-invoice status."""
	if not state:
		return None
	return _STATE_STATUS.get(str(state).strip().lower())


class ComplyanceAPI(BaseAPI):
	API_NAME = "UAE E-Invoice Complyance"
	BASE_PATH = "api/v3"

	def setup(self):
		try:
			self.source = parse_complyance_source(self.settings.participant_id)
		except ComplyanceSourceError:
			frappe.throw(
				_("Complyance source must be name:version, for example taxmate:1.0."),
				title=_("ASP Configuration Missing"),
			)
		self.environment = "sandbox" if self.sandbox_mode else "production"

	def get_auth_headers(self) -> dict[str, str]:
		"""Unify uses the API key as a bearer token, not OAuth client credentials."""
		if not self.settings.auth_key:
			frappe.throw(
				_("Set the Complyance API key in Auth Key on UAE Tax Settings."),
				title=_("ASP Authentication Missing"),
			)
		return {"Authorization": f"Bearer {self.settings.get_password('auth_key')}"}

	def get_url(self, *parts: str) -> str:
		base = (self.settings.base_url or DEFAULT_BASE_URL).rstrip("/") + "/"
		path_parts = [p.strip("/") for p in parts if p]
		if self.BASE_PATH:
			path_parts.insert(0, self.BASE_PATH.strip("/"))
		return urljoin(base, "/".join(path_parts))

	def _make_request(
		self,
		method: str,
		path: str,
		data: dict | None = None,
		params: dict | None = None,
	) -> Any:
		# ``new-api: true`` selects the current JSON envelope. XML does not use it.
		previous = self.default_headers
		if method == "POST":
			self.default_headers = {**previous, "new-api": "true"}
		try:
			return super()._make_request(method, path, data=data, params=params)
		finally:
			self.default_headers = previous

	def submit_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
		body = build_unify_request(
			payload,
			source=self.source,
			environment=self.environment,
			purpose="invoicing",
		)
		try:
			response = self.post("unify", body) or {}
		except requests.HTTPError as exc:
			_raise_unify_error(exc)
		# HTTP 200 means validated and stored, not FTA/Peppol acceptance.
		return {
			"status": "Submitted",
			"document_id": response.get("documentId"),
			"uuid": payload.get("UUID"),
			"raw": response,
		}

	def submit_mapping_sample(self, payload: dict[str, Any]) -> dict[str, Any]:
		"""Save this payload in Payload Manager (``purpose=mapping``). Not an e-invoice."""
		body = build_unify_request(
			payload,
			source=self.source,
			environment=self.environment,
			purpose="mapping",
		)
		try:
			response = self.post("unify", body) or {}
		except requests.HTTPError as exc:
			_raise_unify_error(exc)
		return {
			"payload_id": response.get("payloadId"),
			"raw": response,
		}

	def get_document_status(self, document_id: str) -> dict[str, Any]:
		body = self._sales_document(document_id)
		data = body.get("data") if isinstance(body.get("data"), dict) else {}
		state = data.get("state")
		status = taxmate_status_for_state(state)
		result: dict[str, Any] = {"document_status": state, "raw": body}
		if status:
			result["status"] = status
		return result

	def get_document_xml(self, document_id: str) -> bytes:
		body = self._sales_document(document_id)
		data = body.get("data") if isinstance(body.get("data"), dict) else {}
		artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
		return _decode_b64(artifacts.get("invoiceXmlBase64"))

	def get_document_pdf(self, document_id: str) -> bytes:
		# ``pdfBase64`` is on the status route once the document is compliant.
		body = self.get(f"documents/{document_id}/status") or {}
		if not isinstance(body, dict):
			return b""
		encoded = body.get("pdfBase64")
		data = body.get("data")
		if not encoded and isinstance(data, dict):
			encoded = data.get("pdfBase64")
		return _decode_b64(encoded)

	def _sales_document(self, document_id: str) -> dict[str, Any]:
		cached_id = getattr(self, "_status_cache_id", None)
		cached = getattr(self, "_status_cache", None)
		if cached_id == document_id and isinstance(cached, dict):
			return cached
		body = self.get(f"documents/{document_id}", params={"type": "sales"}) or {}
		if not isinstance(body, dict):
			body = {}
		self._status_cache_id = document_id
		self._status_cache = body
		return body


def _decode_b64(value: Any) -> bytes:
	if not value or not isinstance(value, str):
		return b""
	return base64.b64decode(value)


def _error_lines(errors: Any) -> str:
	if not isinstance(errors, list):
		return ""
	lines: list[str] = []
	for err in errors:
		if not isinstance(err, dict):
			continue
		message = err.get("message")
		if not message:
			continue
		code = err.get("code")
		lines.append(f"{code}: {message}" if code else str(message))
	return "\n".join(lines)


def _raise_unify_error(exc: requests.HTTPError) -> None:
	message = str(exc)
	response = exc.response
	if response is not None:
		try:
			body = response.json()
		except Exception:
			body = None
		if isinstance(body, dict):
			lines = _error_lines(body.get("errors"))
			if lines:
				message = lines
			elif body.get("message"):
				message = str(body["message"])
	frappe.throw(message[:2000], title=_("Complyance rejected the invoice"))
