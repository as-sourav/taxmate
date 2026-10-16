"""Force UAE Tax Settings onto Complyance after Flick/Sandbox removal.

Clears ``participant_id`` because that field previously held Peppol IDs
(often ``0235:…``) that look like Complyance ``name:version`` sources but
are not. Operators must set a real Complyance source and API key before
submitting invoices.
"""

from __future__ import annotations

import frappe


_CLEAR = (
	"participant_id",
	"participant_details",
	"webhook_subscription_id",
	"client_id",
)


def execute():
	if not frappe.db.exists("DocType", "UAE Tax Settings"):
		return

	# Singles — skip Document.validate so empty source sites still migrate.
	frappe.db.set_single_value(
		"UAE Tax Settings", "asp_provider", "Complyance", update_modified=False
	)
	meta = frappe.get_meta("UAE Tax Settings")
	for field in _CLEAR:
		if meta.has_field(field):
			frappe.db.set_single_value(
				"UAE Tax Settings", field, "", update_modified=False
			)
