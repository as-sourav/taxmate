// Copyright (c) 2026, Sourav Singh and contributors
// For license information, please see license.txt

frappe.ui.form.on("UAE Tax Settings", {
	refresh(frm) {
		if (frm.doc.sandbox_mode) {
			frm.dashboard.set_headline_alert(
				__(
					"Sandbox mode sends Unify requests with environment sandbox. They are not production filings."
				),
				"orange"
			);
		}
	},
});
