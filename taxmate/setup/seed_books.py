"""Seed Ascra Technology LLP books for TaxMate SPA review.

Creates masters and submitted sales, purchases, fulfilment, and payments.
Names avoid DEMO/E2E/TEST prefixes. Idempotent per company: skips when the
company already has a seeded customer marker.

Run:
  bench --site <site> execute taxmate.setup.seed_books.run

Do not store login passwords in this module.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

import frappe
from frappe.utils import add_days, getdate

from taxmate.uae.constants import UAE_COUNTRY
from taxmate.uae.setup import ensure_company_uae_ready

COMPANY_NAME = "Ascra Technology LLP"
COMPANY_ABBR = "ATL"
COMPANY_TRN = "100312345678901"
SEED_MARKER_CUSTOMER = "Palm Grove Retail LLC"

CUSTOMERS: list[dict] = [
	{"name": "Palm Grove Retail LLC", "trn": "100312459800003", "emirate": "Dubai", "type": "Company"},
	{"name": "Al Noor Facilities FZ-LLC", "trn": "100398761200003", "emirate": "Dubai", "type": "Company"},
	{"name": "Gulf Ledger Advisory LLC", "trn": "100276543100003", "emirate": "Abu Dhabi", "type": "Company"},
	{"name": "Marina Office Fitout LLC", "trn": "100455667700003", "emirate": "Dubai", "type": "Company"},
	{"name": "Shams Procurement Co. LLC", "trn": "100188992200003", "emirate": "Sharjah", "type": "Company"},
	{
		"name": "Barakah Clinics Group LLC",
		"trn": "100533441100003",
		"emirate": "Abu Dhabi",
		"type": "Company",
	},
	{"name": "Horizon Properties LLC", "trn": "100622778800003", "emirate": "Dubai", "type": "Company"},
	{"name": "Saqr Logistics LLC", "trn": "100711223300003", "emirate": "Ajman", "type": "Company"},
	{"name": "Quay Hospitality LLC", "trn": "100844556600003", "emirate": "Dubai", "type": "Company"},
	{"name": "Falcon IT Services LLC", "trn": "100955667700003", "emirate": "Dubai", "type": "Company"},
	{"name": "Walk-in Customer", "trn": None, "emirate": "Dubai", "type": "Individual"},
	{
		"name": "Nordic Tax Partners AB",
		"trn": None,
		"emirate": "Dubai",
		"type": "Company",
		"territory": "Rest Of The World",
	},
]

SUPPLIERS: list[dict] = [
	{"name": "Desert Supplies LLC", "trn": "100167889900003", "group": "Local", "country": UAE_COUNTRY},
	{
		"name": "Emirates Office Systems LLC",
		"trn": "100278991100003",
		"group": "Local",
		"country": UAE_COUNTRY,
	},
	{"name": "Jebel Ali Packaging LLC", "trn": "100389112200003", "group": "Local", "country": UAE_COUNTRY},
	{"name": "Al Ain Print & Paper LLC", "trn": "100490223300003", "group": "Local", "country": UAE_COUNTRY},
	{"name": "Shenzhen Office Hardware Ltd", "trn": None, "group": "Distributor", "country": "China"},
	{"name": "Guangzhou Furnishings Co Ltd", "trn": None, "group": "Distributor", "country": "China"},
	{"name": "Karachi Textile Exports", "trn": None, "group": "Distributor", "country": "Pakistan"},
	{"name": "Utilities - DEWA", "trn": "100100200300003", "group": "Services", "country": UAE_COUNTRY},
]

ITEMS: list[dict] = [
	{
		"code": "CHR-ERG-01",
		"name": "Ergonomic Mesh Office Chair",
		"group": "Products",
		"stock": 1,
		"rate": 685,
		"buy": 410,
		"uom": "Nos",
	},
	{
		"code": "DSK-STD-01",
		"name": "Height-Adjustable Desk 140cm",
		"group": "Products",
		"stock": 1,
		"rate": 1450,
		"buy": 920,
		"uom": "Nos",
	},
	{
		"code": "MON-27-01",
		"name": "27-inch IPS Monitor",
		"group": "Products",
		"stock": 1,
		"rate": 980,
		"buy": 640,
		"uom": "Nos",
	},
	{
		"code": "KB-MEC-01",
		"name": "Mechanical Keyboard",
		"group": "Products",
		"stock": 1,
		"rate": 320,
		"buy": 185,
		"uom": "Nos",
	},
	{
		"code": "MSE-WL-01",
		"name": "Wireless Mouse",
		"group": "Products",
		"stock": 1,
		"rate": 95,
		"buy": 48,
		"uom": "Nos",
	},
	{
		"code": "LMP-LED-01",
		"name": "LED Desk Lamp",
		"group": "Products",
		"stock": 1,
		"rate": 145,
		"buy": 72,
		"uom": "Nos",
	},
	{
		"code": "FIL-A4-01",
		"name": "A4 Filing Cabinet 4-Drawer",
		"group": "Products",
		"stock": 1,
		"rate": 890,
		"buy": 540,
		"uom": "Nos",
	},
	{
		"code": "WST-BIN-01",
		"name": "Office Waste Bin Set",
		"group": "Consumable",
		"stock": 1,
		"rate": 65,
		"buy": 28,
		"uom": "Nos",
	},
	{
		"code": "PAP-A4-01",
		"name": "A4 Copy Paper (5 Reams)",
		"group": "Consumable",
		"stock": 1,
		"rate": 78,
		"buy": 42,
		"uom": "Nos",
	},
	{
		"code": "CBL-USB-01",
		"name": "USB-C Hub 7-in-1",
		"group": "Products",
		"stock": 1,
		"rate": 210,
		"buy": 115,
		"uom": "Nos",
	},
	{
		"code": "SVC-VAT-ADVISORY",
		"name": "VAT Advisory Retainer (Monthly)",
		"group": "Services",
		"stock": 0,
		"rate": 4500,
		"buy": 0,
		"uom": "Nos",
		"sac": "998311",
	},
	{
		"code": "SVC-BOOKKEEP",
		"name": "Bookkeeping Package",
		"group": "Services",
		"stock": 0,
		"rate": 2800,
		"buy": 0,
		"uom": "Nos",
		"sac": "998311",
	},
	{
		"code": "SVC-PAYROLL",
		"name": "Payroll Processing",
		"group": "Services",
		"stock": 0,
		"rate": 1600,
		"buy": 0,
		"uom": "Nos",
		"sac": "998311",
	},
	{
		"code": "SVC-IMPL",
		"name": "ERP Implementation Day Rate",
		"group": "Services",
		"stock": 0,
		"rate": 2200,
		"buy": 0,
		"uom": "Nos",
		"sac": "998314",
	},
	{
		"code": "SVC-TRAIN",
		"name": "Staff Training Workshop",
		"group": "Services",
		"stock": 0,
		"rate": 3500,
		"buy": 0,
		"uom": "Nos",
		"sac": "999293",
	},
	{
		"code": "SVC-ZERO-EXP",
		"name": "Cross-border Advisory (Export)",
		"group": "Services",
		"stock": 0,
		"rate": 5000,
		"buy": 0,
		"uom": "Nos",
		"sac": "998311",
		"zero": 1,
	},
	{
		"code": "SVC-EXEMPT-EDU",
		"name": "Exempt Education Advisory",
		"group": "Services",
		"stock": 0,
		"rate": 1800,
		"buy": 0,
		"uom": "Nos",
		"sac": "999293",
		"exempt": 1,
	},
]

STOCK_PREFIXES = ("CHR", "DSK", "MON", "KB", "MSE", "LMP", "FIL", "WST", "PAP", "CBL")


def run(force: bool | int | str = False) -> dict:
	"""Create company (if missing) and seed books. Returns counts.

	With force=False, still fills missing trading pipelines (SO/PO/DN/PR/…)
	when invoices already exist from an earlier seed.
	"""
	force = bool(force) if not isinstance(force, str) else force.lower() in ("1", "true", "yes")
	frappe.flags.in_import = True
	frappe.set_user("Administrator")

	_ensure_fiscal_year()
	company = _ensure_company()
	ensure_company_uae_ready(company)
	frappe.db.commit()

	abbr = frappe.db.get_value("Company", company, "abbr")
	ctx = _context(company, abbr)

	_ensure_bank(ctx)
	_ensure_customers()
	_ensure_suppliers()
	_ensure_items(ctx)
	frappe.db.commit()

	_receive_opening_stock(ctx)
	frappe.db.commit()

	already = (
		not force
		and frappe.db.exists("Customer", SEED_MARKER_CUSTOMER)
		and frappe.db.count("Sales Invoice", {"company": company, "docstatus": 1}) >= 20
	)

	sales = purchases = payments = 0
	if not already:
		sales = _seed_sales(ctx)
		purchases = _seed_purchases(ctx)
		payments = _seed_payments(ctx)
		frappe.db.commit()

	# Always top up the full trading chain (quotations → orders → fulfilment).
	pipeline = _seed_trading_pipelines(ctx)
	journals = _seed_journals(ctx)
	_ensure_spa_users(ctx)
	pos_profile = _ensure_pos_next(ctx)
	_ensure_legacy_prove_aliases()
	if frappe.db.exists("Item", "DEMO-VAT-CONSULTING"):
		frappe.db.set_value("Item", "DEMO-VAT-CONSULTING", "disabled", 1)
	frappe.db.commit()
	frappe.clear_cache()

	return {
		"company": company,
		"customers": frappe.db.count("Customer"),
		"suppliers": frappe.db.count("Supplier"),
		"items": frappe.db.count("Item", {"disabled": 0}),
		"sales_invoices": sales or frappe.db.count("Sales Invoice", {"company": company, "docstatus": 1}),
		"purchase_invoices": purchases
		or frappe.db.count("Purchase Invoice", {"company": company, "docstatus": 1}),
		"payment_entries": payments or frappe.db.count("Payment Entry", {"company": company, "docstatus": 1}),
		**pipeline,
		"journal_entries": journals,
		"pos_profile": pos_profile,
	}


def _ensure_fiscal_year() -> None:
	if frappe.db.exists("Notification", "Notification for new fiscal year"):
		frappe.db.set_value("Notification", "Notification for new fiscal year", "enabled", 0)
	if not frappe.db.exists("Fiscal Year", "2026"):
		fy = frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": "2026",
				"year_start_date": "2026-01-01",
				"year_end_date": "2026-12-31",
			}
		)
		fy.flags.ignore_permissions = True
		fy.flags.ignore_notifications = True
		fy.insert()
	fy = frappe.get_doc("Fiscal Year", "2026")
	if COMPANY_NAME and not any(r.company == COMPANY_NAME for r in fy.companies):
		if frappe.db.exists("Company", COMPANY_NAME):
			fy.append("companies", {"company": COMPANY_NAME})
			fy.flags.ignore_permissions = True
			fy.flags.ignore_notifications = True
			fy.save()
	frappe.db.set_default("fiscal_year", "2026")


def _ensure_company() -> str:
	if frappe.db.exists("Company", COMPANY_NAME):
		doc = frappe.get_doc("Company", COMPANY_NAME)
		changed = False
		if doc.country != UAE_COUNTRY:
			doc.country = UAE_COUNTRY
			changed = True
		if (doc.tax_id or "") != COMPANY_TRN:
			doc.tax_id = COMPANY_TRN
			changed = True
		if doc.default_currency != "AED":
			doc.default_currency = "AED"
			changed = True
		if changed:
			doc.flags.ignore_permissions = True
			doc.save()
		frappe.db.set_default("company", COMPANY_NAME)
		return COMPANY_NAME

	from erpnext.setup.setup_wizard.operations import install_fixtures as fixtures
	from erpnext.setup.setup_wizard.operations.install_fixtures import install_company, install_defaults

	args = frappe._dict(
		{
			"company_name": COMPANY_NAME,
			"company_abbr": COMPANY_ABBR,
			"currency": "AED",
			"country": UAE_COUNTRY,
			"chart_of_accounts": "Standard",
			"domain": "Distribution",
			"fy_start_date": "2026-01-01",
			"fy_end_date": "2026-12-31",
			"language": "en",
			"timezone": "Asia/Dubai",
		}
	)
	try:
		fixtures.install(UAE_COUNTRY)
	except Exception:
		frappe.log_error(title="TaxMate seed fixtures.install", message=frappe.get_traceback())

	if not frappe.db.exists("Company", COMPANY_NAME):
		install_company(args)
	install_defaults(args)

	company = frappe.get_doc("Company", COMPANY_NAME)
	company.tax_id = COMPANY_TRN
	company.flags.ignore_permissions = True
	company.save()
	frappe.db.set_default("company", COMPANY_NAME)
	frappe.db.set_default("currency", "AED")
	return COMPANY_NAME


def _context(company: str, abbr: str) -> dict:
	wh = frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": "Stores"}, "name")
	if not wh:
		wh = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
	return {
		"company": company,
		"abbr": abbr,
		"warehouse": wh,
		"cost_center": frappe.db.get_value("Company", company, "cost_center"),
		"cash": frappe.db.get_value(
			"Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name"
		),
		"bank_gl": frappe.db.get_value(
			"Account", {"company": company, "account_type": "Bank", "is_group": 0}, "name"
		)
		or frappe.db.get_value(
			"Account",
			{"company": company, "account_name": "Banks Current Accounts", "is_group": 0},
			"name",
		),
		"income": frappe.db.get_value("Company", company, "default_income_account")
		or frappe.db.get_value("Account", {"company": company, "account_name": "Sales Account"}, "name"),
		"cogs": frappe.db.get_value("Company", company, "default_expense_account"),
		"sales_tax": frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": company, "title": "UAE VAT 5%"}, "name"
		)
		or frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": company, "is_default": 1}, "name"
		),
		"sales_tax_zero": frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": company, "title": "UAE VAT Zero"}, "name"
		),
		"sales_tax_exempt": frappe.db.get_value(
			"Sales Taxes and Charges Template", {"company": company, "title": "UAE VAT Exempted"}, "name"
		),
		"purchase_tax": frappe.db.get_value(
			"Purchase Taxes and Charges Template", {"company": company, "title": "UAE VAT 5%"}, "name"
		)
		or frappe.db.get_value(
			"Purchase Taxes and Charges Template", {"company": company, "is_default": 1}, "name"
		),
		"item_tax_5": frappe.db.get_value(
			"Item Tax Template", {"company": company, "title": "UAE VAT 5%"}, "name"
		),
		"item_tax_zero": frappe.db.get_value(
			"Item Tax Template", {"company": company, "title": "UAE VAT Zero"}, "name"
		),
		"item_tax_exempt": frappe.db.get_value(
			"Item Tax Template", {"company": company, "title": "UAE VAT Exempted"}, "name"
		),
	}


def _ensure_bank(ctx: dict) -> None:
	"""Create Emirates NBD bank + leaf GL account (UAE Standard chart only has a Bank group)."""
	if not frappe.db.exists("Bank", "Emirates NBD"):
		frappe.get_doc({"doctype": "Bank", "bank_name": "Emirates NBD"}).insert(ignore_permissions=True)

	bank_gl = ctx.get("bank_gl")
	if not bank_gl:
		parent = frappe.db.get_value(
			"Account",
			{"company": ctx["company"], "account_type": "Bank", "is_group": 1},
			"name",
		)
		leaf_name = f"Banks Current Accounts - {ctx['abbr']}"
		if parent and not frappe.db.exists("Account", leaf_name):
			acc = frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Banks Current Accounts",
					"parent_account": parent,
					"company": ctx["company"],
					"account_type": "Bank",
					"is_group": 0,
					"account_currency": "AED",
				}
			)
			acc.insert(ignore_permissions=True)
			bank_gl = acc.name
		elif frappe.db.exists("Account", leaf_name):
			bank_gl = leaf_name
		ctx["bank_gl"] = bank_gl

	if not bank_gl:
		return
	if frappe.db.exists("Bank Account", {"account_name": "Operating Account", "company": ctx["company"]}):
		return
	frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": "Operating Account",
			"bank": "Emirates NBD",
			"account": bank_gl,
			"is_company_account": 1,
			"company": ctx["company"],
			"is_default": 1,
		}
	).insert(ignore_permissions=True)


def _ensure_customers() -> None:
	for row in CUSTOMERS:
		if frappe.db.exists("Customer", row["name"]):
			continue
		territory = row.get("territory") or "United Arab Emirates"
		if not frappe.db.exists("Territory", territory):
			territory = "All Territories"
		cg = "Commercial" if row["type"] == "Company" else "Individual"
		if not frappe.db.exists("Customer Group", cg):
			cg = "All Customer Groups"
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": row["name"],
				"customer_type": row["type"],
				"customer_group": cg,
				"territory": territory,
				"tax_id": row.get("trn"),
				"default_currency": "AED",
			}
		)
		doc.insert(ignore_permissions=True)
		_party_address("Customer", doc.name, row.get("emirate") or "Dubai", row.get("trn"))


def _ensure_suppliers() -> None:
	for row in SUPPLIERS:
		if frappe.db.exists("Supplier", row["name"]):
			continue
		group = row["group"] if frappe.db.exists("Supplier Group", row["group"]) else "All Supplier Groups"
		doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": row["name"],
				"supplier_group": group,
				"supplier_type": "Company",
				"country": row["country"],
				"tax_id": row.get("trn"),
				"default_currency": "AED" if row["country"] == UAE_COUNTRY else "USD",
			}
		)
		doc.insert(ignore_permissions=True)
		if row["country"] == UAE_COUNTRY:
			_party_address("Supplier", doc.name, "Dubai", row.get("trn"))


def _party_address(party_type: str, party: str, emirate: str, trn: str | None) -> None:
	if frappe.db.exists("Address", {"address_title": party, "address_type": "Billing"}):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": party,
			"address_type": "Billing",
			"address_line1": "Office 1204, Business Bay",
			"city": emirate,
			"country": UAE_COUNTRY,
			"pincode": "00000",
			"links": [{"link_doctype": party_type, "link_name": party}],
		}
	)
	if doc.meta.has_field("emirate"):
		doc.emirate = emirate
	if trn and doc.meta.has_field("tax_id"):
		doc.tax_id = trn
	doc.insert(ignore_permissions=True)


def _ensure_brands() -> None:
	for name in ("Ascra Tools", "Gulf Office", "Marina Gear"):
		if not frappe.db.exists("Brand", name):
			frappe.get_doc({"doctype": "Brand", "brand": name}).insert(ignore_permissions=True)


def _ensure_items(ctx: dict) -> None:
	has_company_field = frappe.get_meta("Item").has_field("custom_company")
	for row in ITEMS:
		if frappe.db.exists("Item", row["code"]):
			if has_company_field and ctx.get("company") and not frappe.db.get_value(
				"Item", row["code"], "custom_company"
			):
				frappe.db.set_value("Item", row["code"], "custom_company", ctx["company"])
			continue
		group = row["group"] if frappe.db.exists("Item Group", row["group"]) else "All Item Groups"
		tax_template = (
			ctx["item_tax_zero"]
			if row.get("zero")
			else ctx.get("item_tax_exempt")
			if row.get("exempt")
			else ctx["item_tax_5"]
		)
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": row["code"],
				"item_name": row["name"],
				"item_group": group,
				"stock_uom": row["uom"],
				"is_stock_item": row["stock"],
				"is_sales_item": 1,
				"is_purchase_item": 1,
				"include_item_in_manufacturing": 0,
				"item_defaults": [
					{
						"company": ctx["company"],
						"default_warehouse": ctx["warehouse"] if row["stock"] else None,
						"income_account": ctx["income"],
						"expense_account": ctx["cogs"],
					}
				],
			}
		)
		if doc.meta.has_field("custom_company") and ctx.get("company"):
			doc.custom_company = ctx["company"]
		if doc.meta.has_field("uae_item_type"):
			doc.uae_item_type = "Goods" if row["stock"] else "Service"
		if row.get("sac") and doc.meta.has_field("sac_code"):
			doc.sac_code = row["sac"]
		if row.get("zero") and doc.meta.has_field("is_zero_rated"):
			doc.is_zero_rated = 1
		if tax_template:
			doc.append("taxes", {"item_tax_template": tax_template, "tax_category": ""})
		doc.insert(ignore_permissions=True)

		if row["rate"]:
			_item_price(row["code"], "Standard Selling", row["rate"])
		if row["buy"]:
			_item_price(row["code"], "Standard Buying", row["buy"])


def _item_price(item: str, price_list: str, rate: float) -> None:
	if not frappe.db.exists("Price List", price_list):
		return
	if frappe.db.exists("Item Price", {"item_code": item, "price_list": price_list}):
		return
	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item,
			"price_list": price_list,
			"price_list_rate": rate,
			"currency": "AED",
		}
	).insert(ignore_permissions=True)


def _ensure_legacy_prove_aliases() -> None:
	"""Prove-it tests still look for DEMO-VAT-CONSULTING on Tax Mate."""
	if frappe.db.exists("Item", "DEMO-VAT-CONSULTING") or not frappe.db.exists("Item", "SVC-VAT-ADVISORY"):
		return
	src = frappe.get_doc("Item", "SVC-VAT-ADVISORY")
	doc = frappe.copy_doc(src)
	doc.item_code = "DEMO-VAT-CONSULTING"
	doc.item_name = "VAT Advisory Retainer (Monthly)"
	doc.insert(ignore_permissions=True)


def _receive_opening_stock(ctx: dict) -> None:
	if not ctx["warehouse"]:
		return
	stock_items = [i for i in ITEMS if i["stock"]]
	if frappe.db.exists("Stock Ledger Entry", {"item_code": stock_items[0]["code"], "is_cancelled": 0}):
		return

	rows = [
		{
			"item_code": item["code"],
			"qty": 250,
			"basic_rate": item["buy"] or 50,
			"t_warehouse": ctx["warehouse"],
			"uom": item["uom"],
			"conversion_factor": 1,
			"transfer_qty": 250,
		}
		for item in stock_items
	]
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": ctx["company"],
			"posting_date": "2026-01-02",
			"posting_time": "10:00:00",
			"set_posting_time": 1,
			"items": rows,
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()


def _months() -> list[date]:
	today = getdate(frappe.utils.today())
	end = min(today, getdate("2026-09-23"))
	out: list[date] = []
	month = 1
	while date(2026, month, 1) <= end:
		out.append(date(2026, month, 1))
		month += 1
		if month > 12:
			break
	return out


def _is_stock_line(item_code: str) -> bool:
	return item_code.split("-", 1)[0] in STOCK_PREFIXES or any(
		item_code.startswith(p) for p in STOCK_PREFIXES
	)


def _seed_sales(ctx: dict) -> int:
	customers = [c["name"] for c in CUSTOMERS if c["name"] != "Walk-in Customer"]
	stock = [i for i in ITEMS if i["stock"]]
	services = [i for i in ITEMS if not i["stock"] and not i.get("zero") and not i.get("exempt")]
	created = 0

	for mi, month_start in enumerate(_months()):
		_, last = monthrange(month_start.year, month_start.month)
		for n in range(5 + (mi % 3)):
			day = 3 + (n * 4) % max(last - 2, 1)
			posting = date(month_start.year, month_start.month, min(day, last))
			customer = customers[(mi * 7 + n) % len(customers)]

			if n % 5 == 0:
				item = services[n % len(services)]
				lines = [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}]
				tax = ctx["sales_tax"]
				update_stock = 0
			elif n % 5 == 1 and ctx["sales_tax_zero"]:
				item = next(i for i in ITEMS if i.get("zero"))
				lines = [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}]
				tax = ctx["sales_tax_zero"]
				customer = "Nordic Tax Partners AB"
				update_stock = 0
			elif n % 5 == 2 and ctx.get("sales_tax_exempt"):
				item = next(i for i in ITEMS if i.get("exempt"))
				lines = [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}]
				tax = ctx["sales_tax_exempt"]
				update_stock = 0
			else:
				a = stock[(mi + n) % len(stock)]
				b = stock[(mi + n + 3) % len(stock)]
				lines = [
					{"item_code": a["code"], "qty": 2 + (n % 3), "rate": a["rate"]},
					{"item_code": b["code"], "qty": 1 + (n % 2), "rate": b["rate"]},
				]
				tax = ctx["sales_tax"]
				update_stock = 1

			if _invoice_exists("Sales Invoice", ctx["company"], posting, customer):
				continue

			doc = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"company": ctx["company"],
					"customer": customer,
					"posting_date": posting.isoformat(),
					"due_date": add_days(posting, 30).isoformat(),
					"set_posting_time": 1,
					"currency": "AED",
					"conversion_rate": 1,
					"selling_price_list": "Standard Selling",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"update_stock": update_stock,
					"set_warehouse": ctx["warehouse"] if update_stock else None,
					"taxes_and_charges": tax,
					"items": lines,
				}
			)
			if doc.meta.has_field("vat_emirate"):
				doc.vat_emirate = next(
					(c["emirate"] for c in CUSTOMERS if c["name"] == customer and c.get("emirate")),
					"Dubai",
				)
			try:
				doc.insert(ignore_permissions=True)
				doc.submit()
				created += 1
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title=f"seed SI {posting} {customer}", message=frappe.get_traceback())
	return created


def _seed_purchases(ctx: dict) -> int:
	local = [s["name"] for s in SUPPLIERS if s["country"] == UAE_COUNTRY and "DEWA" not in s["name"]]
	stock = [i for i in ITEMS if i["stock"]]
	created = 0

	for mi, month_start in enumerate(_months()):
		_, last = monthrange(month_start.year, month_start.month)
		for n in range(3 + (mi % 2)):
			day = 5 + (n * 7) % max(last - 3, 1)
			posting = date(month_start.year, month_start.month, min(day, last))
			supplier = local[(mi + n) % len(local)]
			item = stock[(mi + n * 2) % len(stock)]
			if _invoice_exists("Purchase Invoice", ctx["company"], posting, supplier):
				continue
			bill_no = f"SUP-{month_start.month:02d}-{n + 1:02d}-{mi}"
			doc = frappe.get_doc(
				{
					"doctype": "Purchase Invoice",
					"company": ctx["company"],
					"supplier": supplier,
					"posting_date": posting.isoformat(),
					"due_date": add_days(posting, 21).isoformat(),
					"bill_no": bill_no,
					"bill_date": posting.isoformat(),
					"set_posting_time": 1,
					"currency": "AED",
					"conversion_rate": 1,
					"buying_price_list": "Standard Buying",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"update_stock": 1,
					"set_warehouse": ctx["warehouse"],
					"taxes_and_charges": ctx["purchase_tax"],
					"items": [
						{
							"item_code": item["code"],
							"qty": 8 + n * 2,
							"rate": item["buy"],
							"warehouse": ctx["warehouse"],
						}
					],
				}
			)
			try:
				doc.insert(ignore_permissions=True)
				doc.submit()
				created += 1
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title=f"seed PI {bill_no}", message=frappe.get_traceback())

		util_day = date(month_start.year, month_start.month, min(28, last))
		if not _invoice_exists("Purchase Invoice", ctx["company"], util_day, "Utilities - DEWA"):
			try:
				doc = frappe.get_doc(
					{
						"doctype": "Purchase Invoice",
						"company": ctx["company"],
						"supplier": "Utilities - DEWA",
						"posting_date": util_day.isoformat(),
						"due_date": util_day.isoformat(),
						"bill_no": f"DEWA-{month_start.month:02d}-2026",
						"bill_date": util_day.isoformat(),
						"set_posting_time": 1,
						"currency": "AED",
						"conversion_rate": 1,
						"update_stock": 0,
						"taxes_and_charges": ctx["purchase_tax"],
						"items": [{"item_code": "PAP-A4-01", "qty": 1, "rate": 850 + mi * 40}],
					}
				)
				doc.insert(ignore_permissions=True)
				doc.submit()
				created += 1
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title="seed DEWA", message=frappe.get_traceback())
	return created


def _invoice_exists(doctype: str, company: str, posting: date, party: str) -> bool:
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	return bool(
		frappe.db.exists(
			doctype,
			{
				party_field: party,
				"company": company,
				"posting_date": posting.isoformat(),
				"docstatus": ["<", 2],
			},
		)
	)


def _seed_payments(ctx: dict) -> int:
	created = 0
	# Cash + Cash GL is reliable on a fresh UAE chart (Wire Transfer often has no mop account).
	mode = "Cash" if frappe.db.exists("Mode of Payment", "Cash") else "Wire Transfer"
	paid_account = ctx["cash"] or ctx["bank_gl"]
	if not paid_account:
		return 0

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	for doctype in ("Sales Invoice", "Purchase Invoice"):
		rows = frappe.get_all(
			doctype,
			filters={
				"company": ctx["company"],
				"docstatus": 1,
				"outstanding_amount": [">", 0.01],
				"is_return": 0,
			},
			fields=["name", "posting_date"],
			order_by="posting_date asc",
			limit_page_length=80,
		)
		for i, row in enumerate(rows):
			if i % 3 == 0:
				continue
			try:
				pe = get_payment_entry(doctype, row.name)
				pe.posting_date = add_days(row.posting_date, 7)
				pe.mode_of_payment = mode
				if doctype == "Sales Invoice":
					pe.paid_to = paid_account
				else:
					pe.paid_from = paid_account
				pe.reference_no = f"TRX-{row.name[-6:]}"
				pe.reference_date = pe.posting_date
				pe.insert(ignore_permissions=True)
				pe.submit()
				created += 1
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title=f"seed PE {row.name}", message=frappe.get_traceback())
	return created


def _seed_trading_pipelines(ctx: dict) -> dict:
	"""Quotations, orders, delivery notes, receipts, material / supplier quotes."""
	# Extra stock before fulfilment so DN/PR do not fail valuation.
	_top_up_stock(ctx)
	out = {
		"quotations": _seed_quotations(ctx),
		"sales_orders": _seed_sales_orders(ctx),
		"delivery_notes": _seed_delivery_notes(ctx),
		"supplier_quotations": _seed_supplier_quotations(ctx),
		"material_requests": _seed_material_requests(ctx),
		"purchase_orders": _seed_purchase_orders(ctx),
		"purchase_receipts": _seed_purchase_receipts(ctx),
	}
	out["invoices_from_dn"] = _seed_invoices_from_delivery_notes(ctx)
	out["invoices_from_pr"] = _seed_invoices_from_purchase_receipts(ctx)
	out["sales_returns"] = _seed_sales_returns(ctx)
	out["purchase_returns"] = _seed_purchase_returns(ctx)
	out["draft_invoices"] = _seed_draft_invoices(ctx)
	return out


def _seed_sales_returns(ctx: dict) -> int:
	"""One credit note against a submitted SI."""
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	if frappe.db.exists("Sales Invoice", {"company": ctx["company"], "is_return": 1, "docstatus": 1}):
		return 0
	src = frappe.db.get_value(
		"Sales Invoice",
		{"company": ctx["company"], "docstatus": 1, "is_return": 0},
		"name",
		order_by="posting_date desc",
	)
	if not src:
		return 0
	try:
		ret = make_sales_return(src)
		if ret.meta.has_field("uae_credit_note_reason"):
			ret.uae_credit_note_reason = "GOODS_OR_SERVICES_RETURNED"
		ret.insert(ignore_permissions=True)
		ret.submit()
		return 1
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="seed sales return", message=frappe.get_traceback())
		return 0


def _seed_purchase_returns(ctx: dict) -> int:
	"""One debit note against a submitted PI."""
	from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note

	if frappe.db.exists("Purchase Invoice", {"company": ctx["company"], "is_return": 1, "docstatus": 1}):
		return 0
	src = frappe.db.get_value(
		"Purchase Invoice",
		{"company": ctx["company"], "docstatus": 1, "is_return": 0},
		"name",
		order_by="posting_date desc",
	)
	if not src:
		return 0
	try:
		ret = make_debit_note(src)
		if ret.meta.has_field("uae_credit_note_reason"):
			ret.uae_credit_note_reason = "GOODS_OR_SERVICES_RETURNED"
		ret.insert(ignore_permissions=True)
		ret.submit()
		return 1
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="seed purchase return", message=frappe.get_traceback())
		return 0


def _seed_draft_invoices(ctx: dict) -> int:
	"""Leave a couple of draft SI/PI for list/filter coverage."""
	created = 0
	if not frappe.db.exists("Sales Invoice", {"company": ctx["company"], "docstatus": 0, "is_return": 0}):
		cust = CUSTOMERS[0]["name"]
		item = next(i for i in ITEMS if not i["stock"])
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": ctx["company"],
				"customer": cust,
				"posting_date": frappe.utils.today(),
				"due_date": add_days(frappe.utils.today(), 14),
				"currency": "AED",
				"taxes_and_charges": ctx["sales_tax"],
				"items": [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}],
			}
		)
		try:
			doc.insert(ignore_permissions=True)
			created += 1
		except Exception:
			frappe.db.rollback()
	if not frappe.db.exists("Purchase Invoice", {"company": ctx["company"], "docstatus": 0, "is_return": 0}):
		sup = SUPPLIERS[0]["name"]
		item = next(i for i in ITEMS if i["stock"])
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": ctx["company"],
				"supplier": sup,
				"posting_date": frappe.utils.today(),
				"bill_no": "DRAFT-PI-1",
				"bill_date": frappe.utils.today(),
				"currency": "AED",
				"taxes_and_charges": ctx["purchase_tax"],
				"items": [{"item_code": item["code"], "qty": 1, "rate": item["buy"] or 50}],
			}
		)
		try:
			doc.insert(ignore_permissions=True)
			created += 1
		except Exception:
			frappe.db.rollback()
	return created


def _top_up_stock(ctx: dict) -> None:
	"""Material Receipt when any stock item Bin qty is low."""
	if not ctx.get("warehouse"):
		return
	stock_items = [i for i in ITEMS if i["stock"]]
	need = []
	for item in stock_items:
		qty = (
			frappe.db.get_value(
				"Bin", {"item_code": item["code"], "warehouse": ctx["warehouse"]}, "actual_qty"
			)
			or 0
		)
		if float(qty) < 40:
			need.append(item)
	if not need:
		return
	rows = [
		{
			"item_code": item["code"],
			"qty": 120,
			"basic_rate": item["buy"] or 50,
			"t_warehouse": ctx["warehouse"],
			"uom": item["uom"],
			"conversion_factor": 1,
			"transfer_qty": 120,
		}
		for item in need
	]
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": ctx["company"],
			"posting_date": frappe.utils.today(),
			"posting_time": "09:00:00",
			"set_posting_time": 1,
			"items": rows,
		}
	)
	try:
		se.insert(ignore_permissions=True)
		se.submit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="seed stock top-up", message=frappe.get_traceback())


def _seed_invoices_from_delivery_notes(ctx: dict) -> int:
	"""Bill ~half of submitted DNs that are not fully invoiced."""
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	created = 0
	dns = frappe.get_all(
		"Delivery Note",
		filters={"company": ctx["company"], "docstatus": 1, "per_billed": ["<", 99.99], "is_return": 0},
		fields=["name", "customer", "posting_date"],
		order_by="posting_date asc",
		limit_page_length=30,
	)
	for i, dn in enumerate(dns):
		if i % 2 == 1:
			continue
		try:
			si = make_sales_invoice(dn.name)
			if not si.get("items"):
				continue
			si.set_posting_time = 1
			si.posting_date = add_days(dn.posting_date, 2)
			si.posting_time = "10:00:00"
			si.due_date = add_days(si.posting_date, 30)
			if si.meta.has_field("vat_emirate") and not si.get("vat_emirate"):
				si.vat_emirate = _party_emirate(dn.customer)
			si.insert(ignore_permissions=True)
			si.submit()
			frappe.db.commit()
			created += 1
		except Exception:
			try:
				frappe.log_error(title=f"seed SI from DN {dn.name}", message=frappe.get_traceback())
			except Exception:
				pass
			frappe.db.rollback()
	return created


def _seed_invoices_from_purchase_receipts(ctx: dict) -> int:
	"""Bill ~half of submitted PRs."""
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

	created = 0
	prs = frappe.get_all(
		"Purchase Receipt",
		filters={"company": ctx["company"], "docstatus": 1, "per_billed": ["<", 99.99], "is_return": 0},
		fields=["name", "supplier", "posting_date"],
		order_by="posting_date asc",
		limit_page_length=30,
	)
	for i, pr in enumerate(prs):
		if i % 2 == 1:
			continue
		try:
			pi = make_purchase_invoice(pr.name)
			if not pi.get("items"):
				continue
			pi.set_posting_time = 1
			pi.posting_date = add_days(pr.posting_date, 2)
			pi.posting_time = "10:00:00"
			pi.due_date = add_days(pi.posting_date, 21)
			pi.bill_no = f"PRBILL-{pr.name[-6:]}"
			pi.bill_date = pi.posting_date
			pi.insert(ignore_permissions=True)
			pi.submit()
			frappe.db.commit()
			created += 1
		except Exception:
			try:
				frappe.log_error(title=f"seed PI from PR {pr.name}", message=frappe.get_traceback())
			except Exception:
				pass
			frappe.db.rollback()
	return created


def _party_emirate(customer: str) -> str:
	return next((c["emirate"] for c in CUSTOMERS if c["name"] == customer and c.get("emirate")), "Dubai")


def _safe_submit(doc) -> bool:
	try:
		doc.insert(ignore_permissions=True)
		doc.submit()
		frappe.db.commit()
		return True
	except Exception:
		try:
			frappe.log_error(title=f"seed {getattr(doc, 'doctype', '?')}", message=frappe.get_traceback())
		except Exception:
			pass
		frappe.db.rollback()
		return False


def _seed_quotations(ctx: dict) -> int:
	if frappe.db.count("Quotation", {"company": ctx["company"], "docstatus": 1}) >= 18:
		return 0
	customers = [c["name"] for c in CUSTOMERS if c["type"] == "Company" and c.get("trn")]
	stock = [i for i in ITEMS if i["stock"]]
	services = [i for i in ITEMS if not i["stock"] and not i.get("zero")]
	created = 0
	for mi, month_start in enumerate(_months()):
		for n in range(2):
			day = min(4 + n * 10, monthrange(month_start.year, month_start.month)[1])
			txn = date(month_start.year, month_start.month, day)
			customer = customers[(mi + n) % len(customers)]
			if frappe.db.exists(
				"Quotation",
				{
					"company": ctx["company"],
					"party_name": customer,
					"transaction_date": txn.isoformat(),
					"docstatus": ["<", 2],
				},
			):
				continue
			if n % 2 == 0:
				item = services[n % len(services)]
				lines = [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}]
			else:
				a, b = stock[(mi + n) % len(stock)], stock[(mi + n + 2) % len(stock)]
				lines = [
					{"item_code": a["code"], "qty": 3, "rate": a["rate"]},
					{"item_code": b["code"], "qty": 2, "rate": b["rate"]},
				]
			doc = frappe.get_doc(
				{
					"doctype": "Quotation",
					"quotation_to": "Customer",
					"party_name": customer,
					"order_type": "Sales",
					"status": "Draft",
					"transaction_date": txn.isoformat(),
					"valid_till": add_days(txn, 45).isoformat(),
					"company": ctx["company"],
					"currency": "AED",
					"conversion_rate": 1,
					"selling_price_list": "Standard Selling",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"taxes_and_charges": ctx["sales_tax"],
					"items": lines,
				}
			)
			if doc.meta.has_field("vat_emirate"):
				doc.vat_emirate = _party_emirate(customer)
			if _safe_submit(doc):
				created += 1
	# Leave a few open (submitted, not ordered) already covered; add 3 drafts as Open quotes
	for i, customer in enumerate(customers[:3]):
		name_key = f"draft-qtn-{i}"
		if frappe.db.exists("Quotation", {"company": ctx["company"], "party_name": customer, "docstatus": 0}):
			continue
		item = services[i % len(services)]
		doc = frappe.get_doc(
			{
				"doctype": "Quotation",
				"quotation_to": "Customer",
				"party_name": customer,
				"order_type": "Sales",
				"status": "Draft",
				"transaction_date": "2026-09-10",
				"valid_till": "2026-10-31",
				"company": ctx["company"],
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"taxes_and_charges": ctx["sales_tax"],
				"items": [{"item_code": item["code"], "qty": 1, "rate": item["rate"]}],
			}
		)
		if doc.meta.has_field("vat_emirate"):
			doc.vat_emirate = _party_emirate(customer)
		try:
			doc.insert(ignore_permissions=True)
			created += 1
		except Exception:
			frappe.db.rollback()
		_ = name_key
	return created


def _seed_sales_orders(ctx: dict) -> int:
	if frappe.db.count("Sales Order", {"company": ctx["company"], "docstatus": 1}) >= 20:
		return 0
	customers = [c["name"] for c in CUSTOMERS if c["type"] == "Company" and c.get("trn")]
	stock = [i for i in ITEMS if i["stock"]]
	services = [i for i in ITEMS if not i["stock"] and not i.get("zero")]
	created = 0
	for mi, month_start in enumerate(_months()):
		for n in range(3):
			day = min(6 + n * 7, monthrange(month_start.year, month_start.month)[1])
			txn = date(month_start.year, month_start.month, day)
			delivery = add_days(txn, 14)
			customer = customers[(mi * 3 + n) % len(customers)]
			if frappe.db.exists(
				"Sales Order",
				{
					"company": ctx["company"],
					"customer": customer,
					"transaction_date": txn.isoformat(),
					"docstatus": ["<", 2],
				},
			):
				continue
			if n == 0:
				item = services[mi % len(services)]
				lines = [
					{
						"item_code": item["code"],
						"qty": 1,
						"rate": item["rate"],
						"delivery_date": delivery.isoformat(),
					}
				]
			else:
				a = stock[(mi + n) % len(stock)]
				b = stock[(mi + n + 4) % len(stock)]
				lines = [
					{
						"item_code": a["code"],
						"qty": 4 + n,
						"rate": a["rate"],
						"delivery_date": delivery.isoformat(),
					},
					{
						"item_code": b["code"],
						"qty": 2,
						"rate": b["rate"],
						"delivery_date": delivery.isoformat(),
					},
				]
			doc = frappe.get_doc(
				{
					"doctype": "Sales Order",
					"company": ctx["company"],
					"customer": customer,
					"order_type": "Sales",
					"status": "Draft",
					"transaction_date": txn.isoformat(),
					"delivery_date": delivery.isoformat(),
					"currency": "AED",
					"conversion_rate": 1,
					"selling_price_list": "Standard Selling",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"taxes_and_charges": ctx["sales_tax"],
					"items": lines,
				}
			)
			if doc.meta.has_field("vat_emirate"):
				doc.vat_emirate = _party_emirate(customer)
			if _safe_submit(doc):
				created += 1
	return created


def _seed_delivery_notes(ctx: dict) -> int:
	"""Deliver stock lines from open sales orders; also a few standalone DNs."""
	if frappe.db.count("Delivery Note", {"company": ctx["company"], "docstatus": 1}) >= 15:
		return 0
	created = 0
	orders = frappe.get_all(
		"Sales Order",
		filters={
			"company": ctx["company"],
			"docstatus": 1,
			"per_delivered": ["<", 99.99],
			"status": ["!=", "Closed"],
		},
		fields=["name", "customer", "transaction_date"],
		order_by="transaction_date asc",
		limit_page_length=40,
	)
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

	for i, so in enumerate(orders):
		if i % 2 == 1:
			continue  # leave some undelivered for fulfilment dashboards
		try:
			dn = make_delivery_note(so.name)
			if not dn.get("items"):
				continue
			dn.status = "Draft"
			dn.set_posting_time = 1
			dn.posting_date = add_days(so.transaction_date, 5)
			dn.posting_time = "14:00:00"
			dn.set_warehouse = ctx["warehouse"]
			if dn.meta.has_field("vat_emirate") and not dn.vat_emirate:
				dn.vat_emirate = _party_emirate(so.customer)
			dn.insert(ignore_permissions=True)
			dn.submit()
			frappe.db.commit()
			created += 1
		except Exception:
			try:
				frappe.log_error(title=f"seed DN from {so.name}", message=frappe.get_traceback())
			except Exception:
				pass
			frappe.db.rollback()

	# Standalone DNs for walk-up fulfilment
	stock = [i for i in ITEMS if i["stock"]]
	customers = [c["name"] for c in CUSTOMERS if c.get("trn")]
	for mi, month_start in enumerate(_months()[::2]):
		txn = date(
			month_start.year, month_start.month, min(18, monthrange(month_start.year, month_start.month)[1])
		)
		customer = customers[mi % len(customers)]
		item = stock[mi % len(stock)]
		if frappe.db.exists(
			"Delivery Note",
			{
				"company": ctx["company"],
				"customer": customer,
				"posting_date": txn.isoformat(),
				"docstatus": ["<", 2],
			},
		):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"company": ctx["company"],
				"customer": customer,
				"status": "Draft",
				"posting_date": txn.isoformat(),
				"posting_time": "11:00:00",
				"set_posting_time": 1,
				"currency": "AED",
				"conversion_rate": 1,
				"selling_price_list": "Standard Selling",
				"price_list_currency": "AED",
				"plc_conversion_rate": 1,
				"set_warehouse": ctx["warehouse"],
				"taxes_and_charges": ctx["sales_tax"],
				"items": [
					{
						"item_code": item["code"],
						"qty": 2,
						"rate": item["rate"],
						"warehouse": ctx["warehouse"],
					}
				],
			}
		)
		if doc.meta.has_field("vat_emirate"):
			doc.vat_emirate = _party_emirate(customer)
		if _safe_submit(doc):
			created += 1
	return created


def _seed_supplier_quotations(ctx: dict) -> int:
	if frappe.db.count("Supplier Quotation", {"company": ctx["company"], "docstatus": 1}) >= 10:
		return 0
	local = [s["name"] for s in SUPPLIERS if s["country"] == UAE_COUNTRY and "DEWA" not in s["name"]]
	stock = [i for i in ITEMS if i["stock"]]
	created = 0
	for mi, month_start in enumerate(_months()):
		if mi % 2:
			continue
		txn = date(month_start.year, month_start.month, 8)
		supplier = local[mi % len(local)]
		item = stock[mi % len(stock)]
		if frappe.db.exists(
			"Supplier Quotation",
			{
				"company": ctx["company"],
				"supplier": supplier,
				"transaction_date": txn.isoformat(),
				"docstatus": ["<", 2],
			},
		):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"company": ctx["company"],
				"supplier": supplier,
				"status": "Draft",
				"transaction_date": txn.isoformat(),
				"valid_till": add_days(txn, 30).isoformat(),
				"currency": "AED",
				"conversion_rate": 1,
				"buying_price_list": "Standard Buying",
				"taxes_and_charges": ctx["purchase_tax"],
				"items": [{"item_code": item["code"], "qty": 20, "rate": item["buy"]}],
			}
		)
		if _safe_submit(doc):
			created += 1
	return created


def _seed_material_requests(ctx: dict) -> int:
	if frappe.db.count("Material Request", {"company": ctx["company"], "docstatus": 1}) >= 10:
		return 0
	stock = [i for i in ITEMS if i["stock"]]
	created = 0
	for mi, month_start in enumerate(_months()):
		txn = date(month_start.year, month_start.month, 3)
		sched = add_days(txn, 10)
		item = stock[mi % len(stock)]
		if frappe.db.exists(
			"Material Request",
			{"company": ctx["company"], "transaction_date": txn.isoformat(), "docstatus": ["<", 2]},
		):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Material Request",
				"material_request_type": "Purchase",
				"company": ctx["company"],
				"transaction_date": txn.isoformat(),
				"schedule_date": sched.isoformat(),
				"items": [
					{
						"item_code": item["code"],
						"qty": 15 + mi,
						"warehouse": ctx["warehouse"],
						"schedule_date": sched.isoformat(),
					}
				],
			}
		)
		if _safe_submit(doc):
			created += 1
	return created


def _seed_purchase_orders(ctx: dict) -> int:
	if frappe.db.count("Purchase Order", {"company": ctx["company"], "docstatus": 1}) >= 18:
		return 0
	local = [s["name"] for s in SUPPLIERS if s["country"] == UAE_COUNTRY and "DEWA" not in s["name"]]
	stock = [i for i in ITEMS if i["stock"]]
	created = 0
	for mi, month_start in enumerate(_months()):
		for n in range(2):
			day = min(7 + n * 9, monthrange(month_start.year, month_start.month)[1])
			txn = date(month_start.year, month_start.month, day)
			sched = add_days(txn, 12)
			supplier = local[(mi + n) % len(local)]
			item = stock[(mi + n * 2) % len(stock)]
			if frappe.db.exists(
				"Purchase Order",
				{
					"company": ctx["company"],
					"supplier": supplier,
					"transaction_date": txn.isoformat(),
					"docstatus": ["<", 2],
				},
			):
				continue
			doc = frappe.get_doc(
				{
					"doctype": "Purchase Order",
					"company": ctx["company"],
					"supplier": supplier,
					"status": "Draft",
					"transaction_date": txn.isoformat(),
					"schedule_date": sched.isoformat(),
					"currency": "AED",
					"conversion_rate": 1,
					"buying_price_list": "Standard Buying",
					"price_list_currency": "AED",
					"plc_conversion_rate": 1,
					"taxes_and_charges": ctx["purchase_tax"],
					"items": [
						{
							"item_code": item["code"],
							"qty": 12 + n * 3,
							"rate": item["buy"],
							"schedule_date": sched.isoformat(),
							"warehouse": ctx["warehouse"],
						}
					],
				}
			)
			if _safe_submit(doc):
				created += 1
	return created


def _seed_purchase_receipts(ctx: dict) -> int:
	if frappe.db.count("Purchase Receipt", {"company": ctx["company"], "docstatus": 1}) >= 12:
		return 0
	created = 0
	orders = frappe.get_all(
		"Purchase Order",
		filters={
			"company": ctx["company"],
			"docstatus": 1,
			"per_received": ["<", 99.99],
			"status": ["!=", "Closed"],
		},
		fields=["name", "supplier", "transaction_date"],
		order_by="transaction_date asc",
		limit_page_length=40,
	)
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	for i, po in enumerate(orders):
		if i % 2 == 1:
			continue
		try:
			pr = make_purchase_receipt(po.name)
			if not pr.get("items"):
				continue
			pr.status = "Draft"
			pr.set_posting_time = 1
			pr.posting_date = add_days(po.transaction_date, 4)
			pr.posting_time = "12:00:00"
			pr.set_warehouse = ctx["warehouse"]
			pr.insert(ignore_permissions=True)
			pr.submit()
			frappe.db.commit()
			created += 1
		except Exception:
			try:
				frappe.log_error(title=f"seed PR from {po.name}", message=frappe.get_traceback())
			except Exception:
				pass
			frappe.db.rollback()
	return created


def _seed_journals(ctx: dict) -> int:
	if frappe.db.count("Journal Entry", {"company": ctx["company"], "docstatus": 1}) >= 8:
		return 0
	bank = ctx.get("bank_gl") or ctx.get("cash")
	expense = frappe.db.get_value(
		"Account",
		{"company": ctx["company"], "account_type": "Expense Account", "is_group": 0, "disabled": 0},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": ctx["company"], "root_type": "Expense", "is_group": 0, "disabled": 0},
		"name",
	)
	if not bank or not expense:
		return 0
	cc = ctx.get("cost_center")
	created = 0
	for mi, month_start in enumerate(_months()[::2]):
		txn = date(
			month_start.year, month_start.month, min(25, monthrange(month_start.year, month_start.month)[1])
		)
		if frappe.db.exists(
			"Journal Entry",
			{"company": ctx["company"], "posting_date": txn.isoformat(), "docstatus": ["<", 2]},
		):
			continue
		amount = 350 + mi * 25
		line = {"cost_center": cc} if cc else {}
		doc = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": ctx["company"],
				"posting_date": txn.isoformat(),
				"voucher_type": "Journal Entry",
				"user_remark": f"Office supplies accrual {txn.strftime('%b %Y')}",
				"accounts": [
					{
						**line,
						"account": expense,
						"debit_in_account_currency": amount,
						"credit_in_account_currency": 0,
					},
					{
						**line,
						"account": bank,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": amount,
					},
				],
			}
		)
		if _safe_submit(doc):
			created += 1
	return created


def _ensure_spa_users(ctx: dict) -> None:
	"""Ensure SPA users and roles. Passwords are set outside this seed (never stored here)."""
	from taxmate.setup.spa_roles import apply_spa_role, ensure_spa_roles

	ensure_spa_roles()
	try:
		from taxmate.setup.spa_roles import _allow_reports, _ensure_books_perms

		_ensure_books_perms()
		_allow_reports()
	except Exception:
		frappe.log_error(title="TaxMate seed SPA perms")

	users = [
		{"email": "sourav@ascratech.com", "first_name": "Sourav", "last_name": "Ascra", "role": "owner"},
		{"email": "owner@manara.ae", "first_name": "Layla", "last_name": "Al Hashimi", "role": "owner"},
		{"email": "accountant@manara.ae", "first_name": "Omar", "last_name": "Farouk", "role": "accountant"},
	]
	for u in users:
		if not frappe.db.exists("User", u["email"]):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": u["email"],
					"first_name": u["first_name"],
					"last_name": u["last_name"],
					"send_welcome_email": 0,
					"user_type": "System User",
					"enabled": 1,
				}
			)
			user.insert(ignore_permissions=True)
			# Password is assigned by the operator / onboard script, not the seed.
		else:
			frappe.db.set_value("User", u["email"], "enabled", 1)
		apply_spa_role(u["email"], u["role"])
		frappe.defaults.set_user_default("company", ctx["company"], u["email"])


POS_PROFILE_NAME = "Ascra Front Desk"
POS_PROFILE_USERS = ("sourav@ascratech.com", "Administrator")


def _ensure_mop_account(mode_of_payment: str, company: str, default_account: str) -> None:
	"""Attach a company default account to a Mode of Payment (idempotent)."""
	if not frappe.db.exists("Mode of Payment", mode_of_payment):
		return
	if not default_account or not frappe.db.exists("Account", default_account):
		return
	if frappe.db.exists(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
	):
		return
	mop = frappe.get_doc("Mode of Payment", mode_of_payment)
	mop.append("accounts", {"company": company, "default_account": default_account})
	mop.flags.ignore_permissions = True
	mop.save()


def _ensure_pos_cashier_role(user: str) -> None:
	"""Grant POSNext Cashier add-on without stripping TaxMate markers."""
	if not user or user in ("Administrator", "Guest"):
		return
	if not frappe.db.exists("User", user) or not frappe.db.exists("Role", "POSNext Cashier"):
		return
	from taxmate.setup.spa_roles import apply_spa_roles, spa_roles_of

	roles = spa_roles_of(user) or ["owner"]
	apply_spa_roles(user, roles, extra_roles=["POSNext Cashier"])


def _ensure_pos_next(ctx: dict) -> str | None:
	"""Seed a POS Profile so POS Next can open a shift for Ascra cashiers.

	POS Next lists profiles via INNER JOIN on `POS Profile User` for the session
	user — without applicable_for_users the Open Shift dialog stays empty.
	"""
	if not frappe.db.exists("DocType", "POS Profile"):
		return None

	company = ctx["company"]
	abbr = ctx["abbr"]
	warehouse = f"Stores - {abbr}"
	cash_gl = f"Cash - {abbr}"
	sales_gl = f"Sales - {abbr}"
	write_off = f"Write Off - {abbr}"
	cost_center = f"Main - {abbr}"
	tax_template = f"UAE VAT 5% - {abbr}"
	price_list = "Standard Selling"
	customer = "Walk-in Customer"
	bank_gl = ctx.get("bank_gl") or frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Bank", "is_group": 0},
		"name",
	)

	_ensure_mop_account("Cash", company, cash_gl)
	if bank_gl:
		_ensure_mop_account("Credit Card", company, bank_gl)

	for email in POS_PROFILE_USERS:
		if email != "Administrator":
			_ensure_pos_cashier_role(email)

	users = [u for u in POS_PROFILE_USERS if frappe.db.exists("User", u)]
	if not users:
		return None

	for label, doctype, name in (
		("warehouse", "Warehouse", warehouse),
		("write_off_account", "Account", write_off),
		("write_off_cost_center", "Cost Center", cost_center),
		("income_account", "Account", sales_gl),
		("account_for_change_amount", "Account", cash_gl),
	):
		if not frappe.db.exists(doctype, name):
			frappe.log_error(title=f"TaxMate POS seed missing {label}", message=name)
			return None

	payments = [{"mode_of_payment": "Cash", "default": 1}]
	if frappe.db.exists("Mode of Payment", "Credit Card") and frappe.db.exists(
		"Mode of Payment Account", {"parent": "Credit Card", "company": company}
	):
		payments.append({"mode_of_payment": "Credit Card", "default": 0})

	user_rows = [{"user": u, "default": 1 if i == 0 else 0} for i, u in enumerate(users)]

	if frappe.db.exists("POS Profile", POS_PROFILE_NAME):
		doc = frappe.get_doc("POS Profile", POS_PROFILE_NAME)
		doc.disabled = 0
		doc.company = company
		doc.currency = "AED"
		doc.warehouse = warehouse
		doc.selling_price_list = (
			price_list if frappe.db.exists("Price List", price_list) else doc.selling_price_list
		)
		if frappe.db.exists("Customer", customer):
			doc.customer = customer
		doc.write_off_account = write_off
		doc.write_off_cost_center = cost_center
		doc.write_off_limit = doc.write_off_limit or 1
		doc.income_account = sales_gl
		doc.account_for_change_amount = cash_gl
		if frappe.db.exists("Sales Taxes and Charges Template", tax_template):
			doc.taxes_and_charges = tax_template
		existing_users = {row.user for row in doc.applicable_for_users}
		for row in user_rows:
			if row["user"] not in existing_users:
				doc.append("applicable_for_users", row)
		if not doc.payments:
			for pay in payments:
				doc.append("payments", pay)
		doc.flags.ignore_permissions = True
		doc.save()
		return doc.name

	doc = frappe.get_doc(
		{
			"doctype": "POS Profile",
			"name": POS_PROFILE_NAME,
			"company": company,
			"currency": "AED",
			"warehouse": warehouse,
			"selling_price_list": price_list if frappe.db.exists("Price List", price_list) else None,
			"customer": customer if frappe.db.exists("Customer", customer) else None,
			"write_off_account": write_off,
			"write_off_cost_center": cost_center,
			"write_off_limit": 1,
			"income_account": sales_gl,
			"account_for_change_amount": cash_gl,
			"taxes_and_charges": tax_template
			if frappe.db.exists("Sales Taxes and Charges Template", tax_template)
			else None,
			"update_stock": 1,
			"payments": payments,
			"applicable_for_users": user_rows,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name
