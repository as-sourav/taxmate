"""Webhook fail-closed tests."""

from __future__ import annotations

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
