app_name = "taxmate"
app_title = "TaxMate"
app_publisher = "Sourav Singh"
app_description = "UAE accounting on ERPNext: VAT, e-invoicing, corporate tax, and compliance tracking."
app_email = "sourav@ascratech.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "taxmate",
		"logo": "/assets/taxmate/logo.svg",
		"title": "TaxMate",
		"route": "/taxmate",
		"has_permission": "taxmate.api.permission.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/taxmate/css/taxmate.css"
app_include_js = [
	"/assets/taxmate/js/taxmate_e_invoice.js",
	"/assets/taxmate/js/taxmate_search.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/taxmate/css/taxmate.css"
# web_include_js = "/assets/taxmate/js/taxmate.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "taxmate/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Company": "public/js/company.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Purchase Invoice": "public/js/purchase_invoice.js",
}
doctype_list_js = {
	"Sales Invoice": "public/js/sales_invoice_list.js",
	"Purchase Invoice": "public/js/purchase_invoice_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "taxmate/public/icons.svg"

# Home Pages
# ----------

# Everyone except Administrator lands on /taxmate after login (no Desk).
get_website_user_home_page = "taxmate.setup.spa_roles.website_user_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# React SPA at /taxmate (frappe-react-sdk). Nested routes stay on the same page.
# Do not add the bundle to app_include_js — this is not a Desk extension.
website_route_rules = [
	{"from_route": "/taxmate/<path:app_path>", "to_route": "taxmate"},
]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# Print templates call tm_is_arabic() so Arabic headings follow the request language.
jinja = {
	"methods": [
		"taxmate.utils.jinja_methods",
	],
}

# Installation
# ------------

# before_install = "taxmate.install.before_install"
after_install = "taxmate.install.after_install"
after_migrate = "taxmate.install.after_migrate"

# IDP Scan extension points (apps/idp reads these via frappe.get_hooks)
idp_after_extract = ["taxmate.idp.hooks_idp.idp_after_extract"]
idp_before_make_draft = ["taxmate.idp.hooks_idp.idp_before_make_draft"]


# Uninstallation
# ------------

# before_uninstall = "taxmate.uninstall.before_uninstall"
# after_uninstall = "taxmate.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "taxmate.utils.before_app_install"
# after_app_install = "taxmate.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "taxmate.utils.before_app_uninstall"
# after_app_uninstall = "taxmate.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "taxmate.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "taxmate.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"*": "taxmate.uae.permissions.get_permission_query_conditions",
}

has_permission = {
	"*": "taxmate.uae.permissions.has_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Company": {
		"validate": "taxmate.uae.company.validate",
		"after_insert": [
			"taxmate.uae.company.after_insert",
			"taxmate.uae_compliance.company.after_insert",
			"taxmate.uae_corporate_tax.company.after_insert",
		],
		"on_update": "taxmate.uae.company.on_update",
	},
	"Customer": {
		"validate": "taxmate.uae.validation.validate_party_trn",
	},
	"Supplier": {
		"validate": "taxmate.uae.validation.validate_party_trn",
	},
	"Address": {
		"validate": "taxmate.uae.validation.validate_address_emirate",
	},
	"Item": {
		"validate": "taxmate.uae_vat.overrides.item.validate",
	},
	"Sales Order": {
		"validate": "taxmate.uae_vat.overrides.sales_order.validate",
		"before_submit": "taxmate.uae_vat.overrides.sales_order.before_submit",
	},
	"Sales Invoice": {
		"validate": [
			"taxmate.uae_vat.overrides.sales_invoice.validate",
			"taxmate.uae_e_invoicing.overrides.sales_invoice.validate",
			"taxmate.uae_corporate_tax.overrides.sales_invoice.validate",
		],
		"before_submit": "taxmate.uae_e_invoicing.overrides.sales_invoice.before_submit",
		"on_submit": "taxmate.uae_e_invoicing.overrides.sales_invoice.on_submit",
		"before_cancel": [
			"taxmate.uae_vat.overrides.sales_invoice.before_cancel",
			"taxmate.uae_e_invoicing.overrides.sales_invoice.before_cancel",
		],
		"on_cancel": "taxmate.uae_e_invoicing.overrides.sales_invoice.on_cancel",
	},
	"Purchase Invoice": {
		"validate": [
			"taxmate.uae_vat.overrides.purchase_invoice.validate",
			"taxmate.uae_e_invoicing.overrides.purchase_invoice.validate",
			"taxmate.uae_corporate_tax.overrides.purchase_invoice.validate",
		],
		"before_submit": "taxmate.uae_e_invoicing.overrides.purchase_invoice.before_submit",
		"on_submit": "taxmate.uae_e_invoicing.overrides.purchase_invoice.on_submit",
		"before_cancel": [
			"taxmate.uae_vat.overrides.purchase_invoice.before_cancel",
			"taxmate.uae_e_invoicing.overrides.purchase_invoice.before_cancel",
		],
		"on_cancel": "taxmate.uae_e_invoicing.overrides.purchase_invoice.on_cancel",
	},
	# Mobile device tokens: sign out devices when the user is disabled or the password changes.
	"User": {
		"before_validate": "taxmate.api.mobile_auth.user_before_validate",
		"on_update": "taxmate.api.mobile_auth.user_on_update",
		"on_trash": "taxmate.api.mobile_auth.user_on_trash",
	},
}

for _retained in (
	"UAE VAT 201 Filing Log",
	"UAE CT Filing Log",
	"UAE ESR Filing",
	"UAE Excise Filing Log",
	"UAE Customs Declaration",
	"UAE Bad Debt Relief",
	"UAE Capital Goods Adjustment",
	"UAE VAT Group",
	"UAE FTA Audit Pack",
):
	doc_events.setdefault(_retained, {})
	doc_events[_retained]["on_trash"] = "taxmate.uae.retention.on_trash"

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"taxmate.uae_e_invoicing.background_jobs.retry.retry_failed_e_invoices",
		"taxmate.uae_e_invoicing.background_jobs.status_poll.poll_submitted_e_invoices",
	],
	"daily": [
		"taxmate.uae_compliance.notifications.refresh_all_statuses",
		"taxmate.uae_compliance.notifications.send_deadline_reminders",
		"taxmate.uae_vat.notifications.send_vat_201_reminders",
		"taxmate.uae_e_invoicing.notifications.send_e_invoice_reminders",
		"taxmate.uae_corporate_tax.notifications.send_ct_reminders",
		"taxmate.uae_vat.utils.late_filing.sync_late_filing_notices",
		"taxmate.api.mobile_auth.cleanup_devices",
	],
}

# Testing
# -------

# before_tests = "taxmate.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Mixin runs before ERPNext's Purchase Invoice controller. It does not
# replace reverse-charge posting. get_gl_entries installs a binder so
# ERPNext's UAE regional ledger sees this invoice's company when it
# chooses the VAT credit. Setting the flag earlier is cleared before then.
extend_doctype_class = {
	"Purchase Invoice": "taxmate.uae_vat.overrides.purchase_invoice.PurchaseInvoiceReverseCharge",
}

# Overriding Methods
# ------------------------------
override_whitelisted_methods = {
	"idp.api.settings.get_settings": "taxmate.idp.clerk.get_settings",
	"idp.api.conversation.confirm_card": "taxmate.idp.clerk.confirm_card",
	# Same behaviour, then signs out the user's TaxMate mobile devices.
	"frappe.core.doctype.user.user.update_password": "taxmate.api.mobile_auth.update_password",
}

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "taxmate.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
before_request = ["taxmate.setup.desk_gate.block_desk_for_non_admin"]
# after_request = ["taxmate.utils.after_request"]

# Job Events
# ----------
# before_job = ["taxmate.utils.before_job"]
# after_job = ["taxmate.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# TaxMate mobile app: ``Authorization: TaxMate <device_token>`` (no-op for any other scheme).
auth_hooks = [
	"taxmate.api.mobile_auth.validate",
]

extend_bootinfo = "taxmate.search.boot_session"

# Header company switcher: logout clears ERPNext's session-default company;
# put the user's chosen company back when they sign in again.
on_session_creation = ["taxmate.utils.company.restore_active_company"]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
