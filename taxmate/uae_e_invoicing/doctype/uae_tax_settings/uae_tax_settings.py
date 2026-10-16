# Copyright (c) 2026, Sourav Singh and contributors
# For license information, please see license.txt

from __future__ import annotations

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class UAETaxSettings(Document):
	def validate(self):
		self.asp_provider = "Complyance"
		if self.sla_days is not None and cint(self.sla_days) < 1:
			frappe.throw(_("Transmission SLA Days must be at least 1."))
		if self.archive_retention_years is not None and cint(self.archive_retention_years) < 5:
			frappe.throw(_("Archive Retention must be at least 5 years (FTA minimum)."))
		self._validate_base_url()
		self._validate_complyance_source()

	def _validate_complyance_source(self):
		# Empty is allowed until the site configures Complyance; submit rejects blanks.
		if not (self.participant_id or "").strip():
			return
		from taxmate.uae_e_invoicing.api_classes.complyance import (
			ComplyanceSourceError,
			parse_complyance_source,
		)

		try:
			parse_complyance_source(self.participant_id)
		except ComplyanceSourceError:
			frappe.throw(
				_("Complyance source must be name:version, for example taxmate:1.0."),
				title=_("ASP Configuration Missing"),
			)

	def _validate_base_url(self):
		if not self.base_url:
			return
		parsed = urlparse(self.base_url)
		host = (parsed.hostname or "").lower()
		if parsed.scheme != "https":
			frappe.throw(_("ASP Base URL must use HTTPS."))
		if not host or host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
			frappe.throw(_("ASP Base URL cannot point at a local host."))
		if parsed.username or parsed.password:
			frappe.throw(_("ASP Base URL must not include credentials."))
