"""Party, item, chart of accounts, and payment helpers."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from taxmate.api.resource import (
	_as_data,
	_parse,
	assert_allowed_doctype,
	assert_company_read,
	require_login,
)
from taxmate.utils.company import get_default_company


@frappe.whitelist()
def get_defaults(company: str | None = None) -> dict[str, Any]:
	"""Company, currency, and fiscal year for new vouchers."""
	require_login()
	company = company or get_default_company()
	if not company:
		return {"company": None}

	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	row = frappe.db.get_value(
		"Company",
		company,
		["name", "default_currency", "country", "tax_id", "cost_center"],
		as_dict=True,
	)
	# accounts_frozen_till may not exist on every ERPNext version; fall back gracefully.
	frozen_till = None
	try:
		from erpnext.accounts.utils import get_post_dated_checks_details

		frozen_till = frappe.db.get_value("Accounts Settings", None, "acc_frozen_upto") or None
	except Exception:
		frozen_till = frappe.db.get_value("Accounts Settings", None, "acc_frozen_upto") or None

	out = {
		"company": row.name,
		"currency": row.default_currency,
		"country": row.country,
		"tax_id": row.tax_id,
		"cost_center": row.get("cost_center"),
		"fiscal_year": None,
		"accounts_frozen_till": str(frozen_till) if frozen_till else None,
	}
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_year

	try:
		fiscal = get_fiscal_year(company=company, as_dict=True)
		if fiscal:
			out["fiscal_year"] = fiscal.name
	except FiscalYearError:
		out["fiscal_year"] = None
	return out


@frappe.whitelist()
def get_party_details(
	party=None,
	party_type="Customer",
	company=None,
	doctype=None,
	posting_date=None,
	price_list=None,
	currency=None,
):
	if not party:
		frappe.throw(_("party is required"))
	require_login()
	assert_allowed_doctype(party_type)
	company = company or get_default_company()
	assert_company_read(company)
	if not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.party import get_party_details as erp_get_party_details

	details = erp_get_party_details(
		party=party,
		party_type=party_type,
		company=company,
		doctype=doctype,
		posting_date=posting_date,
		price_list=price_list,
		currency=currency,
	)
	# Desk defaults the transaction price list from Selling/Buying Settings
	# when the party and party group have none. Tax Rules may leave
	# taxes_and_charges empty; Desk then applies the company default template.
	if isinstance(details, dict):
		_stamp_default_price_list(details, party_type)
		_stamp_default_taxes(details, doctype, company, party_type)
		_stamp_vat_emirate(details, company)
	return details


@frappe.whitelist()
def get_item_details(ctx=None, doc=None, for_validate=False, overwrite_warehouse=True):
	require_login()
	ctx = _parse(ctx) or {}
	if not ctx.get("item_code"):
		frappe.throw(_("item_code is required"))
	assert_allowed_doctype("Item")
	if not frappe.has_permission("Item", "read", ctx["item_code"]):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	assert_company_read(ctx.get("company"))

	if ctx.get("company") and not ctx.get("currency"):
		ctx["currency"] = frappe.get_cached_value("Company", ctx["company"], "default_currency")
	if ctx.get("conversion_rate") in (None, ""):
		company_currency = (
			frappe.get_cached_value("Company", ctx["company"], "default_currency")
			if ctx.get("company")
			else None
		)
		if ctx.get("currency") and company_currency and ctx["currency"] != company_currency:
			frappe.throw(_("conversion_rate is required when currency differs from company currency"))
		ctx["conversion_rate"] = 1.0

	# Same fallback Desk uses: the form's price-list field is already
	# Standard Selling / Standard Buying before the user picks an item.
	if not ctx.get("price_list") and not ctx.get("selling_price_list") and not ctx.get("buying_price_list"):
		default_list = _settings_price_list(ctx.get("doctype"))
		if default_list:
			if ctx.get("doctype") in _BUYING_TXN:
				ctx["buying_price_list"] = default_list
			else:
				ctx["selling_price_list"] = default_list

	from erpnext.stock.get_item_details import get_item_details as erp_get_item_details

	out = erp_get_item_details(
		ctx,
		doc=doc,
		for_validate=for_validate,
		overwrite_warehouse=overwrite_warehouse,
	)
	# Desk fetch_from does not run on SPA insert. Stamp UAE classification
	# so invoice lines can send HS/SAC without a second Item get.
	if isinstance(out, dict) and ctx.get("item_code") and frappe.db.exists("Item", ctx["item_code"]):
		item = frappe.get_cached_doc("Item", ctx["item_code"])
		for field in ("uae_item_type", "hs_code", "sac_code"):
			if item.meta.has_field(field) and not out.get(field):
				out[field] = item.get(field)
	# Desk writes price_list_rate into the line rate. ERPNext leaves rate at 0
	# until the form script copies it, so the SPA would show a blank rate.
	if isinstance(out, dict):
		from frappe.utils import flt

		if not flt(out.get("rate")) and flt(out.get("price_list_rate")):
			out["rate"] = out["price_list_rate"]
	return out


@frappe.whitelist()
def get_account_tree(company: str | None = None, parent: str | None = None, include_disabled: bool = False):
	require_login()
	assert_allowed_doctype("Account")
	if not frappe.has_permission("Account", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	company = company or get_default_company()
	if not company:
		frappe.throw(_("Company is required"))
	assert_company_read(company)

	from erpnext.accounts.utils import get_children

	is_root = not parent
	return get_children(
		"Account",
		parent or company,
		company,
		is_root=is_root,
		include_disabled=include_disabled,
	)


@frappe.whitelist()
def get_outstanding_invoices(company, party_type, party, party_account=None):
	require_login()
	assert_allowed_doctype("Payment Entry")
	assert_allowed_doctype(party_type)
	if not company:
		frappe.throw(_("Company is required"))
	assert_company_read(company)
	frappe.has_permission(party_type, "read", party, throw=True)
	if not frappe.has_permission("Payment Entry", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if not party_account:
		from erpnext.accounts.party import get_party_account

		party_account = get_party_account(party_type, party, company)

	from erpnext.accounts.doctype.payment_entry.payment_entry import (
		get_outstanding_reference_documents,
	)

	return get_outstanding_reference_documents(
		{
			"company": company,
			"party_type": party_type,
			"party": party,
			"party_account": party_account,
			"get_outstanding_invoices": True,
		}
	)


@frappe.whitelist(methods=["POST"])
def get_payment_entry(dt, dn, party_amount=None, bank_account=None, payment_type=None):
	require_login()
	assert_allowed_doctype(dt)
	assert_allowed_doctype("Payment Entry")
	doc = frappe.get_doc(dt, dn)
	doc.check_permission("read")

	from erpnext.accounts.doctype.payment_entry.payment_entry import (
		get_payment_entry as erp_get_payment_entry,
	)

	return _as_data(
		erp_get_payment_entry(
			dt,
			dn,
			party_amount=party_amount,
			bank_account=bank_account,
			payment_type=payment_type,
		)
	)


_SELLING_TXN = frozenset({"Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "POS Invoice"})
_BUYING_TXN = frozenset({"Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice"})
_TXN_DOCTYPES = _SELLING_TXN | _BUYING_TXN


def _settings_price_list(doctype: str | None) -> str | None:
	"""Selling/Buying Settings price list — the Desk form-field default."""
	if doctype in _BUYING_TXN:
		return frappe.db.get_single_value("Buying Settings", "buying_price_list")
	return frappe.db.get_single_value("Selling Settings", "selling_price_list")


def _stamp_default_price_list(details: dict, party_type: str) -> None:
	if party_type == "Supplier":
		if not details.get("buying_price_list"):
			details["buying_price_list"] = frappe.db.get_single_value("Buying Settings", "buying_price_list")
	elif not details.get("selling_price_list"):
		details["selling_price_list"] = frappe.db.get_single_value("Selling Settings", "selling_price_list")


def _tax_master_doctype(doctype: str | None, party_type: str | None = None) -> str:
	if doctype in _BUYING_TXN or (not doctype and party_type == "Supplier"):
		return "Purchase Taxes and Charges Template"
	return "Sales Taxes and Charges Template"


def _stamp_default_taxes(
	details: dict, doctype: str | None, company: str | None, party_type: str | None = None
) -> None:
	"""Desk ``apply_default_taxes`` when Tax Rule returned no template."""
	if details.get("taxes_and_charges") or not company:
		return

	master = _tax_master_doctype(doctype, party_type)
	from erpnext.controllers.accounts_controller import (
		get_default_taxes_and_charges,
	)
	from erpnext.controllers.accounts_controller import (
		get_taxes_and_charges as erp_get_taxes_and_charges,
	)

	defaults = get_default_taxes_and_charges(master, company=company) or {}
	template = defaults.get("taxes_and_charges")
	if not template:
		# TaxMate UAE books ship titled templates; install sometimes leaves
		# is_default unset after manual template edits.
		template = frappe.db.get_value(master, {"company": company, "title": "UAE VAT 5%"}, "name")
	if not template:
		return
	details["taxes_and_charges"] = template
	if not details.get("taxes"):
		rows = defaults.get("taxes")
		if not rows:
			rows = erp_get_taxes_and_charges(master, template)
		if rows:
			details["taxes"] = rows


def _stamp_vat_emirate(details: dict, company: str | None) -> None:
	"""SPA has no Desk fetch_from; fill Place of Supply from company address."""
	if details.get("vat_emirate") or not company:
		return
	from taxmate.uae.constants import UAE_COUNTRY

	if frappe.get_cached_value("Company", company, "country") != UAE_COUNTRY:
		return
	from taxmate.uae_vat.utils.place_of_supply import resolve_company_emirate

	emirate = resolve_company_emirate(company, details.get("company_address"))
	if emirate:
		details["vat_emirate"] = emirate


@frappe.whitelist()
def apply_price_list(ctx=None, as_doc=False, doc=None):
	"""Reprice items from the price list (Desk ``apply_price_list``)."""
	require_login()
	ctx = _parse(ctx) or {}
	doctype = ctx.get("doctype")
	if not doctype or doctype not in _TXN_DOCTYPES:
		frappe.throw(_("doctype must be a sales or purchase transaction"))
	assert_allowed_doctype(doctype)
	assert_company_read(ctx.get("company"))
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.stock.get_item_details import apply_price_list as erp_apply_price_list

	return erp_apply_price_list(ctx, as_doc=as_doc, doc=_parse(doc))


@frappe.whitelist()
def apply_pricing_rule(args=None, doc=None):
	"""Apply Pricing Rules to line items (Desk ``apply_pricing_rule``)."""
	require_login()
	args = _parse(args) or {}
	doctype = args.get("doctype")
	if not doctype or doctype not in _TXN_DOCTYPES:
		frappe.throw(_("doctype must be a sales or purchase transaction"))
	assert_allowed_doctype(doctype)
	assert_company_read(args.get("company"))
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.doctype.pricing_rule.pricing_rule import (
		apply_pricing_rule as erp_apply_pricing_rule,
	)

	return erp_apply_pricing_rule(args, doc=_parse(doc))


@frappe.whitelist()
def get_taxes_and_charges(master_doctype=None, master_name=None):
	"""Tax child rows from a Sales/Purchase Taxes and Charges Template."""
	require_login()
	if not master_doctype or not master_name:
		frappe.throw(_("master_doctype and master_name are required"))
	if master_doctype not in (
		"Sales Taxes and Charges Template",
		"Purchase Taxes and Charges Template",
	):
		frappe.throw(_("Invalid tax template DocType"))
	assert_allowed_doctype(master_doctype)
	if not frappe.has_permission(master_doctype, "read", master_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.controllers.accounts_controller import (
		get_taxes_and_charges as erp_get_taxes_and_charges,
	)

	return erp_get_taxes_and_charges(master_doctype, master_name)


@frappe.whitelist()
def get_exchange_rate(
	from_currency=None,
	to_currency=None,
	transaction_date=None,
	args=None,
):
	"""Company conversion rate (Desk ``erpnext.setup.utils.get_exchange_rate``).

	``args`` is ``for_selling`` or ``for_buying``, matching Currency Exchange filters.
	Same currency returns 1. A missing rate returns 0 so the form can block save.
	"""
	require_login()
	if not from_currency or not to_currency:
		frappe.throw(_("from_currency and to_currency are required"))
	if args not in (None, "", "for_selling", "for_buying"):
		frappe.throw(_("args must be for_selling or for_buying"))
	assert_allowed_doctype("Currency Exchange")
	if not frappe.has_permission("Currency Exchange", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.setup.utils import get_exchange_rate as erp_get_exchange_rate
	from frappe.utils import flt

	return flt(erp_get_exchange_rate(from_currency, to_currency, transaction_date, args or None))


@frappe.whitelist()
def get_conversion_factor(item_code=None, uom=None):
	"""UOM conversion factor for an item (Desk ``get_conversion_factor``)."""
	require_login()
	if not item_code or not uom:
		frappe.throw(_("item_code and uom are required"))
	assert_allowed_doctype("Item")
	if not frappe.has_permission("Item", "read", item_code):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.stock.get_item_details import get_conversion_factor as erp_get_conversion_factor

	return erp_get_conversion_factor(item_code, uom)


@frappe.whitelist()
def get_payment_terms(
	terms_template=None,
	posting_date=None,
	grand_total=None,
	base_grand_total=None,
	bill_date=None,
):
	"""Payment schedule rows from a Payment Terms Template (Desk ``get_payment_terms``)."""
	require_login()
	if not terms_template:
		frappe.throw(_("terms_template is required"))
	assert_allowed_doctype("Payment Terms Template")
	if not frappe.has_permission("Payment Terms Template", "read", terms_template):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.controllers.accounts_controller import get_payment_terms as erp_get_payment_terms

	return erp_get_payment_terms(
		terms_template,
		posting_date=posting_date,
		grand_total=grand_total,
		base_grand_total=base_grand_total,
		bill_date=bill_date,
	)


@frappe.whitelist()
def get_credit_balance(
	customer: str | None = None, company: str | None = None, extra_amount: float | int | str = 0
):
	"""Advisory credit balance for Sales forms. Does not throw — submit still validates on the server."""
	require_login()
	if not customer:
		frappe.throw(_("customer is required"))
	assert_allowed_doctype("Customer")
	if not frappe.has_permission("Customer", "read", customer):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	company = company or get_default_company()
	if not company:
		frappe.throw(_("Company is required"))
	assert_company_read(company)

	from erpnext.selling.doctype.customer.customer import get_credit_limit, get_customer_outstanding
	from frappe.utils import flt

	credit_limit = flt(get_credit_limit(customer, company))
	outstanding = flt(get_customer_outstanding(customer, company))
	projected = outstanding + flt(extra_amount)
	return {
		"credit_limit": credit_limit,
		"outstanding": outstanding,
		"extra_amount": flt(extra_amount),
		"projected": projected,
		"remaining": credit_limit - projected if credit_limit else None,
		"crossed": bool(credit_limit and projected > credit_limit),
	}


@frappe.whitelist(methods=["POST"])
def preview_taxes_and_totals(doc: dict | str | None = None):
	"""Run ERPNext ``calculate_taxes_and_totals`` on an unsaved doc dict.

	Does not invent tax math — uses AccountsController. Does not save.
	"""
	require_login()
	doc = _parse(doc) or {}
	doctype = doc.get("doctype")
	if not doctype or doctype not in _TXN_DOCTYPES:
		frappe.throw(_("doctype must be a sales or purchase transaction"))
	assert_allowed_doctype(doctype)
	if not frappe.has_permission(doctype, "create") and not frappe.has_permission(doctype, "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	assert_company_read(doc.get("company"))

	# Ephemeral doc — never insert.
	preview = frappe.get_doc(doc)
	if preview.meta.has_field("taxes_and_charges") and preview.get("taxes_and_charges"):
		if not preview.get("taxes"):
			from erpnext.controllers.accounts_controller import (
				get_taxes_and_charges as erp_get_taxes_and_charges,
			)

			rows = erp_get_taxes_and_charges(_tax_master_doctype(doctype), preview.taxes_and_charges)
			for row in rows or []:
				preview.append("taxes", row)

	if hasattr(preview, "set_missing_values"):
		try:
			preview.set_missing_values(for_validate=True)
		except Exception as exc:
			# Draft previews often miss warehouse/account defaults; still show totals.
			frappe.logger("taxmate.api.accounts").debug("preview set_missing_values skipped: %s", exc)

	preview.flags.ignore_permissions = True
	preview.calculate_taxes_and_totals()

	return {
		"total": preview.get("total"),
		"net_total": preview.get("net_total"),
		"discount_amount": preview.get("discount_amount"),
		"additional_discount_percentage": preview.get("additional_discount_percentage"),
		"apply_discount_on": preview.get("apply_discount_on"),
		"total_taxes_and_charges": preview.get("total_taxes_and_charges"),
		"grand_total": preview.get("grand_total"),
		"rounded_total": preview.get("rounded_total"),
		"base_net_total": preview.get("base_net_total"),
		"base_grand_total": preview.get("base_grand_total"),
		"taxes": [_as_data(t) for t in (preview.get("taxes") or [])],
		"items": [
			{
				"idx": t.get("idx"),
				"item_code": t.get("item_code"),
				"qty": t.get("qty"),
				"rate": t.get("rate"),
				"amount": t.get("amount"),
				"net_amount": t.get("net_amount"),
			}
			for t in (preview.get("items") or [])
		],
	}


@frappe.whitelist(methods=["POST"])
def make_sales_return(source_name: str):
	require_login()
	assert_allowed_doctype("Sales Invoice")
	doc = frappe.get_doc("Sales Invoice", source_name)
	doc.check_permission("read")
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as erp_make

	return _as_data(erp_make(source_name))


@frappe.whitelist(methods=["POST"])
def make_purchase_return(source_name: str):
	require_login()
	assert_allowed_doctype("Purchase Invoice")
	doc = frappe.get_doc("Purchase Invoice", source_name)
	doc.check_permission("read")
	from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note

	return _as_data(make_debit_note(source_name))


@frappe.whitelist()
def resolve_payment_accounts(
	company: str, payment_type: str, mode_of_payment: str, party_type: str, party: str
):
	"""Both legs of a Payment Entry, without the user ever seeing an account.

	The Payment Entry controller never reads ``mode_of_payment`` -- ``paid_from``
	and ``paid_to`` are mandatory and nothing server-side fills them, so the
	client has to send them. In Desk that resolution is client-side
	(payment_entry.js:472). This does it on the server instead, so the
	Receive -> paid_to / Pay -> paid_from mapping lives in one place.

	It also closes two gaps in the underlying ERPNext helpers:

	* ``get_default_bank_cash_account`` has no permission check and accepts any
	  company, so a user could read another company's default bank account.
	  ``assert_company_read`` fixes that.
	* the same helper computes an account balance by default. The form does not
	  need it, so ``fetch_balance=False`` keeps it off the wire.
	"""
	require_login()
	if payment_type not in ("Receive", "Pay"):
		frappe.throw(_("Payment Type must be Receive or Pay"))
	assert_allowed_doctype("Payment Entry")
	assert_allowed_doctype(party_type)
	assert_company_read(company)
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
	from erpnext.accounts.doctype.payment_entry.payment_entry import (
		get_party_details as pe_party_details,
	)

	# Party leg. This helper does its own has_permission on the party.
	party_details = pe_party_details(company, party_type, party, frappe.utils.today())

	# Bank / cash leg.
	bank = get_default_bank_cash_account(company, mode_of_payment=mode_of_payment, fetch_balance=False) or {}
	bank_account = bank.get("account")
	if not bank_account:
		frappe.throw(
			_("Set a default account for Mode of Payment {0} in company {1}.").format(
				mode_of_payment, company
			),
			title=_("Mode of Payment"),
		)

	bank_leg = "paid_to" if payment_type == "Receive" else "paid_from"
	party_leg = "paid_from" if payment_type == "Receive" else "paid_to"

	return {
		bank_leg: bank_account,
		party_leg: party_details.get("party_account"),
		f"{bank_leg}_account_currency": bank.get("account_currency"),
		f"{party_leg}_account_currency": party_details.get("party_account_currency"),
		# What decides whether Reference No. is mandatory
		# (payment_entry.py:1248) -- the UI mirrors that rule.
		"bank_account_type": bank.get("account_type"),
		"party_name": party_details.get("party_name"),
	}


@frappe.whitelist()
def get_je_account_details(
	account: str,
	date: str,
	company: str,
	debit: str | None = None,
	credit: str | None = None,
	exchange_rate: str | None = None,
) -> dict:
	"""Account type, currency, party type and exchange rate for a JE line.

	Wraps erpnext journal_entry.get_account_details_and_party_type after
	permission + company checks.
	"""
	require_login()
	assert_allowed_doctype("Account")
	assert_allowed_doctype("Journal Entry")
	assert_company_read(company)
	if not frappe.has_permission("Account", "read", account):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.doctype.journal_entry.journal_entry import (
		get_account_details_and_party_type,
	)

	return (
		get_account_details_and_party_type(
			account=account,
			date=date,
			company=company,
			debit=debit,
			credit=credit,
			exchange_rate=exchange_rate,
		)
		or {}
	)


@frappe.whitelist()
def get_je_party_account(company: str, party_type: str, party: str) -> dict:
	"""Party account and currency for a JE line.

	Wraps erpnext.accounts.party.get_party_account with
	permission + company checks.  Returns {account, account_currency}.
	"""
	require_login()
	assert_allowed_doctype(party_type)
	assert_allowed_doctype("Journal Entry")
	assert_company_read(company)
	if not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.party import get_party_account

	account = get_party_account(party_type, party, company)
	currency = None
	if account:
		currency = frappe.db.get_value("Account", account, "account_currency")
	return {"account": account, "account_currency": currency}


@frappe.whitelist()
def get_accounting_dimensions() -> list:
	"""Configured Accounting Dimensions (excluding Cost Center and Project).

	Wraps erpnext accounting_dimension.get_dimensions.
	Returns list of {fieldname, label, document_type, mandatory_for_bs, mandatory_for_pl}.
	Empty list when no dimensions are configured.
	"""
	require_login()
	try:
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			get_dimensions,
		)

		result = get_dimensions() or ([], [])
		dims = result[0] if isinstance(result, (list, tuple)) and len(result) >= 1 else []
		return [
			{
				"fieldname": d.get("fieldname"),
				"label": d.get("label") or d.get("document_type") or d.get("fieldname"),
				"document_type": d.get("document_type"),
				"mandatory_for_bs": bool(d.get("mandatory_for_bs")),
				"mandatory_for_pl": bool(d.get("mandatory_for_pl")),
			}
			for d in (dims or [])
		]
	except Exception:
		return []


@frappe.whitelist()
def resolve_internal_transfer_accounts(company: str, mode_of_payment: str) -> dict:
	"""Both cash/bank legs for an Internal Transfer Payment Entry.

	Internal Transfer moves money between two company accounts (e.g. petty cash
	to bank). Both paid_from and paid_to are bank/cash accounts resolved from
	the Mode of Payment rather than a party account.
	"""
	require_login()
	assert_allowed_doctype("Payment Entry")
	assert_company_read(company)
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account

	bank = get_default_bank_cash_account(company, mode_of_payment=mode_of_payment, fetch_balance=False) or {}
	bank_account = bank.get("account")
	if not bank_account:
		frappe.throw(
			_("Set a default account for Mode of Payment {0} in company {1}.").format(
				mode_of_payment, company
			),
			title=_("Mode of Payment"),
		)
	return {
		"paid_from": bank_account,
		"paid_to": bank_account,
		"paid_from_account_currency": bank.get("account_currency"),
		"paid_to_account_currency": bank.get("account_currency"),
		"bank_account_type": bank.get("account_type"),
	}
