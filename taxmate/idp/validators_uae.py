# Copyright (c) 2026, Ascra Technologies and contributors
# For license information, please see license.txt

"""UAE invoice field checks and confidence scores (flag only)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

# IBR-132-AE: 15 digits, starts with 1, ends with 03.
_TRN_RE = re.compile(r"^1\d{12}03$")
_ISO_CURRENCIES = frozenset(
	{
		"AED",
		"USD",
		"EUR",
		"GBP",
		"SAR",
		"INR",
		"CNY",
		"JPY",
		"CHF",
		"CAD",
		"AUD",
		"KWD",
		"BHD",
		"OMR",
		"QAR",
	}
)


def _num(value: Any) -> float | None:
	if value is None or value == "":
		return None
	try:
		return float(str(value).replace(",", "").strip())
	except (TypeError, ValueError):
		return None


def _parse_date(value: Any) -> date | None:
	if value is None or value == "":
		return None
	text = str(value).strip()[:10]
	for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
		try:
			return datetime.strptime(text, fmt).date()
		except ValueError:
			continue
	return None


def validate_trn(trn: Any) -> tuple[bool, str | None]:
	text = str(trn or "").strip()
	if not text:
		return False, "missing"
	if not _TRN_RE.match(text):
		return False, "trn_format"
	return True, None


def validate_vat_amount(net: Any, vat: Any, rate: float = 0.05) -> tuple[bool, str | None]:
	n = _num(net)
	v = _num(vat)
	if n is None or v is None:
		return False, "missing"
	if abs(v) < 1e-9:
		return True, None
	expected = round(n * rate, 2)
	if abs(expected - round(v, 2)) > 0.05:
		return False, "vat_math"
	return True, None


def validate_totals(net: Any, vat: Any, grand: Any) -> tuple[bool, str | None]:
	n, v, g = _num(net), _num(vat), _num(grand)
	if None in (n, v, g):
		return False, "missing"
	if abs((n + v) - g) > 0.05:
		return False, "total_mismatch"
	return True, None


def validate_bill_date(value: Any, *, today: date | None = None) -> tuple[bool, str | None]:
	d = _parse_date(value)
	if d is None:
		return False, "date_unparseable"
	today = today or date.today()
	if d > today + timedelta(days=2):
		return False, "date_future"
	return True, None


def validate_currency(code: Any) -> tuple[bool, str | None]:
	text = str(code or "").strip().upper()
	if not text:
		return False, "missing"
	if text not in _ISO_CURRENCIES:
		return False, "currency_unknown"
	return True, None


def score_fields(
	header: dict[str, Any],
	*,
	ocr_confidence: float | None = None,
	used_llm: bool = False,
) -> dict[str, Any]:
	base = 0.55 if used_llm else 0.7
	if ocr_confidence is not None:
		base = 0.4 * base + 0.6 * float(ocr_confidence)

	checks = {
		"supplier_trn": validate_trn(header.get("supplier_trn") or header.get("tax_id")),
		"bill_date": validate_bill_date(header.get("bill_date") or header.get("posting_date")),
		"currency": validate_currency(header.get("currency")),
		"tax_total": validate_vat_amount(
			header.get("net_total"),
			header.get("tax_total") or header.get("total_taxes_and_charges"),
		),
		"grand_total": validate_totals(
			header.get("net_total"),
			header.get("tax_total") or header.get("total_taxes_and_charges") or 0,
			header.get("grand_total"),
		),
	}
	out: dict[str, Any] = {}
	for field, (ok, flag) in checks.items():
		conf = base if ok else max(0.15, base - 0.35)
		out[field] = {"confidence": round(conf, 3), "ok": ok, "flag": flag}
	bill_no = str(header.get("bill_no") or "").strip()
	out["bill_no"] = {
		"confidence": round(base if bill_no else 0.2, 3),
		"ok": bool(bill_no),
		"flag": None if bill_no else "missing",
	}
	return out


def attach_confidence(extracted: dict[str, Any]) -> dict[str, Any]:
	header = (extracted.get("extracted_data") or {}).get("header") or {}
	scores = score_fields(
		header,
		ocr_confidence=extracted.get("confidence"),
		used_llm=bool(extracted.get("used_llm")),
	)
	extracted["field_confidence"] = scores
	flags = [f"{k}:{v['flag']}" for k, v in scores.items() if v.get("flag")]
	if flags:
		warnings = (extracted.get("validation") or {}).setdefault("warnings", [])
		warnings.append(
			{"field": "", "message": "uae_checks:" + ",".join(flags), "severity": "warning"}
		)
	return extracted
