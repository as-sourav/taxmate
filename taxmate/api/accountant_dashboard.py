"""Accountant dashboard — the work queues and the state of the books, in one call.

Design: claude/dashboard-scope.md in the TaxMate project ("Accountant version").

Same rules as the owner dashboard (owner_dashboard.py), plus two of its own:

* **Queues first.** Every count here is something a person can clear today.
  Each one is computed from the same filter the screen links to, so the
  number on the tile and the list behind it agree.
* **Only the close checklist and the VAT card follow the accounting month.**
  Everything else is company-wide and as of today. The payload says which is
  which, so the screen never implies a filter that is not applied.

Nothing here writes. Checks that ERPNext cannot answer from its own tables —
a bank statement's closing balance, whether accruals were posted — are left
out rather than guessed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_last_day, getdate, today

from taxmate.api.owner_dashboard import AGE_BUCKETS, _filing_row, age_bucket
from taxmate.api.resource import assert_company_read, require_login
from taxmate.setup.spa_roles import require_spa_role
from taxmate.utils.company import get_default_company
from taxmate.utils.localize import ledger_label

_VAT_LOG = "UAE VAT 201 Filing Log"
_CT_LOG = "UAE CT Filing Log"
_UBO = "UAE UBO Register"
_EINV_LOG = "UAE E-Invoice Log"
_GL_EXCLUDE_VOUCHERS = ["Period Closing Voucher"]
_DRAFT_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry")
_ACTIVITY_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry")

LATE_DAYS = 60  # "Invoices 60+ days late" queue
ROUND_OFF_LIMIT = 100.0  # round-off balance for the month above this is flagged
TOLERANCE = 0.5  # differences below half a fils-rounded dirham are noise
MONTHS_SHOWN = 3
TOP_PARTIES = 6
LIST_LIMIT = 6


# ── Pure helpers (no database; unit-tested without a site) ─────────────────


def month_options(on: date, n: int = MONTHS_SHOWN) -> list[str]:
	"""The current month and the ``n - 1`` before it, oldest first, as YYYY-MM."""
	first = on.replace(day=1)
	return [getdate(add_months(first, -i)).strftime("%Y-%m") for i in range(n - 1, -1, -1)]


def month_bounds(key: str) -> tuple[date, date]:
	"""First and last day of a YYYY-MM month."""
	try:
		y, m = (int(x) for x in key.split("-"))
		start = date(y, m, 1)
	except (ValueError, AttributeError):
		frappe.throw(_("Month must look like 2026-09"))
	return start, getdate(get_last_day(start))


def to_company_currency(row: dict) -> float:
	"""A Payment Entry's unallocated amount in company currency.

	ERPNext keeps ``unallocated_amount`` in the party account's currency:
	``paid_from`` for Receive, ``paid_to`` for Pay (payment_entry.py
	``set_unallocated_amount``). The matching exchange rate converts it.
	"""
	amount = flt(row.get("unallocated_amount"))
	rate = (
		row.get("source_exchange_rate")
		if row.get("payment_type") == "Receive"
		else row.get("target_exchange_rate")
	)
	return amount * (flt(rate) or 1.0)


def ageing_by_party(rows: list[dict], on: date, top: int = TOP_PARTIES) -> dict:
	"""Outstanding by party x ageing bucket: the largest ``top`` parties, then Others.

	``rows`` carry ``party``, ``label``, ``due_date`` and ``v`` (outstanding).
	The totals row is the sum of every row, so it matches the owner
	dashboard's ageing card for the same day.
	"""
	parties: dict[str, dict] = {}
	for r in rows:
		key = r.get("party") or ""
		p = parties.setdefault(
			key, {"party": key, "label": r.get("label") or key, "buckets": [0.0] * len(AGE_BUCKETS)}
		)
		due = getdate(r["due_date"]) if r.get("due_date") else None
		p["buckets"][AGE_BUCKETS.index(age_bucket(due, on))] += flt(r.get("v"))

	ranked = sorted(parties.values(), key=lambda p: (-sum(p["buckets"]), p["label"]))
	shown, rest = ranked[:top], ranked[top:]
	out = [_party_row(p) for p in shown]
	others = None
	if rest:
		b = [sum(p["buckets"][i] for p in rest) for i in range(len(AGE_BUCKETS))]
		others = {"count": len(rest), "buckets": [round(x, 2) for x in b], "total": round(sum(b), 2)}
	total_b = [sum(p["buckets"][i] for p in ranked) for i in range(len(AGE_BUCKETS))]
	return {
		"rows": out,
		"others": others,
		"total": {"buckets": [round(x, 2) for x in total_b], "total": round(sum(total_b), 2)},
		"parties": len(ranked),
	}


def _party_row(p: dict) -> dict:
	return {
		"party": p["party"],
		"label": p["label"],
		"buckets": [round(x, 2) for x in p["buckets"]],
		"total": round(sum(p["buckets"]), 2),
	}


def filed_period_for(d: date | None, filed: list[dict]) -> dict | None:
	"""The filed VAT return whose period contains ``d``, if any."""
	if not d:
		return None
	for f in filed:
		if f["start"] <= d <= f["end"]:
			return f
	return None


def activity_verb(docstatus: int, amended_from: str | None) -> str:
	if cint(docstatus) == 2:
		return "cancelled"
	return "amended" if amended_from else "submitted"


# ── Endpoint ───────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_accountant_dashboard(month: str | None = None, company: str | None = None) -> dict[str, Any]:
	require_login()
	require_spa_role("accountant", "clerk", "viewer")
	company = company or get_default_company()
	if not company:
		frappe.throw(_("Set a default Company to see the dashboard."))
	assert_company_read(company)

	on = getdate(today())
	months = month_options(on)
	month = month if month in months else months[-1]
	ctx = _Ctx(company, on, month)

	queues = ctx.queues()
	return {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"today": str(on),
		"month": month,
		"months": ctx.month_states(months),
		"queues": queues,
		"close": ctx.close(),
		"vat": ctx.vat(),
		"health": ctx.health(),
		"banks": ctx.banks(),
		"unallocated": ctx.unallocated(),
		"fixes": ctx.fixes(),
		"ageing": {
			"receivable": ctx.party_ageing("Sales Invoice"),
			"payable": ctx.party_ageing("Purchase Invoice"),
		},
		"einvoice": ctx.einvoice(),
		"activity": ctx.activity(),
		"calendar": ctx.calendar(),
	}


class _Ctx:
	"""One request's company, day and accounting month; one method per section."""

	def __init__(self, company: str, on: date, month: str):
		self.company = company
		self.on = on
		self.month = month
		self.m_start, self.m_end = month_bounds(month)
		default_fb = frappe.get_cached_value("Company", company, "default_finance_book")
		self.finance_books = ["", default_fb] if default_fb else [""]
		frozen = (
			frappe.db.get_value("Company", company, "accounts_frozen_till_date")
			if frappe.get_meta("Company").has_field("accounts_frozen_till_date")
			else None
		)
		self.frozen_till = getdate(frozen) if frozen else None
		self._filed: list[dict] | None = None
		self._unalloc: list[dict] | None = None
		self._fix_cache: dict | None = None

	# ── plumbing ──

	def _can(self, *doctypes: str) -> bool:
		cache = self.__dict__.setdefault("_perm", {})
		for d in doctypes:
			if d not in cache:
				cache[d] = bool(frappe.db.exists("DocType", d) and frappe.has_permission(d, "read"))
			if not cache[d]:
				return False
		return True

	def _gl_filters(self, extra: list | None = None) -> list:
		return [
			["company", "=", self.company],
			["is_cancelled", "=", 0],
			["voucher_type", "not in", _GL_EXCLUDE_VOUCHERS],
			["finance_book", "in", self.finance_books],
		] + (extra or [])

	def _gl_balance(
		self, accounts: list[str], upto: date, since: date | None = None, in_account_currency: bool = False
	) -> dict[str, float]:
		"""Debit - credit per account up to ``upto`` (optionally from ``since``).

		Company currency, unless ``in_account_currency``.
		"""
		if not accounts:
			return {}
		f = [["account", "in", accounts], ["posting_date", "<=", upto]]
		if since:
			f.append(["posting_date", ">=", since])
		dr, cr = (
			("debit_in_account_currency", "credit_in_account_currency")
			if in_account_currency
			else ("debit", "credit")
		)
		rows = frappe.get_list(
			"GL Entry",
			filters=self._gl_filters(f),
			fields=["account", {"SUM": dr, "as": "dr"}, {"SUM": cr, "as": "cr"}],
			group_by="account",
			order_by="account",
			limit_page_length=0,
		)
		return {r.account: flt(r.dr) - flt(r.cr) for r in rows}

	def _accounts(self, **filters) -> list[dict]:
		return frappe.get_list(
			"Account",
			filters={"company": self.company, "is_group": 0, **filters},
			fields=["name", "account_name", "account_type", "account_currency"],
			order_by="name",
			limit_page_length=0,
		)

	def _company_bank_accounts(self) -> list[dict] | None:
		"""Enabled company Bank Accounts linked to a ledger account — the rows of the bank table."""
		if not self._can("Bank Account"):
			return None
		if "_bank_accts" not in self.__dict__:
			self._bank_accts = [
				b
				for b in frappe.get_list(
					"Bank Account",
					filters=[
						["company", "=", self.company],
						["is_company_account", "=", 1],
						["disabled", "=", 0],
					],
					fields=["name", "account", "account_name", "bank_account_no", "iban"],
					limit_page_length=0,
				)
				if b.account
			]
		return self._bank_accts

	def _bank_txn_filters(self, extra: list | None = None) -> list:
		"""Open statement lines, limited to the bank accounts the bank table lists,
		so the queue tile and the close step count what the table shows (a
		disabled bank account's leftover lines would otherwise count but never show)."""
		f = [["company", "=", self.company], ["docstatus", "=", 1], ["unallocated_amount", ">", 0]]
		accts = self._company_bank_accounts()
		if accts is not None:
			f.append(["bank_account", "in", [b.name for b in accts] or [""]])
		return f + (extra or [])

	def _in_company_currency(self, row: dict) -> float:
		"""An invoice group's summed ``outstanding_amount`` (``v``) in company currency.

		ERPNext keeps outstanding_amount in the party account's currency; a
		foreign-currency party account is always in the invoice currency, so
		the invoice's ``conversion_rate`` converts it (as the ledger booked it).
		"""
		if "_company_cur" not in self.__dict__:
			self._company_cur = frappe.get_cached_value("Company", self.company, "default_currency")
		cur = row.get("party_account_currency")
		if cur and cur != self._company_cur:
			return flt(row.get("v")) * (flt(row.get("conversion_rate")) or 1.0)
		return flt(row.get("v"))

	def _count(self, doctype: str, filters: list) -> int:
		rows = frappe.get_list(doctype, filters=filters, fields=[{"COUNT": "*", "as": "n"}], limit=1)
		return cint(rows[0].n) if rows else 0

	def filed_returns(self) -> list[dict]:
		"""Submitted VAT returns, newest first: the periods TaxMate locks."""
		if self._filed is None:
			self._filed = []
			if self._can(_VAT_LOG):
				rows = frappe.get_list(
					_VAT_LOG,
					filters=[["company", "=", self.company], ["docstatus", "=", 1]],
					fields=["name", "period_start", "period_end", "filed_on", "modified"],
					order_by="period_end desc",
					limit=8,
				)
				self._filed = [
					{
						"name": r.name,
						"start": getdate(r.period_start),
						"end": getdate(r.period_end),
						"filed_on": r.filed_on or r.modified,
					}
					for r in rows
					if r.period_start and r.period_end
				]
		return self._filed

	def _open_since(self) -> date:
		"""First day not covered by a filed VAT return — where data fixes still matter."""
		filed = self.filed_returns()
		if filed:
			return max(f["end"] for f in filed) + timedelta(days=1)
		return date(self.on.year, 1, 1)

	# ── accounting months ──

	def month_states(self, months: list[str]) -> list[dict]:
		out = []
		for key in months:
			start, end = month_bounds(key)
			locked = bool(self.frozen_till and self.frozen_till >= end)
			filed = filed_period_for(end, self.filed_returns())
			out.append(
				{
					"key": key,
					"start": str(start),
					"end": str(end),
					"state": "locked" if locked else ("open" if end >= self.on else "unlocked"),
					"vat_filed": bool(filed) if self._can(_VAT_LOG) else None,
				}
			)
		return out

	# ── work queues (today) ──

	def queues(self) -> dict:
		drafts = None
		if any(self._can(d) for d in _DRAFT_DOCTYPES):
			by = {
				d: self._count(d, [["company", "=", self.company], ["docstatus", "=", 0]])
				for d in _DRAFT_DOCTYPES
				if self._can(d)
			}
			drafts = {"total": sum(by.values()), "by_doctype": by}

		unalloc = None
		rows = self._unallocated_rows()
		if rows is not None:
			unalloc = {"count": len(rows), "amount": round(sum(r["amount"] for r in rows), 2)}

		bank = None
		if self._can("Bank Transaction"):
			b = frappe.get_list(
				"Bank Transaction",
				filters=self._bank_txn_filters(),
				fields=["bank_account", {"COUNT": "*", "as": "n"}],
				group_by="bank_account",
				order_by="bank_account",
				limit_page_length=0,
			)
			bank = {"count": sum(cint(r.n) for r in b), "accounts": len(b)}

		einv = None
		if self._can(_EINV_LOG):
			e = frappe.get_list(
				_EINV_LOG,
				filters=[["company", "=", self.company], ["status", "in", ["Rejected", "Failed"]]],
				fields=["status", {"COUNT": "*", "as": "n"}],
				group_by="status",
				order_by="status",
				limit_page_length=0,
			)
			by = {r.status: cint(r.n) for r in e}
			einv = {
				"count": sum(by.values()),
				"rejected": by.get("Rejected", 0),
				"failed": by.get("Failed", 0),
			}

		fixes = self._fixes()
		data = (
			None
			if fixes is None
			else {"count": sum(c["count"] for c in fixes), "checks": sum(1 for c in fixes if c["count"])}
		)

		late = self.late_invoices()

		return {
			"drafts": drafts,
			"unallocated": unalloc,
			"bank": bank,
			"einvoice": einv,
			"data": data,
			"late": late,
		}

	# ── invoices long past due (today) ──

	def late_invoices(self) -> dict | None:
		"""Count and value of submitted sales invoices due more than
		``LATE_DAYS`` ago and still outstanding.

		Lifted out of ``queues()`` unchanged so the All-clients dashboard can
		ask for this one figure without paying for the whole queue payload.
		``queues()`` now calls it, so there is still one definition and the two
		dashboards cannot disagree.

		The ``is_opening`` exclusion is why this agrees with the 61-90 and 90+
		ageing columns; see the comment in the filters below.
		"""
		if not self._can("Sales Invoice"):
			return None
		cutoff = self.on - timedelta(days=LATE_DAYS)
		r = frappe.get_list(
			"Sales Invoice",
			filters=[
				["company", "=", self.company],
				["docstatus", "=", 1],
				["outstanding_amount", ">", 0],
				["due_date", "is", "set"],
				["due_date", "<", cutoff],
				# Same basis as the ageing tables below, so the tile and the 61-90 / 90+ columns agree.
				["is_opening", "!=", "Yes"],
			],
			fields=[
				"party_account_currency",
				"conversion_rate",
				{"COUNT": "*", "as": "n"},
				{"SUM": "outstanding_amount", "as": "v"},
				{"MIN": "due_date", "as": "oldest"},
			],
			# Grouped by currency and rate: outstanding_amount is in the party
			# account's currency, so each group is converted before summing.
			group_by="party_account_currency, conversion_rate",
			order_by="party_account_currency",
			limit_page_length=0,
		)
		oldest = min((getdate(x.oldest) for x in r if x.oldest), default=None)
		late = {
			"count": sum(cint(x.n) for x in r),
			"amount": round(sum(self._in_company_currency(x) for x in r), 2),
			"oldest_days": (self.on - oldest).days if oldest else None,
		}
		return late

	# ── month-end close ──

	def close(self) -> dict:
		s, e = self.m_start, self.m_end
		steps: list[dict] = []

		def step(key: str, ok: bool | None, **info):
			# ok=None → not applicable (e.g. no assets); counts as done.
			steps.append({"key": key, "ok": bool(ok) if ok is not None else True, "na": ok is None, **info})

		if self._can("Bank Transaction"):
			rows = frappe.get_list(
				"Bank Transaction",
				filters=self._bank_txn_filters([["date", "<=", e]]),
				fields=["bank_account", {"COUNT": "*", "as": "n"}],
				group_by="bank_account",
				order_by="bank_account",
				limit_page_length=0,
			)
			total_accts = (
				self._count(
					"Bank Account",
					[["company", "=", self.company], ["is_company_account", "=", 1], ["disabled", "=", 0]],
				)
				if self._can("Bank Account")
				else 0
			)
			n = sum(cint(r.n) for r in rows)
			step("bank", n == 0 if total_accts else None, n=n, accounts=len(rows), total=total_accts)

		drafts = {
			d: self._count(
				d,
				[["company", "=", self.company], ["docstatus", "=", 0], ["posting_date", "between", [s, e]]],
			)
			for d in _DRAFT_DOCTYPES
			if self._can(d)
		}
		if drafts:
			n = sum(drafts.values())
			step("drafts", n == 0, n=n)

		if self._can("Payment Entry"):
			rows = [r for r in (self._unallocated_rows() or []) if getdate(r["date"]) <= e]
			step("payments", not rows, n=len(rows), amount=round(sum(r["amount"] for r in rows), 2))

		dep = self._depreciation_due(e)
		if dep is not None:
			step(
				"depreciation",
				None if dep["assets"] == 0 else dep["n"] == 0,
				n=dep["n"],
				amount=dep["amount"],
			)

		stock = self._stock_vs_gl(e)
		if stock is not None:
			step(
				"stock", None if not stock["applies"] else abs(stock["diff"]) <= TOLERANCE, diff=stock["diff"]
			)

		vat = self._vat_log_for(e)
		if vat is not None:
			if vat["log"]:
				step("vat", True, status=vat["log"].status, name=vat["log"].name)
			else:
				step("vat", False, name=None)

		susp = self._suspense(e)
		if susp is not None:
			step(
				"suspense",
				None if not susp["accounts"] else abs(susp["balance"]) <= TOLERANCE,
				amount=susp["balance"],
				n=susp["accounts"],
			)

		locked = bool(self.frozen_till and self.frozen_till >= e)
		step(
			"lock",
			locked,
			frozen_till=str(self.frozen_till) if self.frozen_till else None,
			ready=all(x["ok"] for x in steps),
		)

		return {
			"month": self.month,
			"start": str(s),
			"end": str(e),
			"done": sum(1 for x in steps if x["ok"]),
			"total": len(steps),
			"steps": steps,
		}

	def _depreciation_due(self, upto: date) -> dict | None:
		if not self._can("Asset", "Asset Depreciation Schedule"):
			return None
		assets = self._count(
			"Asset",
			[["company", "=", self.company], ["docstatus", "=", 1], ["calculate_depreciation", "=", 1]],
		)
		if not assets:
			return {"assets": 0, "n": 0, "amount": 0.0}
		rows = frappe.get_list(
			"Asset Depreciation Schedule",
			filters=[
				["company", "=", self.company],
				["docstatus", "=", 1],
				["status", "=", "Active"],
				["Depreciation Schedule", "schedule_date", "<=", upto],
				["Depreciation Schedule", "journal_entry", "is", "not set"],
			],
			fields=["name", "depreciation_schedule.depreciation_amount as amount"],
			limit_page_length=0,
		)
		return {"assets": assets, "n": len(rows), "amount": round(sum(flt(r.amount) for r in rows), 2)}

	def _stock_vs_gl(self, upto: date) -> dict | None:
		if not self._can("Stock Ledger Entry", "GL Entry", "Account"):
			return None
		if not cint(frappe.get_cached_value("Company", self.company, "enable_perpetual_inventory")):
			return {"applies": False, "diff": 0.0}
		accts = [a.name for a in self._accounts(account_type="Stock")]
		sle = frappe.get_list(
			"Stock Ledger Entry",
			filters=[["company", "=", self.company], ["is_cancelled", "=", 0], ["posting_date", "<=", upto]],
			fields=[{"SUM": "stock_value_difference", "as": "v"}, {"COUNT": "*", "as": "n"}],
			limit=1,
		)
		if not accts and not (sle and cint(sle[0].n)):
			return {"applies": False, "diff": 0.0}
		stock_value = flt(sle[0].v) if sle else 0.0
		gl = sum(self._gl_balance(accts, upto).values())
		return {
			"applies": True,
			"diff": round(gl - stock_value, 2),
			"stock": round(stock_value, 2),
			"gl": round(gl, 2),
		}

	def _suspense(self, upto: date) -> dict | None:
		"""Balance on Temporary-type accounts (suspense, temporary opening)."""
		if not self._can("GL Entry", "Account"):
			return None
		accts = [a.name for a in self._accounts(account_type="Temporary")]
		bal = self._gl_balance(accts, upto)
		entries = 0
		if accts and any(abs(v) > TOLERANCE for v in bal.values()):
			entries = self._count(
				"GL Entry", self._gl_filters([["account", "in", accts], ["posting_date", "<=", upto]])
			)
		return {"accounts": len(accts), "balance": round(sum(bal.values()), 2), "entries": entries}

	def _vat_log_for(self, d: date) -> dict | None:
		if not self._can(_VAT_LOG):
			return None
		rows = frappe.get_list(
			_VAT_LOG,
			filters=[
				["company", "=", self.company],
				["docstatus", "<", 2],
				["period_start", "<=", d],
				["period_end", ">=", d],
			],
			fields=[
				"name",
				"period_start",
				"period_end",
				"filing_due_date",
				"status",
				"docstatus",
				"net_vat_due",
				"generated_on",
			],
			order_by="docstatus desc, modified desc",
			limit=1,
		)
		return {"log": rows[0] if rows else None}

	# ── VAT 201 for the selected month ──

	def vat(self) -> dict | None:
		found = self._vat_log_for(self.m_end)
		if found is None:
			return None
		log = found["log"]
		if not log:
			return {"log": None, "month_end": str(self.m_end)}
		boxes = []
		if frappe.has_permission(_VAT_LOG, "read", log.name):
			doc = frappe.get_doc(_VAT_LOG, log.name)
			boxes = [
				{
					"box": b.box_no,
					"legend": b.legend,
					"amount": flt(b.amount),
					"vat": flt(b.vat_amount),
					"subtotal": cint(b.is_subtotal),
				}
				for b in (doc.get("boxes") or [])
			]
		ledger = self._vat_ledger(getdate(log.period_start), getdate(log.period_end))
		net = flt(log.net_vat_due)
		due = getdate(log.filing_due_date) if log.filing_due_date else None
		return {
			"log": {
				"name": log.name,
				"period_start": str(log.period_start),
				"period_end": str(log.period_end),
				"due_date": str(due) if due else None,
				"days": (due - self.on).days if due else None,
				"status": log.status or ("Filed" if cint(log.docstatus) == 1 else "Draft"),
				"filed": cint(log.docstatus) == 1,
				"generated_on": str(log.generated_on) if log.generated_on else None,
				"in_progress": getdate(log.period_end) >= self.on,
			},
			"boxes": boxes,
			"net": round(net, 2),
			"ledger": ledger if ledger is None else {**ledger, "diff": round(ledger["net"] - net, 2)},
		}

	def _vat_ledger(self, start: date, end: date) -> dict | None:
		"""Net credit on the company's VAT accounts over the return period.

		Output VAT is credited and recoverable input VAT debited to the
		accounts listed in UAE VAT Settings, so credit - debit over the
		period should equal Box 14 (payable positive). A difference means a
		VAT posting the return did not pick up, or the reverse.
		"""
		if not self._can("GL Entry") or not frappe.db.exists("DocType", "UAE VAT Account"):
			return None
		accts = frappe.get_all(
			"UAE VAT Account",
			filters={"parent": self.company, "parenttype": "UAE VAT Settings"},
			pluck="account",
		)
		if not accts:
			return {"net": 0.0, "accounts": 0}
		# Payment Entries are left out: paying the previous return to the FTA
		# debits the VAT account inside this period without being part of it.
		# A VAT payment booked by journal still shows up as a difference, and
		# the screen says that is the usual cause.
		rows = frappe.get_list(
			"GL Entry",
			filters=self._gl_filters(
				[
					["account", "in", accts],
					["posting_date", "between", [start, end]],
					["voucher_type", "!=", "Payment Entry"],
				]
			),
			fields=["account", {"SUM": "debit", "as": "dr"}, {"SUM": "credit", "as": "cr"}],
			group_by="account",
			order_by="account",
			limit_page_length=0,
		)
		bal = {r.account: flt(r.dr) - flt(r.cr) for r in rows}
		return {"net": round(-sum(bal.values()), 2), "accounts": len(accts)}

	# ── ledger health (today) ──

	def health(self) -> list[dict] | None:
		if not self._can("GL Entry", "Account"):
			return None
		out: list[dict] = []
		on = self.on

		tb = frappe.get_list(
			"GL Entry",
			filters=self._gl_filters([["posting_date", "<=", on]]),
			fields=[{"SUM": "debit", "as": "dr"}, {"SUM": "credit", "as": "cr"}],
			limit=1,
		)
		dr, cr = (flt(tb[0].dr), flt(tb[0].cr)) if tb else (0.0, 0.0)
		out.append(
			{
				"key": "trial_balance",
				"ok": abs(dr - cr) <= TOLERANCE,
				"amount": round(dr, 2),
				"diff": round(dr - cr, 2),
			}
		)

		susp = self._suspense(on)
		out.append(
			{
				"key": "suspense",
				"ok": abs(susp["balance"]) <= TOLERANCE,
				"amount": susp["balance"],
				"n": susp["entries"],
				"na": not susp["accounts"],
			}
		)

		for key, acct_type in (("receivable", "Receivable"), ("payable", "Payable")):
			chk = self._control_vs_party(acct_type)
			if chk is not None:
				out.append({"key": key, "ok": abs(chk) <= TOLERANCE, "diff": chk})

		stock = self._stock_vs_gl(on)
		if stock is not None and stock["applies"]:
			out.append({"key": "stock", "ok": abs(stock["diff"]) <= TOLERANCE, "diff": stock["diff"]})

		late = self._changed_after_filing()
		if late is not None:
			out.append({"key": "after_filing", "ok": not late, "n": len(late), "items": late[:3]})

		bad = self._bad_account_postings()
		out.append({"key": "bad_accounts", "ok": bad == 0, "n": bad})

		ro = self._round_off()
		if ro is not None:
			out.append(
				{"key": "round_off", "ok": abs(ro) <= ROUND_OFF_LIMIT, "amount": ro, "limit": ROUND_OFF_LIMIT}
			)
		return out

	def _control_vs_party(self, account_type: str) -> float | None:
		"""GL balance of the control accounts minus the party ledger. Should be 0."""
		if not self._can("Payment Ledger Entry"):
			return None
		accts = [a.name for a in self._accounts(account_type=account_type)]
		if not accts:
			return 0.0
		gl = sum(self._gl_balance(accts, self.on).values())
		ple = frappe.get_list(
			"Payment Ledger Entry",
			filters=[
				["company", "=", self.company],
				["delinked", "=", 0],
				["account", "in", accts],
				["posting_date", "<=", self.on],
			],
			fields=[{"SUM": "amount", "as": "v"}],
			limit=1,
		)
		# PLE amount is debit - credit for Receivable but credit - debit for Payable
		# (erpnext/accounts/utils.py get_payment_ledger_entries); GL here is debit - credit.
		sign = -1 if account_type == "Payable" else 1
		return round(gl - sign * (flt(ple[0].v) if ple else 0.0), 2)

	def _changed_after_filing(self) -> list[dict] | None:
		"""Ledger postings dated inside a filed VAT period but created after it was filed."""
		filed = self.filed_returns()
		if not self._can(_VAT_LOG):
			return None
		out: list[dict] = []
		for f in filed[:4]:
			if not f["filed_on"]:
				continue
			rows = frappe.get_list(
				"GL Entry",
				# No is_cancelled filter: cancelling a document after filing writes
				# reversal rows (also is_cancelled=1) dated in the filed period, and
				# that is exactly the change this check exists to catch.
				filters=[
					["company", "=", self.company],
					["posting_date", "between", [f["start"], f["end"]]],
					["creation", ">", f["filed_on"]],
				],
				fields=["voucher_type", "voucher_no", {"MIN": "posting_date", "as": "posting_date"}],
				group_by="voucher_type, voucher_no",
				order_by="voucher_no",
				limit_page_length=0,
			)
			out += [
				{
					"doctype": r.voucher_type,
					"name": r.voucher_no,
					"posting_date": str(r.posting_date),
					"return": f["name"],
				}
				for r in rows
			]
		return out

	def _bad_account_postings(self) -> int:
		"""Postings this month to group accounts or to disabled accounts."""
		bad = frappe.get_list(
			"Account",
			filters=[["company", "=", self.company]],
			or_filters=[["is_group", "=", 1], ["disabled", "=", 1]],
			pluck="name",
			limit_page_length=0,
		)
		if not bad:
			return 0
		return self._count(
			"GL Entry",
			self._gl_filters(
				[["account", "in", bad], ["posting_date", "between", [self.on.replace(day=1), self.on]]]
			),
		)

	def _round_off(self) -> float | None:
		acct = frappe.get_cached_value("Company", self.company, "round_off_account")
		if not acct:
			return None
		bal = self._gl_balance([acct], self.on, since=self.on.replace(day=1))
		return round(bal.get(acct, 0.0), 2)

	# ── bank reconciliation (today) ──

	def banks(self) -> list[dict] | None:
		if not self._can("Account", "GL Entry"):
			return None
		accts = self._accounts(account_type=["in", ["Bank", "Cash"]])
		if not accts:
			return []
		bal = self._gl_balance([a.name for a in accts], self.on)
		# A foreign-currency bank is reconciled against its statement in its own
		# currency, and the screen labels the balance with account_currency.
		company_cur = frappe.get_cached_value("Company", self.company, "default_currency")
		foreign = [a.name for a in accts if a.account_currency and a.account_currency != company_cur]
		if foreign:
			bal.update(self._gl_balance(foreign, self.on, in_account_currency=True))

		links: dict[str, dict] = {}
		txn: dict[str, dict] = {}
		for b in self._company_bank_accounts() or []:
			links[b.account] = b
		if links and self._can("Bank Transaction"):
			names = [b.name for b in links.values()]
			for r in frappe.get_list(
				"Bank Transaction",
				filters=[
					["bank_account", "in", names],
					["docstatus", "=", 1],
					["unallocated_amount", ">", 0],
				],
				fields=[
					"bank_account",
					{"COUNT": "*", "as": "n"},
					{"SUM": "unallocated_amount", "as": "v"},
					{"MIN": "date", "as": "oldest"},
				],
				group_by="bank_account",
				order_by="bank_account",
				limit_page_length=0,
			):
				txn.setdefault(r.bank_account, {}).update(n=cint(r.n), v=flt(r.v), oldest=r.oldest)
			for r in frappe.get_list(
				"Bank Transaction",
				filters=[["bank_account", "in", names], ["docstatus", "=", 1]],
				fields=["bank_account", {"MAX": "date", "as": "last"}],
				group_by="bank_account",
				order_by="bank_account",
				limit_page_length=0,
			):
				txn.setdefault(r.bank_account, {}).update(last=r.last)

		can_txn = self._can("Bank Transaction")
		out = []
		for a in accts:
			ba = links.get(a.name)
			t = txn.get(ba.name, {}) if ba else {}
			number = (ba.bank_account_no or ba.iban or "") if ba else ""
			oldest = getdate(t["oldest"]) if t.get("oldest") else None
			last = getdate(t["last"]) if t.get("last") else None
			out.append(
				{
					"account": a.name,
					"label": ledger_label(a.account_name),
					"type": a.account_type,
					"currency": a.account_currency,
					"mask": number[-4:] if number else "",
					"bank_account": ba.name if ba else None,
					"balance": round(bal.get(a.name, 0.0), 2),
					# None, not 0, when bank statement lines cannot be read.
					"unreconciled": t.get("n", 0) if can_txn else None,
					"unreconciled_amount": round(t.get("v", 0.0), 2) if can_txn else None,
					"last_statement": str(last) if last else None,
					# Everything dated before the oldest open line is matched.
					"reconciled_to": str(oldest - timedelta(days=1))
					if oldest
					else (str(last) if last else None),
				}
			)
		return sorted(out, key=lambda r: (r["type"] != "Bank", -r["balance"]))

	# ── unallocated payments (today) ──

	def _unallocated_rows(self) -> list[dict] | None:
		if self._unalloc is None:
			if not self._can("Payment Entry"):
				return None
			rows = frappe.get_list(
				"Payment Entry",
				filters=[
					["company", "=", self.company],
					["docstatus", "=", 1],
					["unallocated_amount", ">", 0],
					["party_type", "in", ["Customer", "Supplier"]],
				],
				fields=[
					"name",
					"payment_type",
					"party_type",
					"party",
					"party_name",
					"posting_date",
					"reference_no",
					"unallocated_amount",
					"source_exchange_rate",
					"target_exchange_rate",
				],
				order_by="posting_date asc",
				limit_page_length=0,
			)
			self._unalloc = [
				{
					"name": r.name,
					"type": r.payment_type,
					"party_type": r.party_type,
					"party": r.party,
					"party_name": r.party_name or r.party,
					"date": str(r.posting_date),
					"days": (self.on - getdate(r.posting_date)).days,
					"reference": r.reference_no,
					"amount": round(to_company_currency(r), 2),
				}
				for r in rows
			]
		return self._unalloc

	def unallocated(self) -> dict | None:
		rows = self._unallocated_rows()
		if rows is None:
			return None
		biggest = sorted(rows, key=lambda r: -r["amount"])[:LIST_LIMIT]
		open_count = self._open_invoice_counts(biggest)
		for r in biggest:
			r["open_docs"] = open_count.get((r["party_type"], r["party"]), 0)
		return {
			"count": len(rows),
			"amount": round(sum(r["amount"] for r in rows), 2),
			"oldest_days": max((r["days"] for r in rows), default=None),
			"rows": biggest,
		}

	def _open_invoice_counts(self, rows: list[dict]) -> dict[tuple, int]:
		out: dict[tuple, int] = {}
		for party_type, doctype, field in (
			("Customer", "Sales Invoice", "customer"),
			("Supplier", "Purchase Invoice", "supplier"),
		):
			parties = sorted({r["party"] for r in rows if r["party_type"] == party_type})
			if not parties or not self._can(doctype):
				continue
			for r in frappe.get_list(
				doctype,
				filters=[
					["company", "=", self.company],
					["docstatus", "=", 1],
					["outstanding_amount", ">", 0],
					[field, "in", parties],
				],
				fields=[field, {"COUNT": "*", "as": "n"}],
				group_by=field,
				order_by=field,
				limit_page_length=0,
			):
				out[(party_type, r[field])] = cint(r.n)
		return out

	# ── data to fix before filing ──

	def _fixes(self) -> list[dict] | None:
		if self._fix_cache is not None:
			return self._fix_cache["checks"]
		since = self._open_since()
		checks: list[dict] = []

		if self._can("Purchase Invoice", "Supplier"):
			rows = frappe.get_list(
				"Purchase Invoice",
				filters=[
					["company", "=", self.company],
					["docstatus", "=", 1],
					["posting_date", ">=", since],
					["base_total_taxes_and_charges", ">", 0],
				],
				# One row per supplier, not per bill: the unfiled period can hold a year of bills.
				fields=[
					"supplier",
					"supplier_name",
					{"COUNT": "*", "as": "n"},
					{"SUM": "base_total_taxes_and_charges", "as": "v"},
				],
				group_by="supplier, supplier_name",
				order_by="supplier",
				limit_page_length=0,
			)
			no_trn = self._parties_without_trn("Supplier", {r.supplier for r in rows})
			hit = sorted((r for r in rows if r.supplier in no_trn), key=lambda r: -cint(r.n))
			checks.append(
				{
					"key": "supplier_trn",
					"severity": "bad",
					"count": sum(cint(r.n) for r in hit),
					"amount": round(sum(flt(r.v) for r in hit), 2),
					"names": _first_names([r.supplier_name or r.supplier for r in hit]),
					"route": "/suppliers",
				}
			)

		if self._can("Sales Invoice", "Customer"):
			rows = frappe.get_list(
				"Sales Invoice",
				filters=[
					["company", "=", self.company],
					["docstatus", "=", 1],
					["posting_date", ">=", since],
					["base_total_taxes_and_charges", ">", 0],
				],
				fields=["customer", "customer_name", {"COUNT": "*", "as": "n"}],
				group_by="customer, customer_name",
				order_by="customer",
				limit_page_length=0,
			)
			business = self._business_customers({r.customer for r in rows})
			no_trn = self._parties_without_trn("Customer", business)
			hit = sorted((r for r in rows if r.customer in no_trn), key=lambda r: -cint(r.n))
			checks.append(
				{
					"key": "customer_trn",
					"severity": "bad",
					"count": sum(cint(r.n) for r in hit),
					"names": _first_names([r.customer_name or r.customer for r in hit]),
					"route": "/customers",
				}
			)

			if frappe.get_meta("Sales Invoice").has_field("vat_emirate"):
				pos_filters = [
					["company", "=", self.company],
					["docstatus", "<", 2],
					["posting_date", ">=", since],
					["vat_emirate", "is", "not set"],
				]
				n = self._count("Sales Invoice", pos_filters)
				rows = (
					frappe.get_list(
						"Sales Invoice",
						filters=pos_filters,
						fields=["name"],
						order_by="posting_date asc",
						limit=2,
					)
					if n
					else []
				)
				checks.append(
					{
						"key": "place_of_supply",
						"severity": "warn",
						"count": n,
						"names": {"shown": [r.name for r in rows], "more": max(n - len(rows), 0)},
						"route": f"/invoices/{rows[0].name}" if n == 1 else "/invoices",
					}
				)

		if self._can("Item"):
			meta = frappe.get_meta("Item")
			if all(meta.has_field(f) for f in ("uae_item_type", "hs_code", "sac_code")):
				# Counted, not listed: the item master can be very large.
				base = [["disabled", "=", 0], ["is_sales_item", "=", 1]]
				goods_f = [*base, ["uae_item_type", "in", ["Goods", "Both"]], ["hs_code", "is", "not set"]]
				services_f = [
					*base,
					["uae_item_type", "in", ["Service", "Both"]],
					["sac_code", "is", "not set"],
				]
				both_f = [
					*base,
					["uae_item_type", "=", "Both"],
					["hs_code", "is", "not set"],
					["sac_code", "is", "not set"],
				]
				# A "Both" item missing both codes is in both lists; count it once.
				n = (
					self._count("Item", goods_f)
					+ self._count("Item", services_f)
					- self._count("Item", both_f)
				)
				sample = {}
				for f in (goods_f, services_f) if n else ():
					for r in frappe.get_list(
						"Item", filters=f, fields=["name", "item_name"], order_by="name", limit=2
					):
						sample.setdefault(r.name, r.item_name or r.name)
				shown = list(sample.values())[:2]
				checks.append(
					{
						"key": "item_codes",
						"severity": "warn",
						"count": n,
						"names": {"shown": shown, "more": max(n - len(shown), 0)},
						"route": "/catalogue/items",
					}
				)

		result = checks if checks else None
		self._fix_cache = {"checks": result, "since": since}
		return result

	def _parties_without_trn(self, doctype: str, names: set[str]) -> set[str]:
		if not names:
			return set()
		rows = frappe.get_list(
			doctype,
			filters=[["name", "in", sorted(names)]],
			fields=["name", "tax_id"],
			limit_page_length=0,
		)
		from taxmate.uae.validation import is_valid_uae_trn

		return {r.name for r in rows if not is_valid_uae_trn(r.tax_id)}

	def _business_customers(self, names: set[str]) -> set[str]:
		"""Customers marked as companies — the ones a tax invoice needs a TRN for."""
		if not names:
			return set()
		return set(
			frappe.get_list(
				"Customer",
				filters=[["name", "in", sorted(names)], ["customer_type", "=", "Company"]],
				pluck="name",
				limit_page_length=0,
			)
		)

	def fixes(self) -> dict | None:
		checks = self._fixes()
		if checks is None:
			return None
		return {
			"since": str(self._fix_cache["since"]),
			"count": sum(c["count"] for c in checks),
			"checks": sorted(checks, key=lambda c: (c["count"] == 0, c["severity"] != "bad")),
		}

	# ── ageing by party (today) ──

	def party_ageing(self, doctype: str) -> dict | None:
		if not self._can(doctype):
			return None
		party = "customer" if doctype == "Sales Invoice" else "supplier"
		rows = frappe.get_list(
			doctype,
			filters=[
				["company", "=", self.company],
				["docstatus", "=", 1],
				["outstanding_amount", ">", 0],
				["is_opening", "!=", "Yes"],
			],
			fields=[
				party,
				f"{party}_name as label",
				"due_date",
				"party_account_currency",
				"conversion_rate",
				{"SUM": "outstanding_amount", "as": "v"},
			],
			group_by=f"{party}, due_date, party_account_currency, conversion_rate",
			order_by=party,
			limit_page_length=0,
		)
		data = ageing_by_party(
			[
				{
					"party": r[party],
					"label": r.label,
					"due_date": r.due_date,
					"v": self._in_company_currency(r),
				}
				for r in rows
			],
			self.on,
		)
		return data

	# ── e-invoicing (this calendar month) ──

	def einvoice(self) -> dict | None:
		if not self._can(_EINV_LOG):
			return None
		start = self.on.replace(day=1)
		counts = frappe.get_list(
			_EINV_LOG,
			filters=[["company", "=", self.company], ["creation", ">=", start]],
			fields=["status", {"COUNT": "*", "as": "n"}],
			group_by="status",
			order_by="status",
			limit_page_length=0,
		)
		by = {r.status: cint(r.n) for r in counts}
		issues = frappe.get_list(
			_EINV_LOG,
			filters=[["company", "=", self.company], ["status", "in", ["Rejected", "Failed"]]],
			fields=[
				"name",
				"status",
				"reference_doctype",
				"reference_name",
				"error_message",
				"retry_count",
				"modified",
			],
			order_by="modified desc",
			limit=4,
		)
		return {
			"accepted": by.get("Accepted", 0),
			"pending": sum(by.get(s, 0) for s in ("Draft", "Generated", "Queued", "Submitted")),
			"rejected": by.get("Rejected", 0),
			"failed": by.get("Failed", 0),
			"issues": [
				{
					"log": r.name,
					"status": r.status,
					"doctype": r.reference_doctype,
					"name": r.reference_name,
					"error": (r.error_message or "").strip()[:240],
					"retries": cint(r.retry_count),
					# The background job retries Failed up to 5 times; Rejected never.
					"auto_retry": r.status == "Failed" and cint(r.retry_count) < 5,
				}
				for r in issues
			],
		}

	# ── recent activity ──

	def activity(self) -> list[dict]:
		rows: list[dict] = []
		for doctype in _ACTIVITY_DOCTYPES:
			if not self._can(doctype):
				continue
			party = {
				"Sales Invoice": "customer_name",
				"Purchase Invoice": "supplier_name",
				"Payment Entry": "party_name",
			}.get(doctype)
			amount = {
				"Sales Invoice": "base_grand_total",
				"Purchase Invoice": "base_grand_total",
				"Payment Entry": "base_paid_amount",
				"Journal Entry": "total_debit",
			}[doctype]
			fields = [
				"name",
				"docstatus",
				"amended_from",
				"modified",
				"modified_by",
				"posting_date",
				amount + " as amount",
			]
			if party:
				fields.append(party + " as party")
			for r in frappe.get_list(
				doctype,
				filters=[["company", "=", self.company], ["docstatus", ">", 0]],
				fields=fields,
				order_by="modified desc",
				limit=8,
			):
				rows.append({**r, "doctype": doctype})
		rows.sort(key=lambda r: r["modified"], reverse=True)
		filed = self.filed_returns()
		users: dict[str, str] = {}
		out = []
		for r in rows[:8]:
			uid = r["modified_by"]
			if uid not in users:
				users[uid] = frappe.db.get_value("User", uid, "full_name") or uid
			posting = getdate(r["posting_date"]) if r.get("posting_date") else None
			f = filed_period_for(posting, filed)
			out.append(
				{
					"doctype": r["doctype"],
					"name": r["name"],
					"verb": activity_verb(r["docstatus"], r.get("amended_from")),
					"when": str(r["modified"]),
					"user": users[uid],
					"party": r.get("party"),
					"amount": round(flt(r.get("amount")), 2),
					"posting_date": str(posting) if posting else None,
					"in_filed_period": f["name"] if f else None,
					"frozen": bool(self.frozen_till and posting and posting <= self.frozen_till),
				}
			)
		return out

	# ── compliance calendar ──

	def calendar(self) -> list[dict]:
		out: list[dict] = []
		for doctype, kind, amount_field in ((_VAT_LOG, "vat", "net_vat_due"), (_CT_LOG, "ct", "tax_payable")):
			if not self._can(doctype):
				continue
			meta = frappe.get_meta(doctype)
			if not meta.has_field(amount_field):
				amount_field = "name"
			# UAE CT Filing Log has no ``status`` field (only deadline_status).
			status_field = ["status"] if meta.has_field("status") else []
			for r in frappe.get_list(
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
					*status_field,
					amount_field,
				],
				order_by="filing_due_date asc",
				limit=3,
			):
				row = _filing_row(r, self.on, amount_field)
				row["kind"] = kind
				row["draft_status"] = r.status
				out.append(row)
		out.sort(key=lambda r: r["due_date"])
		out = out[:3]

		if self._can(_UBO):
			u = frappe.get_list(
				_UBO,
				filters=[["company", "=", self.company]],
				fields=["name", "status", "last_reviewed_on"],
				order_by="modified desc",
				limit=1,
			)
			if u:
				owners = len(frappe.get_doc(_UBO, u[0].name).get("beneficial_owners") or [])
				out.append(
					{
						"kind": "ubo",
						"name": u[0].name,
						"status": u[0].status,
						"last_reviewed": str(u[0].last_reviewed_on) if u[0].last_reviewed_on else None,
						"owners": owners,
					}
				)

		try:
			from taxmate.uae.readiness import get_uae_readiness_checklist

			data = get_uae_readiness_checklist(self.company)
		except frappe.PermissionError:
			data = None
		if data and data.get("applicable"):
			items = data.get("items") or []
			out.append(
				{
					"kind": "readiness",
					"done": sum(1 for i in items if i.get("ok")),
					"total": len(items),
					"missing": [i.get("label") for i in items if not i.get("ok")][:2],
				}
			)
		return out


def _first_names(names: list[str], n: int = 2) -> dict:
	seen: list[str] = []
	for x in names:
		if x and x not in seen:
			seen.append(x)
	return {"shown": seen[:n], "more": max(len(seen) - n, 0)}
