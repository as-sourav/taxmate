"""ASP webhook receiver + subscription registration."""

from __future__ import annotations

import hashlib
import hmac

import frappe
from frappe import _
from frappe.utils import get_url

from taxmate.uae_e_invoicing.utils.e_invoice import apply_status_update

WEBHOOK_METHOD_PATH = "/api/method/taxmate.uae_e_invoicing.utils.webhook.uae_e_invoice_webhook"


# ASP callbacks are unauthenticated at the Frappe session layer; auth is HMAC
# over the request body using the configured webhook secret (see _verify_signature).
@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def uae_e_invoice_webhook():
	"""Receive ASP status callbacks, verify the secret, update statuses."""
	if frappe.request.method != "POST":
		frappe.throw(_("Method not allowed"), frappe.PermissionError)

	raw_body = frappe.request.get_data() or b""
	payload = frappe.request.get_json(silent=True) or {}
	signature_valid = _verify_signature(raw_body)
	if not signature_valid:
		frappe.local.response.http_status_code = 401
		return {"ok": False, "message": "Invalid webhook signature"}

	event_type = payload.get("event") or payload.get("event_type") or "unknown"
	document_id = (
		payload.get("document_id")
		or payload.get("documentId")
		or (payload.get("data") or {}).get("document_id")
	)
	asp_status = (
		payload.get("status") or (payload.get("data") or {}).get("status") or _status_from_event(event_type)
	)

	webhook_log = frappe.get_doc(
		{
			"doctype": "UAE E-Invoice Webhook Log",
			"event_type": event_type,
			"asp_document_id": document_id,
			"asp_status": asp_status,
			"signature_valid": int(signature_valid),
			"payload": frappe.as_json(payload),
		}
	)
	webhook_log.insert(ignore_permissions=True)

	log_name = None
	incoming_name = None

	if _is_incoming_document_event(event_type, payload):
		from taxmate.uae_e_invoicing.doctype.uae_incoming_invoice.uae_incoming_invoice import (
			create_from_webhook,
		)

		incoming_name = create_from_webhook(payload)
	elif document_id and asp_status:
		log_name = apply_status_update(document_id, asp_status, response=payload)

	webhook_log.db_set(
		{"processed": int(bool(log_name or incoming_name)), "e_invoice_log": log_name},
		update_modified=False,
	)

	return {"ok": True, "processed": bool(log_name or incoming_name)}


@frappe.whitelist()
def register_webhook():
	"""Register this site's callback URL with the configured ASP."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	from taxmate.uae_e_invoicing.utils.e_invoice import get_api

	settings = frappe.get_doc("UAE Tax Settings")
	secret = settings.get_password("webhook_secret", raise_exception=False)
	if not secret:
		frappe.throw(_("Set a Webhook Secret in UAE Tax Settings first."))

	api = get_api()
	if not hasattr(api, "register_webhook"):
		frappe.throw(_("The configured ASP does not support webhook registration."))

	callback_url = get_url(WEBHOOK_METHOD_PATH)
	response = api.register_webhook(callback_url, secret)

	subscription_id = response.get("subscription_id") or response.get("subscriptionId") or response.get("id")
	if subscription_id:
		frappe.db.set_single_value("UAE Tax Settings", "webhook_subscription_id", subscription_id)

	return {"ok": True, "subscription_id": subscription_id, "callback_url": callback_url}


@frappe.whitelist()
def get_webhook_subscription():
	"""Inspect the registered subscription and its recent deliveries at the ASP."""
	frappe.only_for(("System Manager", "Accounts Manager"))

	from taxmate.uae_e_invoicing.utils.e_invoice import get_api

	subscription_id = frappe.db.get_single_value("UAE Tax Settings", "webhook_subscription_id")
	if not subscription_id:
		frappe.throw(_("No webhook subscription registered yet — run Register Webhook first."))

	api = get_api()
	if not hasattr(api, "get_webhook_subscription"):
		frappe.throw(_("The configured ASP does not support subscription lookup."))

	result = {"subscription": api.get_webhook_subscription(subscription_id)}
	if hasattr(api, "get_webhook_deliveries"):
		result["deliveries"] = api.get_webhook_deliveries(subscription_id)
	return result


def _verify_signature(raw_body: bytes) -> bool:
	"""HMAC-SHA256 signature check; falls back to shared-secret header.

	Fail closed: unsigned requests are rejected. A webhook secret must be set
	in UAE Tax Settings; sandbox is not an exception.
	"""
	settings = frappe.get_cached_doc("UAE Tax Settings")
	getter = getattr(settings, "get_password", None)
	secret = getter("webhook_secret", raise_exception=False) if callable(getter) else settings.get("webhook_secret")
	if not secret:
		return False
	headers = frappe.request.headers

	signature = headers.get("X-Webhook-Signature")
	if signature:
		expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
		provided = signature.removeprefix("sha256=")
		return hmac.compare_digest(expected, provided)

	shared = headers.get("X-Webhook-Secret")
	if shared:
		return hmac.compare_digest(secret, shared)

	return False


def _is_incoming_document_event(event_type: str, payload: dict) -> bool:
	"""True only for explicit Corner-4 receive events (never infer from payload shape)."""
	return (event_type or "").lower() in ("invoice.received", "document.received")


def _status_from_event(event_type: str) -> str | None:
	"""Derive status from event names like 'invoice.accepted'."""
	if "." in (event_type or ""):
		return event_type.rsplit(".", 1)[-1]
	return None
