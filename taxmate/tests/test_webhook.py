"""Webhook fail-closed tests."""

from __future__ import annotations

import hashlib
import hmac
import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestWebhookSignature(unittest.TestCase):
	def test_unsigned_without_secret_is_rejected(self):
		from taxmate.uae_e_invoicing.utils.webhook import _verify_signature

		settings = frappe._dict(webhook_secret=None, asp_provider="Complyance", sandbox_mode=1)
		with patch("frappe.get_cached_doc", return_value=settings):
			self.assertFalse(_verify_signature(b"{}"))

	def test_signature_reads_password_store_when_field_is_blank(self):
		from taxmate.uae_e_invoicing.utils.webhook import _verify_signature

		class Settings:
			webhook_secret = ""

			def get_password(self, fieldname, raise_exception=True):
				self.fieldname = fieldname
				return "sekrit"

		settings = Settings()
		raw = b"{}"
		digest = hmac.new(b"sekrit", raw, hashlib.sha256).hexdigest()
		request = frappe._dict(headers={"X-Webhook-Signature": digest})
		with (
			patch("frappe.get_cached_doc", return_value=settings),
			patch("frappe.request", request),
		):
			self.assertTrue(_verify_signature(raw))
		self.assertEqual(settings.fieldname, "webhook_secret")


class TestWebhookEndpoint(FrappeTestCase):
	def test_unsigned_post_does_not_insert_log(self):
		from taxmate.uae_e_invoicing.utils.webhook import uae_e_invoice_webhook

		before = (
			frappe.db.count("UAE E-Invoice Webhook Log")
			if frappe.db.exists("DocType", "UAE E-Invoice Webhook Log")
			else 0
		)
		frappe.local.request = frappe._dict(
			method="POST",
			get_data=lambda: b"{}",
			get_json=lambda silent=True: {},
			headers={},
		)
		frappe.local.response = frappe._dict()
		result = uae_e_invoice_webhook()
		self.assertFalse(result.get("ok"))
		self.assertEqual(frappe.local.response.http_status_code, 401)
		if frappe.db.exists("DocType", "UAE E-Invoice Webhook Log"):
			self.assertEqual(frappe.db.count("UAE E-Invoice Webhook Log"), before)
