"""Owner dashboard — every figure the home screen shows, in one call.

Design: claude/dashboard-scope.md in the TaxMate project.

Rules this module keeps, because each one is a way a dashboard quietly lies:

* **Permission-aware.** Everything reads through ``frappe.get_list``, never
  ``get_all`` (which sets ``ignore_permissions``). A section the user cannot
  read comes back as ``None`` and the screen says so, rather than showing a
  zero that looks like a real figure.
* **Company currency.** Sums use the ``base_*`` columns. A total across mixed
  document currencies is meaningless.
* **Same basis as the ledger.** Profit comes from GL Entry by account
  ``root_type`` — the basis ERPNext's own Profit and Loss Statement uses — so
  the dashboard and the report agree for the same dates and cost center.
* **Like-for-like comparison.** The period runs to *today*, so the previous
  period is cut to the same number of days. Comparing 21 days of September
  with all 31 of August would make every month look like a collapse.
* **Company-wide where the ledger is company-wide.** Bank balances and VAT are
  not split by cost center; they ignore that filter and the payload says so.
* **VAT is read, never recomputed.** The figure is the VAT 201 filing log's
  own ``net_vat_due``. A second calculation here could disagree with the
  return actually filed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, getdate, today

from taxmate.api.resource import assert_company_read, require_login
from taxmate.setup.spa_roles import require_spa_role
from taxmate.utils.company import get_default_company
from taxmate.utils.localize import ledger_label

PERIODS = ("month", "quarter", "year")
AGE_BUCKETS = ("current", "1_30", "31_60", "61_90", "90_plus")
_VAT_LOG = "UAE VAT 201 Filing Log"
_CT_LOG = "UAE CT Filing Log"
_GL_EXCLUDE_VOUCHERS = ["Period Closing Voucher"]


# ── Pure helpers (no database; unit-tested without a site) ─────────────────


def period_bounds(key: str, on: date) -> dict[str, date]:
	"""Current period to date, and the previous period cut to the same length.

	month   — 1st of this month → today;   previous: same days of last month
	quarter — 1st of this quarter → today; previous: same days of last quarter
	year    — the last 12 months → today;  previous: the 12 months before that
	"""
	if key not in PERIODS:
		frappe.throw(_("Period must be one of: {0}").format(", ".join(PERIODS)))

	if key == "month":
		start = on.replace(day=1)
		prev_start = _as_date(add_months(start, -1))
	elif key == "quarter":
		start = date(on.year, ((on.month - 1) // 3) * 3 + 1, 1)
		prev_start = _as_date(add_months(start, -3))
	else:
		start = _as_date(add_months(on.replace(day=1), -11))
		prev_start = _as_date(add_months(start, -12))

	elapsed = (on - start).days
	prev_end = min(prev_start + timedelta(days=elapsed), start - timedelta(days=1))
	return {"start": start, "end": on, "prev_start": prev_start, "prev_end": prev_end}


def month_keys(on: date, n: int = 12) -> list[str]:
	"""The last ``n`` calendar months ending with ``on``'s month, as YYYY-MM."""
	first = on.replace(day=1)
	return [_as_date(add_months(first, -i)).strftime("%Y-%m") for i in range(n - 1, -1, -1)]


def bucket_by_month(rows: list[dict], keys: list[str], date_field: str, value_field: str) -> list[float]:
	"""Fold daily sums into the month buckets named by ``keys``."""
	totals = dict.fromkeys(keys, 0.0)
	for row in rows:
		d = row.get(date_field)
		if not d:
			continue
		k = getdate(d).strftime("%Y-%m")
		if k in totals:
			totals[k] += flt(row.get(value_field))
	return [round(totals[k], 2) for k in keys]


def age_bucket(due: date | None, on: date) -> str:
	"""Which ageing bucket an outstanding amount falls in, by days past due."""
	if not due:
		return "current"
	late = (on - due).days
	if late <= 0:
		return "current"
	if late <= 30:
		return "1_30"
	if late <= 60:
		return "31_60"
	if late <= 90:
		return "61_90"
	return "90_plus"


def prorate(amount: float, start: date, end: date, fy_start: date, fy_end: date) -> float:
	"""The share of an annual budget that falls inside [start, end]."""
	lo, hi = max(start, fy_start), min(end, fy_end)
	if hi < lo:
		return 0.0
	fy_days = (fy_end - fy_start).days + 1
	return flt(amount) * ((hi - lo).days + 1) / fy_days if fy_days else 0.0


def _as_date(value) -> date:
	return getdate(value)


# ── Endpoint ───────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_owner_dashboard(
	period: str = "month",
	cost_center: str | None = None,
	company: str | None = None,
) -> dict[str, Any]:
	require_login()
	# Accountants may open the owner KPI view; owners must not open the
	# accountant books dashboard (gated separately on that endpoint).
	require_spa_role("owner", "accountant")
	company = company or get_default_company()
	if not company:
		frappe.throw(_("Set a default Company to see the dashboard."))
	assert_company_read(company)

	cost_center = cost_center or None
	if cost_center:
		cc_company = frappe.db.get_value("Cost Center", cost_center, "company")
		if cc_company != company:
			frappe.throw(_("Cost Center {0} does not belong to {1}").format(cost_center, company))

	on = getdate(today())
	bounds = period_bounds(period, on)
	months = month_keys(on)
	ctx = _Ctx(company, cost_center, on, bounds, months)

	return {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"today": str(on),
		"period": {
			"key": period,
			"start": str(bounds["start"]),
			"end": str(bounds["end"]),
			"prev_start": str(bounds["prev_start"]),
			"prev_end": str(bounds["prev_end"]),
		},
		"months": months,
		"cost_center": cost_center,
		"cost_centers": ctx.cost_centers(),
		"pnl": ctx.pnl(),
		"flows": ctx.flows(),
		"bank": ctx.bank(),
		"vat": ctx.vat(),
		"ageing": {
			"receivable": ctx.ageing("Sales Invoice"),
			"payable": ctx.ageing("Purchase Invoice"),
		},
		"budget": ctx.budget(),
		"top_customers": ctx.top_customers(),
		"top_expenses": ctx.top_expenses(),
		"overdue_invoices": ctx.overdue_invoices(),
		"bills_due": ctx.bills_due(),
		"deadlines": ctx.deadlines(),
		"readiness": ctx.readiness(),
	}


class _Ctx:
	"""One request's filters, and one method per dashboard section."""

	def __init__(self, company: str, cost_center: str | None, on: date, bounds: dict, months: list[str]):
		self.company = company
		self.cost_center = cost_center
		self.on = on
		self.b = bounds
		self.months = months
		self.series_start = getdate(months[0] + "-01")
		self._accounts: dict[str, list[dict]] | None = None
		default_fb = frappe.get_cached_value("Company", company, "default_finance_book")
		self.finance_books = ["", default_fb] if default_fb else [""]

	# ── filters ──

	def _doc_filters(self, doctype: str, extra: list | None = None) -> list:
		f: list = [["company", "=", self.company], ["docstatus", "=", 1]]
		meta = frappe.get_meta(doctype)
		if self.cost_center and meta.has_field("cost_center"):
			# Inclusive of children, as ERPNext's own reports treat a group cost center.
			f.append(["cost_center", "descendants of (inclusive)", self.cost_center])
		if meta.has_field("is_opening"):
			# Opening invoices carry balances brought forward, not this period's trade.
			f.append(["is_opening", "!=", "Yes"])
		return f + (extra or [])

	def _gl_filters(self, extra: list | None = None, *, company_wide: bool = False) -> list:
		f: list = [
			["company", "=", self.company],
			["is_cancelled", "=", 0],
			["voucher_type", "not in", _GL_EXCLUDE_VOUCHERS],
			# Same finance-book rule as ERPNext's financial statements: the
			# company's default book plus entries with none. Without it, a
			# second book (e.g. tax depreciation) is double-counted.
			["finance_book", "in", self.finance_books],
		]
		if self.cost_center and not company_wide:
			f.append(["cost_center", "descendants of (inclusive)", self.cost_center])
		return f + (extra or [])

	@staticmethod
	def _can(doctype: str) -> bool:
		return bool(frappe.has_permission(doctype, "read"))

	# ── chart of accounts ──

	def _accounts_by_root(self) -> dict[str, list[dict]]:
		if self._accounts is None:
			rows = frappe.get_list(
				"Account",
				filters={"company": self.company, "is_group": 0, "root_type": ["in", ["Income", "Expense"]]},
				fields=["name", "account_name", "root_type", "account_type"],
				limit_page_length=0,
			)
			self._accounts = {"Income": [], "Expense": []}
			for r in rows:
				self._accounts[r.root_type].append(r)
		return self._accounts

	def _gl_sum_by_account(self, accounts: list[str], start: date, end: date) -> dict[str, float]:
		"""Net debit - credit per account over [start, end]."""
		if not accounts:
			return {}
		rows = frappe.get_list(
			"GL Entry",
			filters=self._gl_filters(
				[["account", "in", accounts], ["posting_date", "between", [start, end]]]
			),
			fields=["account", {"SUM": "debit", "as": "dr"}, {"SUM": "credit", "as": "cr"}],
			group_by="account",
			order_by="account",
			limit_page_length=0,
		)
		return {r.account: flt(r.dr) - flt(r.cr) for r in rows}

	def _gl_daily(self, accounts: list[str]) -> list[dict]:
		if not accounts:
			return []
		return frappe.get_list(
			"GL Entry",
			filters=self._gl_filters(
				[["account", "in", accounts], ["posting_date", "between", [self.series_start, self.on]]]
			),
			fields=["posting_date", {"SUM": "debit", "as": "dr"}, {"SUM": "credit", "as": "cr"}],
			group_by="posting_date",
			order_by="posting_date",
			limit_page_length=0,
		)

	# ── sections ──

	def cost_centers(self) -> list[dict]:
		if not self._can("Cost Center"):
			return []
		rows = frappe.get_list(
			"Cost Center",
			filters={"company": self.company, "is_group": 0, "disabled": 0},
			fields=["name", "cost_center_name"],
			order_by="cost_center_name",
			limit_page_length=0,
		)
		return [{"name": r.name, "label": r.cost_center_name or r.name} for r in rows]

	def pnl(self) -> dict | None:
		if not self._can("GL Entry") or not self._can("Account"):
			return None
		acc = self._accounts_by_root()
		inc = [a.name for a in acc["Income"]]
		exp = [a.name for a in acc["Expense"]]
		cogs = {a.name for a in acc["Expense"] if a.account_type == "Cost of Goods Sold"}

		def totals(start: date, end: date) -> dict:
			i = self._gl_sum_by_account(inc, start, end)
			e = self._gl_sum_by_account(exp, start, end)
			return {
				"revenue": round(-sum(i.values()), 2),  # income is credit-normal
				"expenses": round(sum(e.values()), 2),
				"cogs": round(sum(v for k, v in e.items() if k in cogs), 2),
			}

		cur = totals(self.b["start"], self.b["end"])
		prev = totals(self.b["prev_start"], self.b["prev_end"])

		inc_daily = self._gl_daily(inc)
		for r in inc_daily:
			r["v"] = flt(r.cr) - flt(r.dr)
		exp_daily = self._gl_daily(exp)
		for r in exp_daily:
			r["v"] = flt(r.dr) - flt(r.cr)

		return {
			**cur,
			"prev": prev,
			"revenue_by_month": bucket_by_month(inc_daily, self.months, "posting_date", "v"),
			"expenses_by_month": bucket_by_month(exp_daily, self.months, "posting_date", "v"),
		}

	def _flow(self, doctype: str, value_field: str, extra: list | None = None) -> dict | None:
		if not self._can(doctype):
			return None

		def total(start: date, end: date) -> tuple[float, int]:
			rows = frappe.get_list(
				doctype,
				filters=self._doc_filters(
					doctype, (extra or []) + [["posting_date", "between", [start, end]]]
				),
				fields=[{"SUM": value_field, "as": "v"}, {"COUNT": "*", "as": "n"}],
				limit=1,
			)
			return (flt(rows[0].v), cint(rows[0].n)) if rows else (0.0, 0)

		value, count = total(self.b["start"], self.b["end"])
		prev, prev_count = total(self.b["prev_start"], self.b["prev_end"])
		daily = frappe.get_list(
			doctype,
			filters=self._doc_filters(
				doctype, (extra or []) + [["posting_date", "between", [self.series_start, self.on]]]
			),
			fields=["posting_date", {"SUM": value_field, "as": "v"}],
			group_by="posting_date",
			order_by="posting_date",
			limit_page_length=0,
		)
		return {
			"value": round(value, 2),
			"count": count,
			"prev": round(prev, 2),
			"prev_count": prev_count,
			"by_month": bucket_by_month(daily, self.months, "posting_date", "v"),
		}

	def flows(self) -> dict:
		# Net totals: credit notes and debit notes carry negative base_net_total,
		# so returns net off without a separate query.
		return {
			"invoiced": self._flow("Sales Invoice", "base_net_total"),
			"bills": self._flow("Purchase Invoice", "base_net_total"),
			"received": self._flow(
				"Payment Entry", "base_received_amount", [["payment_type", "=", "Receive"]]
			),
			"paid": self._flow("Payment Entry", "base_paid_amount", [["payment_type", "=", "Pay"]]),
		}

	def bank(self) -> dict | None:
		if not self._can("GL Entry") or not self._can("Account"):
			return None
		accts = frappe.get_list(
			"Account",
			filters={"company": self.company, "is_group": 0, "account_type": ["in", ["Bank", "Cash"]]},
			fields=["name", "account_name", "account_type"],
			limit_page_length=0,
		)
		if not accts:
			return {"total": 0.0, "accounts": [], "company_wide": True}
		rows = frappe.get_list(
			"GL Entry",
			filters=self._gl_filters(
				[["account", "in", [a.name for a in accts]], ["posting_date", "<=", self.on]],
				company_wide=True,
			),
			fields=["account", {"SUM": "debit", "as": "dr"}, {"SUM": "credit", "as": "cr"}],
			group_by="account",
			order_by="account",
			limit_page_length=0,
		)
		bal = {r.account: flt(r.dr) - flt(r.cr) for r in rows}
		out = sorted(
			(
				{
					"name": a.name,
					"label": ledger_label(a.account_name),
					"type": a.account_type,
					"balance": round(bal.get(a.name, 0.0), 2),
				}
				for a in accts
			),
			key=lambda x: -x["balance"],
		)
		return {"total": round(sum(bal.values()), 2), "accounts": out, "company_wide": True}

	def vat(self) -> dict | None:
		"""The VAT 201 return the owner should be thinking about now.

		The open period containing today if there is one, else the earliest
		return not yet filed. Read straight from the filing log.
		"""
		if not frappe.db.exists("DocType", _VAT_LOG) or not self._can(_VAT_LOG):
			return None
		rows = frappe.get_list(
			_VAT_LOG,
			filters=[["company", "=", self.company], ["docstatus", "<", 2]],
			fields=[
				"name",
				"period_start",
				"period_end",
				"filing_due_date",
				"status",
				"deadline_status",
				"net_vat_due",
				"tax_currency",
			],
			order_by="period_end desc",
			limit=12,
		)
		if not rows:
			return None
		current = next(
			(
				r
				for r in rows
				if r.period_start
				and r.period_end
				and getdate(r.period_start) <= self.on <= getdate(r.period_end)
			),
			None,
		)
		if current is None:
			open_rows = [r for r in rows if r.status != "Filed" and r.filing_due_date]
			current = min(open_rows, key=lambda r: getdate(r.filing_due_date)) if open_rows else rows[0]
		return {**_filing_row(current, self.on), "company_wide": True}

	def ageing(self, doctype: str) -> dict | None:
		"""Outstanding today, by days past due. Point in time — ignores the period.

		An invoice with no due date counts as current, not overdue.

		``outstanding_amount`` is in the party account's currency, which for a
		UAE company billing in AED is the company currency.
		"""
		if not self._can(doctype):
			return None
		rows = frappe.get_list(
			doctype,
			filters=self._doc_filters(doctype, [["outstanding_amount", ">", 0]]),
			fields=["due_date", {"SUM": "outstanding_amount", "as": "v"}],
			group_by="due_date",
			order_by="due_date",
			limit_page_length=0,
		)
		buckets = dict.fromkeys(AGE_BUCKETS, 0.0)
		for r in rows:
			buckets[age_bucket(getdate(r.due_date) if r.due_date else None, self.on)] += flt(r.v)
		total = sum(buckets.values())
		return {
			"total": round(total, 2),
			"overdue": round(total - buckets["current"], 2),
			"buckets": [round(buckets[k], 2) for k in AGE_BUCKETS],
		}

	def budget(self) -> dict | None:
		"""Budget vs actual for expense accounts. ``None`` when no budgets exist.

		ERPNext v16 keeps one Budget per account, with its own start and end
		dates (``budget_start_date`` / ``budget_end_date``). The amount is
		prorated by days into the selected period. A Budget Distribution
		(monthly weights) is not applied yet — evenly spread for now.
		"""
		if not frappe.db.exists("DocType", "Budget") or not all(
			self._can(d) for d in ("Budget", "GL Entry", "Account")
		):
			return None
		meta = frappe.get_meta("Budget")
		if not all(
			meta.has_field(f) for f in ("account", "budget_amount", "budget_start_date", "budget_end_date")
		):
			# A Budget schema this code does not know. Better no card than a wrong one.
			return None
		filters = [
			["company", "=", self.company],
			["docstatus", "=", 1],
			["budget_against", "=", "Cost Center"],
			["budget_start_date", "<=", self.b["end"]],
			["budget_end_date", ">=", self.b["start"]],
		]
		if self.cost_center:
			filters.append(["cost_center", "=", self.cost_center])
		budgets = frappe.get_list(
			"Budget",
			filters=filters,
			fields=["account", "budget_amount", "budget_start_date", "budget_end_date"],
			limit_page_length=0,
		)
		planned: dict[str, float] = {}
		for b in budgets:
			if not (b.account and b.budget_start_date and b.budget_end_date):
				continue
			planned[b.account] = planned.get(b.account, 0.0) + prorate(
				b.budget_amount,
				self.b["start"],
				self.b["end"],
				getdate(b.budget_start_date),
				getdate(b.budget_end_date),
			)
		if not planned:
			return None

		actual = self._gl_sum_by_account(list(planned), self.b["start"], self.b["end"])
		names = {a.name: a.account_name for a in self._accounts_by_root()["Expense"]}
		rows = sorted(
			(
				{
					"account": acc,
					"label": ledger_label(names.get(acc, acc)),
					"budget": round(p, 2),
					"actual": round(actual.get(acc, 0.0), 2),
				}
				for acc, p in planned.items()
			),
			key=lambda r: -r["budget"],
		)
		return {
			"rows": rows[:5],
			"total_budget": round(sum(r["budget"] for r in rows), 2),
			"total_actual": round(sum(r["actual"] for r in rows), 2),
		}

	def top_customers(self) -> list[dict]:
		if not self._can("Sales Invoice"):
			return []
		# Grouped on the link alone (portable GROUP BY); sorted here, because
		# ordering by an aggregate alias is not something every query builder allows.
		rows = frappe.get_list(
			"Sales Invoice",
			filters=self._doc_filters(
				"Sales Invoice", [["posting_date", "between", [self.b["start"], self.b["end"]]]]
			),
			fields=["customer", {"SUM": "base_net_total", "as": "v"}],
			group_by="customer",
			order_by="customer",
			limit_page_length=0,
		)
		top = sorted((r for r in rows if flt(r.v) > 0), key=lambda r: -flt(r.v))[:5]
		return [
			{
				"name": r.customer,
				"label": frappe.get_cached_value("Customer", r.customer, "customer_name") or r.customer,
				"value": round(flt(r.v), 2),
			}
			for r in top
		]

	def top_expenses(self) -> list[dict]:
		if not self._can("GL Entry") or not self._can("Account"):
			return []
		acc = self._accounts_by_root()["Expense"]
		sums = self._gl_sum_by_account([a.name for a in acc], self.b["start"], self.b["end"])
		names = {a.name: a.account_name for a in acc}
		top = sorted(((k, v) for k, v in sums.items() if v > 0), key=lambda kv: -kv[1])[:5]
		return [{"account": k, "label": ledger_label(names.get(k, k)), "value": round(v, 2)} for k, v in top]

	def overdue_invoices(self) -> list[dict]:
		if not self._can("Sales Invoice"):
			return []
		rows = frappe.get_list(
			"Sales Invoice",
			filters=self._doc_filters(
				"Sales Invoice",
				[["outstanding_amount", ">", 0], ["due_date", "is", "set"], ["due_date", "<", self.on]],
			),
			fields=["name", "customer", "customer_name", "due_date", "outstanding_amount", "currency"],
			order_by="outstanding_amount desc",
			limit=5,
		)
		return [
			{
				"name": r.name,
				"party": r.customer_name or r.customer,
				"amount": flt(r.outstanding_amount),
				"currency": r.currency,
				"due_date": str(r.due_date),
				"days": (self.on - getdate(r.due_date)).days,
			}
			for r in rows
		]

	def bills_due(self) -> list[dict]:
		if not self._can("Purchase Invoice"):
			return []
		rows = frappe.get_list(
			"Purchase Invoice",
			filters=self._doc_filters(
				"Purchase Invoice",
				[
					["outstanding_amount", ">", 0],
					["due_date", "is", "set"],
					["due_date", "between", [self.on, self.on + timedelta(days=6)]],
				],
			),
			fields=["name", "supplier", "supplier_name", "due_date", "outstanding_amount", "currency"],
			order_by="due_date asc",
			limit=5,
		)
		return [
			{
				"name": r.name,
				"party": r.supplier_name or r.supplier,
				"amount": flt(r.outstanding_amount),
				"currency": r.currency,
				"due_date": str(r.due_date),
				"days": (getdate(r.due_date) - self.on).days,
			}
			for r in rows
		]

	def deadlines(self) -> list[dict]:
		"""Unfiled VAT 201 and Corporate Tax returns, soonest first."""
		out: list[dict] = []
		for doctype, kind, amount_field in ((_VAT_LOG, "vat", "net_vat_due"), (_CT_LOG, "ct", "tax_payable")):
			if not frappe.db.exists("DocType", doctype) or not self._can(doctype):
				continue
			rows = frappe.get_list(
				doctype,
				filters=[
					["company", "=", self.company],
					["docstatus", "<", 2],
					["deadline_status", "!=", "Filed"],
					["filing_due_date", "is", "set"],
				],
				fields=[
					"name",
					"period_start",
					"period_end",
					"filing_due_date",
					"deadline_status",
					amount_field,
				],
				order_by="filing_due_date asc",
				limit=3,
			)
			for r in rows:
				row = _filing_row(r, self.on, amount_field)
				row["kind"] = kind
				out.append(row)
		return sorted(out, key=lambda r: r["due_date"])[:3]

	def readiness(self) -> dict | None:
		try:
			from taxmate.uae.readiness import get_uae_readiness_checklist

			data = get_uae_readiness_checklist(self.company)
		except frappe.PermissionError:
			return None
		if not data.get("applicable"):
			return None
		items = data.get("items") or []
		return {
			"done": sum(1 for i in items if i.get("ok")),
			"total": len(items),
			"missing": [i.get("label") for i in items if not i.get("ok")][:3],
		}


def _filing_row(r, on: date, amount_field: str = "net_vat_due") -> dict:
	due = getdate(r.filing_due_date) if r.get("filing_due_date") else None
	return {
		"name": r.name,
		"period_start": str(r.period_start) if r.get("period_start") else None,
		"period_end": str(r.period_end) if r.get("period_end") else None,
		"due_date": str(due) if due else "",
		"days": (due - on).days if due else None,
		"status": r.get("deadline_status") or r.get("status"),
		"amount": flt(r.get(amount_field)),
	}
