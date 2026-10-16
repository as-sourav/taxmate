// Copyright (c) 2026, Sourav Singh and contributors
// For license information, please see license.txt

/* global taxmate */

frappe.ui.form.on("Company", {
	refresh(frm) {
		taxmate.show_uae_readiness(frm);
	},
	country(frm) {
		taxmate.show_uae_readiness(frm);
	},
});

frappe.provide("taxmate");

taxmate.show_uae_readiness = function (frm) {
	if (!frm.doc.name || frm.doc.country !== "United Arab Emirates") {
		frm.dashboard.clear_headline();
		return;
	}

	frappe.call({
		method: "taxmate.uae.readiness.get_uae_readiness_checklist",
		args: { company: frm.doc.name },
		callback(r) {
			if (!r.message || !r.message.applicable) {
				return;
			}

			const data = r.message;
			const lines = (data.items || []).map((item) => {
				const mark = item.ok ? "✓" : "○";
				return `${mark} ${item.label}`;
			});

			const color = data.ready ? "green" : "orange";
			const mandateHtml = taxmate._mandate_headline(data.e_invoice_mandate);
			frm.dashboard.set_headline_alert(
				`<div>
					<strong>${frappe.utils.escape_html(data.message)}</strong>
					<div class="text-muted" style="margin-top: 4px;">${lines
						.map((l) => frappe.utils.escape_html(l))
						.join("<br>")}</div>
					${mandateHtml}
					<div style="margin-top: 6px;">
						<a href="/app/taxmate-settings">${__("TaxMate Settings")}</a>
						&nbsp;|&nbsp;
						<a href="/app/uae-vat-settings">${__("UAE VAT Settings")}</a>
						&nbsp;|&nbsp;
						<a href="/app/query-report/UAE%20VAT%20201">${__("UAE VAT 201")}</a>
					</div>
				</div>`,
				color
			);
		},
	});
};

taxmate._mandate_headline = function (mandate) {
	if (!mandate || !mandate.cohort) {
		return "";
	}
	const esc = frappe.utils.escape_html;
	const lines = [];
	lines.push(esc(mandate.cohort_label || mandate.cohort));
	if (mandate.cohort === "Unclassified") {
		lines.push(
			esc(
				__(
					"Set last accounting-period FS revenue (MD 244) or a cohort override. TaxMate does not classify from the general ledger."
				)
			)
		);
	} else {
		if (mandate.asp_appointment_deadline) {
			const aspBits = [__("ASP appointment"), mandate.asp_appointment_deadline];
			if (mandate.days_to_asp_deadline != null) {
				aspBits.push(
					mandate.asp_deadline_passed
						? __("deadline passed")
						: __("{0} day(s) left", [mandate.days_to_asp_deadline])
				);
			}
			lines.push(esc(aspBits.join(" — ")));
		}
		if (mandate.go_live_date) {
			const liveBits = [__("Go-live"), mandate.go_live_date];
			if (mandate.days_to_go_live != null) {
				liveBits.push(
					mandate.mandate_live
						? __("now mandatory")
						: __("{0} day(s) left", [mandate.days_to_go_live])
				);
			}
			lines.push(esc(liveBits.join(" — ")));
		}
	}
	if (mandate.disclaimer) {
		lines.push(`<span class="text-muted">${esc(mandate.disclaimer)}</span>`);
	}
	return `<div style="margin-top: 8px;"><strong>${esc(
		__("E-invoicing mandate")
	)}</strong><div>${lines.join("<br>")}</div></div>`;
};
