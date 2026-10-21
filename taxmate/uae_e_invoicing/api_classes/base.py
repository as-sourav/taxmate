"""Base ASP API client: OAuth2 token lifecycle + Integration Request logging."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.synchronization import filelock

# Refresh the token this many seconds before its actual expiry
TOKEN_EXPIRY_BUFFER = 120
TOKEN_LOCK_TIMEOUT = 30


class BaseAPI:
	API_NAME = "UAE E-Invoice"
	BASE_PATH = ""
	TOKEN_PATH = "oauth/token"
	# Header used for the static auth key; providers may override
	AUTH_KEY_HEADER = "Authorization"

	def __init__(self):
		self.settings = frappe.get_cached_doc("UAE Tax Settings")
		self.sandbox_mode = bool(self.settings.sandbox_mode)
		self.default_headers = {"Content-Type": "application/json"}
		self.setup()

	def setup(self):
		pass

	# ------------------------------------------------------------------
	# Auth
	# ------------------------------------------------------------------

	def get_auth_headers(self) -> dict[str, str]:
		"""Prefer OAuth2 client-credentials; fall back to the static auth key.

		Password values live in ``__Auth``. They are not loaded onto the document.
		"""
		client_id = (self.settings.get("client_id") or "").strip()
		client_secret = self.settings.get_password("client_secret", raise_exception=False)
		if client_id and client_secret:
			token = self._get_valid_access_token()
			return {"Authorization": f"Bearer {token}"}

		key = self.settings.get_password("auth_key", raise_exception=False)
		if key:
			if self.AUTH_KEY_HEADER == "Authorization":
				return {"Authorization": f"Bearer {key}"}
			return {self.AUTH_KEY_HEADER: key}

		frappe.throw(
			_("Configure OAuth2 credentials or an Auth Key in UAE Tax Settings."),
			title=_("ASP Authentication Missing"),
		)

	def _get_valid_access_token(self) -> str:
		expiry = self.settings.token_expiry and get_datetime(self.settings.token_expiry)
		if (
			self.settings.access_token
			and expiry
			and expiry > add_to_date(now_datetime(), seconds=TOKEN_EXPIRY_BUFFER)
		):
			return self.settings.get_password("access_token")

		return self._fetch_access_token()

	def _token_still_valid(self) -> str | None:
		"""Return cached token if still within the refresh buffer; else None."""
		expiry = self.settings.token_expiry and get_datetime(self.settings.token_expiry)
		if (
			self.settings.access_token
			and expiry
			and expiry > add_to_date(now_datetime(), seconds=TOKEN_EXPIRY_BUFFER)
		):
			return self.settings.get_password("access_token")
		return None

	def _fetch_access_token(self) -> str:
		"""OAuth2 client-credentials grant with singleflight lock.

		Concurrent workers wait on the same site lock, then re-check the
		cached token so only one process hits the ASP token endpoint.
		"""
		lock_name = f"uae_asp_oauth_token_{frappe.local.site}"
		with filelock(lock_name, timeout=TOKEN_LOCK_TIMEOUT):
			# Another worker may have refreshed while we waited
			self.settings = frappe.get_doc("UAE Tax Settings")
			cached = self._token_still_valid()
			if cached:
				return cached

			url = self.get_url(self.TOKEN_PATH)
			payload = {
				"grant_type": "client_credentials",
				"client_id": self.settings.client_id,
				"client_secret": self.settings.get_password("client_secret"),
			}

			response = requests.post(url, json=payload, timeout=30)
			if not response.ok:
				frappe.log_error(
					title=f"{self.API_NAME}: token request failed",
					message=f"{response.status_code}: {response.text[:2000]}",
				)
				frappe.throw(
					_("Could not obtain an access token from the ASP ({0}).").format(response.status_code),
					title=_("ASP Authentication Failed"),
				)

			data = response.json()
			token = data.get("access_token")
			if not token:
				frappe.throw(_("ASP token response did not include an access token."))

			expires_in = int(data.get("expires_in") or 3600)
			settings_doc = frappe.get_doc("UAE Tax Settings")
			settings_doc.set_password("access_token", token)
			settings_doc.token_expiry = add_to_date(now_datetime(), seconds=expires_in)
			settings_doc.save(ignore_permissions=True)
			self.settings = settings_doc
			return token

	# ------------------------------------------------------------------
	# HTTP
	# ------------------------------------------------------------------

	def get_url(self, *parts: str) -> str:
		base = (self.settings.base_url or "").rstrip("/") + "/"
		path_parts = [p.strip("/") for p in parts if p]
		if self.BASE_PATH:
			path_parts.insert(0, self.BASE_PATH.strip("/"))
		return urljoin(base, "/".join(path_parts))

	def post(self, path: str, data: dict | None = None) -> Any:
		return self._make_request("POST", path, data=data)

	def put(self, path: str, data: dict | None = None) -> Any:
		return self._make_request("PUT", path, data=data)

	def get(self, path: str, params: dict | None = None) -> Any:
		return self._make_request("GET", path, params=params)

	def submit_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
		"""Submit a PINT-AE (or mapped) document. Providers must implement this."""
		raise NotImplementedError

	def get_document_status(self, document_id: str) -> dict[str, Any]:
		"""Poll ASP status for a previously submitted document."""
		raise NotImplementedError

	def get_document_xml(self, document_id: str) -> bytes:
		"""Fetch the signed XML archive for a document."""
		raise NotImplementedError

	def get_document_pdf(self, document_id: str) -> bytes:
		"""Fetch the rendered PDF archive for a document."""
		raise NotImplementedError

	def get_binary(self, path: str) -> bytes:
		"""Fetch binary content (XML / PDF) without JSON decoding."""
		headers = {**self.default_headers, **self.get_auth_headers()}
		headers.pop("Content-Type", None)
		response = requests.get(self.get_url(path), headers=headers, timeout=60)
		response.raise_for_status()
		return response.content

	def _make_request(
		self,
		method: str,
		path: str,
		data: dict | None = None,
		params: dict | None = None,
	) -> Any:
		url = self.get_url(path) if path else (self.settings.base_url or "")
		headers = {**self.default_headers, **self.get_auth_headers()}

		integration = frappe.get_doc(
			{
				"doctype": "Integration Request",
				"integration_request_service": self.API_NAME,
				"status": "Queued",
				"url": url,
				"request_headers": frappe.as_json(self._mask(headers)),
				"data": frappe.as_json(self._mask_payload(data)),
			}
		)
		integration.insert(ignore_permissions=True)

		try:
			response = requests.request(
				method,
				url,
				headers=headers,
				json=data,
				params=params,
				timeout=30,
			)
			integration.db_set(
				{
					"status": "Completed" if response.ok else "Failed",
					"output": response.text[:100000],
				},
				update_modified=False,
			)
			response.raise_for_status()
			if response.content:
				return response.json()
			return {}
		except Exception as e:
			integration.db_set(
				{"status": "Failed", "error": str(e)[:5000]},
				update_modified=False,
			)
			raise

	def _mask(self, headers: dict) -> dict:
		masked = dict(headers)
		for key in ("Authorization",):
			if key in masked:
				masked[key] = "*****"
		return masked

	def _mask_payload(self, data: dict | None) -> dict:
		"""Redact secrets before persisting request bodies to Integration Request."""
		if not data:
			return {}
		masked = dict(data)
		for key in (
			"secret",
			"client_secret",
			"password",
			"access_token",
			"token",
			"auth_key",
			"webhook_secret",
		):
			if masked.get(key):
				masked[key] = "*****"
		return masked
