"""Translate ledger labels with Frappe ``_()``.

Account ids look like ``Sales - XSm``. That id is what General Ledger
filters and row links use, so it stays in English. The visible label
translates the account name and keeps the company abbreviation.

A name such as ``Petty Cash - Others`` is a whole chart label, not an
abbreviation. An exact catalog hit wins over the abbreviation split.
"""

from __future__ import annotations

import re

from frappe import _

_ABBR = re.compile(r" - ([A-Za-z0-9]{2,8})$")


def ledger_label(text: str | None) -> str | None:
	"""Return the current-language label for a chart string."""
	if not isinstance(text, str):
		return text
	raw = text.strip()
	if len(raw) >= 2 and raw[0] == raw[-1] == "'":
		raw = raw[1:-1].strip()
	if not raw:
		return text
	full = _(raw)
	if full != raw:
		return full
	match = _ABBR.search(raw)
	if match:
		head = raw[: match.start()]
		translated = _(head)
		if translated != head:
			return f"{translated} - {match.group(1)}"
	return raw


def account_display(account: str | None, acc_name: str | None) -> str | None:
	"""Label for the Account column. Does not replace the account id."""
	if not isinstance(account, str):
		return None
	raw = account.strip()
	if not raw:
		return None
	if len(raw) >= 2 and raw[0] == raw[-1] == "'":
		return ledger_label(raw)
	if not isinstance(acc_name, str) or not acc_name.strip():
		return None
	name = acc_name.strip()
	if raw == name:
		return ledger_label(name)
	match = _ABBR.search(raw)
	if match and raw[: match.start()] == name:
		return f"{ledger_label(name)} - {match.group(1)}"
	return None


def localize_report(report_name: str, result: dict) -> dict:
	"""Add the translated heading and account labels.

	``account``, ``parent_account``, and ``voucher_type`` stay as stored.
	The first two are document names; the last one is how a row opens
	its invoice or payment.
	"""
	result["report_label"] = _(report_name)
	columns = result.get("columns")
	if isinstance(columns, list):
		for col in columns:
			if isinstance(col, dict) and isinstance(col.get("label"), str):
				col["label"] = _(col["label"])
	rows = result.get("result")
	if isinstance(rows, list):
		for row in rows:
			if not isinstance(row, dict):
				continue
			acc_name = row.get("acc_name")
			name = acc_name if isinstance(acc_name, str) else None
			account = row.get("account") if isinstance(row.get("account"), str) else None
			label = account_display(account, name)
			if label:
				row["account_label"] = label
			if name:
				row["acc_name"] = ledger_label(name)
	return result
