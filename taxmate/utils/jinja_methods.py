"""Print-language helpers. Registered from hooks.jinja for the invoice and worksheet templates."""

from __future__ import annotations

import re

import frappe

from taxmate.uae_e_invoicing.constants import CREDIT_NOTE_REASON_CODES, credit_note_reason_code

_ARABIC = re.compile(r"[\u0600-\u06FF]")

# Print labels for the stored BTAE-03 codes. The e-invoice payload keeps the code.
_REASON_AR = {
	"SUPPLY_CANCELLED": "إلغاء التوريد",
	"TAX_TREATMENT_CHANGED": "تغيير المعاملة الضريبية",
	"CONSIDERATION_ALTERED": "تعديل المقابل",
	"GOODS_OR_SERVICES_RETURNED": "إعادة السلع أو الخدمات",
	"TAX_APPLIED_IN_ERROR": "تطبيق الضريبة بالخطأ",
	"VOLUME_DISCOUNT": "خصم كمية",
}

_STATUS_AR = {
	"Draft": "مسودة",
	"Generated": "تم الإنشاء",
	"Queued": "في الانتظار",
	"Submitted": "مقدّم",
	"Accepted": "مقبول",
	"Rejected": "مرفوض",
	"Failed": "فشل",
	"Cancelled": "ملغى",
}


def _text(value) -> str:
	if value is None:
		return ""
	return str(value).strip()


def tm_is_arabic() -> bool:
	"""True when this print request is Arabic. The Jinja frappe.lang value is a cached snapshot."""
	return str(getattr(frappe.local, "lang", "") or "").startswith("ar")


def tm_name(stored, arabic=None) -> str:
	"""Arabic print uses the Arabic party or address text when it is not blank."""
	arabic_text = _text(arabic)
	stored_text = _text(stored)
	if tm_is_arabic() and arabic_text:
		return arabic_text
	return stored_text


def tm_line(primary, secondary=None, arabic=None) -> str:
	"""On an Arabic print, use Arabic text saved on the row. Otherwise keep the stored English value."""
	arabic_text = _text(arabic)
	primary_text = _text(primary)
	secondary_text = _text(secondary)
	if tm_is_arabic():
		if arabic_text:
			return arabic_text
		for value in (primary_text, secondary_text):
			if value and _ARABIC.search(value):
				return value
	return primary_text or secondary_text


def tm_reason(raw) -> str:
	"""Credit-note reason in the print language. Unknown text is printed as stored."""
	code = credit_note_reason_code(None if raw is None else str(raw))
	if not code:
		return _text(raw)
	if tm_is_arabic():
		return _REASON_AR.get(code) or CREDIT_NOTE_REASON_CODES[code]
	return CREDIT_NOTE_REASON_CODES[code]


def tm_status(raw) -> str:
	"""E-invoice status in the print language. Unknown text is printed as stored."""
	text = _text(raw)
	if tm_is_arabic():
		return _STATUS_AR.get(text) or text
	return text
