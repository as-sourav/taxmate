"""Consent-based related masters for Scan create.

Unattended inventing stays off. The clerk confirms each proposal, then
TaxMate inserts UOM, Supplier, Customer, and Item (and Address) before the draft.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from taxmate.uae.constants import UAE_EMIRATES

# Links the scan may create after the clerk confirms. Everything else blocks.
CREATABLE: frozenset[str] = frozenset({"UOM", "Supplier", "Customer", "Item"})
EMIRATES: tuple[str, ...] = tuple(UAE_EMIRATES)

_PARTY_LABEL: dict[str, str] = {
	"supplier": "idp.field.supplier",
	"customer": "f.customer",
	"supplier_name": "idp.field.supplier",
	"customer_name": "f.customer",
}

_PARTY_LINK: dict[str, str] = {
	"Supplier": "supplier",
	"Customer": "customer",
}

_FIELD_TO_DOCTYPE: dict[str, str] = {
	"supplier": "Supplier",
	"customer": "Customer",
	"item_code": "Item",
	"item": "Item",
}

# Target doctype → party Link (mirrors taxmate.idp.desk.PARTY_FIELD for creatable parties).
_PARTY_BY_DOCTYPE: dict[str, str] = {
	"Sales Invoice": "customer",
	"Purchase Invoice": "supplier",
	"Sales Order": "customer",
	"Purchase Order": "supplier",
	"Delivery Note": "customer",
	"Purchase Receipt": "supplier",
	"Supplier Quotation": "supplier",
}

_SUPPLIER_ALIASES: tuple[str, ...] = (
	"supplier",
	"supplier_name",
	"vendor",
	"seller",
	"seller_name",
	"bill_from",
	"sold_by",
	"from",
	"supplier_address_title",
	# Invoice PDFs often print the issuer only as the bank beneficiary.
	"account_name",
	"beneficiary",
	"beneficiary_name",
	"company_name",
	"remitter",
)
_CUSTOMER_ALIASES: tuple[str, ...] = (
	"customer",
	"customer_name",
	"buyer",
	"client",
	"bill_to",
	"sold_to",
	"ship_to",
	"customer_address_title",
)
_SELLER_ADDRESS_ALIASES: tuple[str, ...] = (
	"supplier_address",
	"seller_address",
	"vendor_address",
	"company_address",
	"from_address",
	"remitter_address",
)
_BUYER_ADDRESS_ALIASES: tuple[str, ...] = (
	"billing_address",
	"customer_address",
	"bill_to_address",
	"buyer_address",
	"ship_to_address",
	"bill_address",
)
_ADDRESS_ALIASES: tuple[str, ...] = (
	_SELLER_ADDRESS_ALIASES + _BUYER_ADDRESS_ALIASES + ("address", "address_line1")
)
_PHONE_ALIASES: tuple[str, ...] = ("phone", "mobile_no", "mobile", "tel", "telephone", "contact_number")
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
	"bill_no": ("invoice_number", "invoice_no", "bill_number", "inv_no", "bill_no"),
	"posting_date": ("date", "invoice_date", "bill_date", "posting_date"),
	"transaction_date": ("date", "order_date", "po_date", "transaction_date"),
	"grand_total": ("total", "total_amount", "grand_total", "amount_due", "total_due"),
	"net_total": ("subtotal", "sub_total", "net_total", "net_amount", "total_due"),
	"currency": ("currency",),
	"tax_id": ("tax_id", "trn", "vat_number", "supplier_trn", "customer_trn", "gstin"),
}


def salvage_from_ocr_text(extracted: dict[str, Any], ocr_text: str | None) -> None:
	"""Fill gaps the LLM left using the raw OCR text (UAE tax-invoice layout)."""
	if not extracted.get("success") or not ocr_text:
		return
	data = extracted.get("extracted_data")
	if not isinstance(data, dict):
		return
	header = data.get("header")
	if not isinstance(header, dict):
		return
	doctype = str(data.get("doctype") or "")
	body = ocr_text.replace("\r", "")
	if "\\n" in body and body.count("\n") < 2:
		body = body.replace("\\n", "\n").replace("\\t", "\t")
	_fill_printed_header(header, body, doctype)

	if doctype.startswith("Purchase") or doctype == "Supplier Quotation":
		if not str(header.get("supplier") or "").strip():
			m = re.search(r"Account\s*Name\s*[-\u2013:]\s*(.+)", body, re.IGNORECASE)
			if m:
				header["supplier"] = m.group(1).strip().split("\n")[0].strip()
				header.setdefault("account_name", header["supplier"])
		if not str(header.get("address_line1") or header.get("seller_address") or "").strip():
			# Letterhead block sits above "Bill To" on most UAE tax invoices.
			m = re.search(r"^(.+?)Bill\s*To\s*:", body, re.IGNORECASE | re.DOTALL)
			if m:
				block = m.group(1)
				lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
				addr_lines = [
					ln
					for ln in lines
					if not re.fullmatch(r"\+?\d[\d\s-]{7,}", ln)
					and "tax invoice" not in ln.lower()
					and len(ln) > 8
				]
				picked = [
					ln
					for ln in addr_lines
					if re.search(r"PO Box|Park|Street|Road|Dubai|Abu|Sharjah|UAE|Emirates", ln, re.I)
				]
				if picked:
					raw_addr = re.sub(r"\s+", " ", ", ".join(picked[:3])).strip()
					# Never assign free text to Link field supplier_address.
					header["seller_address"] = raw_addr
					line1, city, state = _split_address(raw_addr)
					header["address_line1"] = line1 or raw_addr
					if city and not header.get("city"):
						header["city"] = city
					if state:
						header["state"] = state
						header["vat_emirate"] = state
		if not str(header.get("phone") or "").strip():
			m = re.search(r"(\+\d[\d\s-]{7,20}\d)", body)
			if m:
				header["phone"] = re.sub(r"[\s-]+", " ", m.group(1)).strip()

	if doctype.startswith("Sales") or doctype in ("Quotation", "Delivery Note"):
		if not str(header.get("customer") or "").strip():
			m = re.search(r"Bill\s*To\s*:\s*(.+)", body, re.IGNORECASE)
			if m:
				header["customer"] = m.group(1).strip().split("\n")[0].strip()

	items = data.get("items") if isinstance(data.get("items"), list) else []
	supplier_hint = str(header.get("supplier") or header.get("account_name") or "").strip().lower()
	parsed_lines = (
		_parse_tax_invoice_lines(body)
		or _parse_coded_tax_lines(body)
		or _parse_plain_tax_lines(body)
		or _parse_code_amount_lines(body)
	)
	bad = not items
	for row in items:
		if not isinstance(row, dict):
			continue
		label = str(row.get("item_name") or row.get("description") or "").strip().lower()
		if not label:
			bad = True
			break
		# LLM often parks the issuer letterhead on the only item row.
		if supplier_hint and (supplier_hint in label or label in supplier_hint):
			bad = True
			break
		if (
			re.search(r"\bfzco\b|\bllc\b|\bl\.l\.c\b", label)
			and "device" not in label
			and "service" not in label
		):
			bad = True
			break
	current_rows = [row for row in items if isinstance(row, dict)]
	footer = _printed_footer(body)
	if parsed_lines and (
		_rows_match_footer(parsed_lines, footer)
		or bad
		or _rows_are_units(items)
		or len(parsed_lines) > len(current_rows)
	):
		data["items"] = parsed_lines
	elif bad:
		desc = ""
		for m in re.finditer(r"(?m)^(?P<line>.{20,180})$", body):
			line = re.sub(r"\s+", " ", m.group("line")).strip()
			lower = line.lower()
			if supplier_hint and (supplier_hint in lower or lower in supplier_hint):
				continue
			if any(
				tok in lower
				for tok in (
					"bank name",
					"iban",
					"swift",
					"subtotal",
					"total due",
					"tax invoice",
					"bill to",
					"thank you",
				)
			):
				continue
			if re.search(r"from\s+\d|device|service|license|subscription|orch", lower):
				desc = line
				break
		if not desc:
			m = re.search(
				r"Description\s*\n(.+?)(?:\n\s*(?:Quantity|SUBTOTAL|Bank Name|Unit Price)|$)",
				body,
				re.IGNORECASE | re.DOTALL,
			)
			if m:
				desc = re.sub(r"\s+", " ", m.group(1)).strip()
		if desc:
			qty = 1
			qm = re.search(r"Quantity\s*\n\s*(\d+)", body, re.IGNORECASE)
			if qm:
				qty = int(qm.group(1))
			rate = header.get("net_total") or header.get("grand_total") or header.get("total_due") or 0
			data["items"] = [
				{
					"item_name": desc,
					"description": desc,
					"qty": qty,
					"quantity": qty,
					"rate": rate,
					"unit_price": rate,
					"amount": rate,
					"uom": "Nos",
				}
			]
	_apply_pos_receipt(data, header, body, parsed_lines)
	if footer and not _retail_slip(body):
		_stamp_printed_footer(header, footer)


_POS_MONEY = r"\d{1,3}(?:,\d{3})*\.\d{2}"
_POS_ITEM = re.compile(
	rf"^\s*(?P<idx>\d{{1,3}})\s+(?P<body>.+?)\s+"
	rf"(?P<price>{_POS_MONEY})\s+(?P<qty>{_POS_MONEY})\s+(?P<amt>{_POS_MONEY})\s*$"
)
_POS_STOP = re.compile(
	r"net\s+amount|pay\s+by|item\s+count|sub\s*total|vat\s*%|\bvat\b",
	re.IGNORECASE,
)
_POS_BARCODE = re.compile(r"^\d{8,14}$")


def _apply_pos_receipt(
	data: dict[str, Any],
	header: dict[str, Any],
	body: str,
	tax_rows: list[dict[str, Any]],
) -> None:
	"""Retail slips print Price, Qty, Amt. A tax-invoice table already parsed wins."""
	if tax_rows or not _retail_slip(body):
		return
	rows, vat = _parse_pos_receipt(body)
	if not rows:
		return
	if not str(header.get("supplier") or "").strip():
		for line in body.splitlines():
			text = re.sub(r"\s+", " ", line).strip()
			if len(text) < 4 or re.fullmatch(r"[\d\W]+", text):
				continue
			if re.search(r"^(tel|trn|shop|tax invoice)\b", text, re.IGNORECASE):
				continue
			header["supplier"] = text
			break
	current = [row for row in (data.get("items") or []) if isinstance(row, dict)]
	if _prefer_pos_rows(current, rows):
		data["items"] = rows
		current = rows
	if vat:
		_apply_printed_vat(header, current, vat)


def _prefer_pos_rows(current: list[dict[str, Any]], parsed: list[dict[str, Any]]) -> bool:
	if not current or len(parsed) > len(current):
		return True
	return _price_stored_as_qty(current)


def _price_stored_as_qty(items: list[dict[str, Any]]) -> bool:
	"""Price landed in qty and the rate collapsed to 1."""
	rows = [row for row in items if isinstance(row, dict)]
	if not rows:
		return False
	hits = 0
	for row in rows:
		qty = float(row.get("qty") or 0)
		rate = float(row.get("rate") or 0)
		amount = float(row.get("amount") or 0)
		if abs(rate - 1) < 0.02 and qty > 1 and abs(amount - qty) < 0.05:
			hits += 1
	return hits == len(rows)


def _parse_pos_receipt(body: str) -> tuple[list[dict[str, Any]], dict[str, float] | None]:
	rows: list[dict[str, Any]] = []
	lines = body.splitlines()
	index = 0
	while index < len(lines):
		match = _POS_ITEM.match(lines[index].strip())
		if not match:
			index += 1
			continue
		parts = [match.group("body").strip()]
		price = _money(match.group("price"))
		qty = _money(match.group("qty")) or 1
		amount = _money(match.group("amt"))
		index += 1
		while index < len(lines):
			nxt = lines[index].strip()
			if not nxt or _POS_ITEM.match(nxt) or _POS_STOP.search(nxt) or _POS_BARCODE.match(nxt):
				if _POS_BARCODE.match(nxt):
					index += 1
				break
			parts.append(nxt)
			index += 1
		name = re.sub(r"\s+", " ", " ".join(parts)).strip(" -")
		if not name or price < 0 or qty <= 0:
			continue
		rows.append(
			{
				"item_name": name,
				"description": name,
				"qty": qty,
				"quantity": qty,
				"rate": price,
				"unit_price": price,
				"amount": amount or round(price * qty, 2),
				"uom": "Nos",
			}
		)
	return rows, _pos_vat(body)


def _retail_slip(body: str) -> bool:
	"""A shop receipt names Price, Qty, and Amt. A tax invoice names Taxable Amt."""
	if re.search(r"taxable\s+amt", body, re.IGNORECASE):
		return False
	return bool(re.search(r"\bprice\b.+\bqty\b.+\bamt\b", body, re.IGNORECASE | re.DOTALL))


def _pos_vat(body: str) -> dict[str, float] | None:
	lines = body.splitlines()
	amount_only = re.compile(rf"^(?:{_POS_MONEY}\s+){{3}}{_POS_MONEY}$")
	for index, line in enumerate(lines):
		if not re.search(r"vat", line, re.IGNORECASE):
			continue
		nums = re.findall(_POS_MONEY, line)
		if len(nums) < 4 and index + 1 < len(lines) and amount_only.match(lines[index + 1].strip()):
			nums = re.findall(_POS_MONEY, lines[index + 1])
		if len(nums) < 4:
			continue
		rate, net, vat, gross = (_money(token) for token in nums[:4])
		if gross <= 0 or vat < 0 or net <= 0:
			continue
		if abs(round(net + vat, 2) - gross) > 0.05:
			continue
		return {"rate": rate, "net": net, "vat": vat, "gross": gross}
	return None


def _apply_printed_vat(
	header: dict[str, Any],
	items: list[dict[str, Any]],
	vat: dict[str, float],
) -> None:
	"""Shelf prices on a tax invoice are VAT-inclusive. The draft stores the net."""
	header["net_total"] = vat["net"]
	header["grand_total"] = vat["gross"]
	header["tax_total"] = vat["vat"]
	header["total_taxes_and_charges"] = vat["vat"]
	priced = [row for row in items if isinstance(row, dict)]
	total = round(sum(float(row.get("amount") or 0) for row in priced), 2)
	if not priced or abs(total - vat["gross"]) > 0.05 or abs(total - vat["net"]) <= 0.02:
		return
	running = 0.0
	for row in priced[:-1]:
		amount = round(float(row.get("amount") or 0) * vat["net"] / vat["gross"], 2)
		qty = float(row.get("qty") or 1) or 1
		row["amount"] = amount
		row["rate"] = round(amount / qty, 2)
		row["unit_price"] = row["rate"]
		running += amount
	last = priced[-1]
	amount = round(vat["net"] - running, 2)
	qty = float(last.get("qty") or 1) or 1
	last["amount"] = amount
	last["rate"] = round(amount / qty, 2)
	last["unit_price"] = last["rate"]


# Printed units that a column scan must not treat as the product.
_UNIT_TOKENS: frozenset[str] = frozenset(
	{
		"btl",
		"btls",
		"bottle",
		"bottles",
		"cup",
		"cups",
		"pkt",
		"pkts",
		"packet",
		"packets",
		"tub",
		"tubs",
		"tray",
		"trays",
		"nos",
		"pcs",
		"pc",
		"piece",
		"pieces",
		"kg",
		"gm",
		"gms",
		"ltr",
		"ml",
		"box",
		"boxes",
		"ctn",
		"carton",
		"cartons",
		"set",
		"pair",
		"dozen",
		"unit",
		"units",
		"bag",
		"bags",
		"can",
		"cans",
		"roll",
		"rolls",
		"pack",
		"packs",
	}
)

_TAX_LINE = re.compile(
	r"^\s*(?P<idx>\d{1,3})\s+"
	r"(?P<code>[A-Z][A-Z0-9-]{2,})\s+"
	r"(?P<body>.+?)\s+"
	r"(?P<qty>\d+(?:\.\d+)?)\s+"
	r"(?P<uom>[A-Za-z]{2,12})\s+"
	r"(?P<rate>\d[\d,]*\.\d{2})\s+"
	r"(?P<disc>-|—|\d[\d,]*\.\d{2})\s+"
	r"(?P<taxable>\d[\d,]*\.\d{2})\s+"
	r"(?P<vat>\d[\d,]*\.\d{2})\s+"
	r"(?P<total>\d[\d,]*\.\d{2})\s*$"
)


def _unit_token(value: str) -> bool:
	token = re.sub(r"[^A-Za-z]", "", value or "").lower()
	return bool(token) and token in _UNIT_TOKENS


def _rows_are_units(items: list[Any]) -> bool:
	"""True when the extract parked the UOM column in the item name."""
	labels: list[str] = []
	for row in items:
		if not isinstance(row, dict):
			continue
		label = str(row.get("item_name") or row.get("item_code") or "").strip()
		if label:
			labels.append(label)
	if len(labels) < 2:
		return False
	hits = sum(1 for label in labels if _unit_token(label))
	return hits >= max(2, (len(labels) + 1) // 2)


def _money(token: str) -> float:
	text = str(token or "").strip()
	if text in {"", "-", "—"}:
		return 0.0
	return float(text.replace(",", ""))


def _parse_tax_invoice_lines(body: str) -> list[dict[str, Any]]:
	"""Read a # / code / description / qty / UOM / rate / discount / taxable / VAT / total table."""
	rows: list[dict[str, Any]] = []
	seen: set[str] = set()
	for line in body.splitlines():
		match = _TAX_LINE.match(line)
		if not match:
			continue
		code = match.group("code").strip()
		if code in seen or _unit_token(code):
			continue
		qty = _money(match.group("qty"))
		rate = _money(match.group("rate"))
		disc = _money(match.group("disc"))
		taxable = _money(match.group("taxable"))
		vat = _money(match.group("vat"))
		total = _money(match.group("total"))
		if qty <= 0 or rate < 0:
			continue
		net = round(qty * rate - disc, 2)
		if abs(net - taxable) > 0.05 and abs(round(taxable + vat, 2) - total) > 0.05:
			continue
		name = re.sub(r"\s+", " ", match.group("body")).strip(" -")
		uom = match.group("uom").strip()
		row: dict[str, Any] = {
			"item_code": code,
			"item_name": name or code,
			"description": name or code,
			"qty": qty,
			"quantity": qty,
			"uom": uom,
			"stock_uom": uom,
			"rate": rate,
			"unit_price": rate,
			"amount": taxable,
			"conversion_factor": 1,
			"stock_qty": qty,
			"base_rate": rate,
			"base_amount": taxable,
		}
		if disc > 0:
			row["discount_amount"] = disc
		rows.append(row)
		seen.add(code)
	return rows if len(rows) >= 2 else []


_TABLE_MONEY = r"\d[\d,]*\.\d{2}"
_CODED_TAX = re.compile(
	rf"^\s*(?P<idx>\d{{1,3}})\s+"
	rf"(?P<code>[A-Z][A-Z0-9-]{{2,}})\s+"
	rf"(?P<body>.+?)\s+"
	rf"(?P<qty>\d+(?:\.\d+)?)\s+"
	rf"(?P<uom>[A-Za-z]{{2,12}})\s+"
	rf"(?P<rate>{_TABLE_MONEY})\s+"
	rf"(?P<taxable>{_TABLE_MONEY})\s+"
	rf"(?P<vat>{_TABLE_MONEY})\s+"
	rf"(?P<total>{_TABLE_MONEY})\s*$"
)
_PLAIN_TAX = re.compile(
	rf"^\s*(?P<idx>\d{{1,3}})\s+"
	rf"(?P<body>.+?)\s+"
	rf"(?P<qty>\d+(?:\.\d+)?)\s+"
	rf"(?P<uom>[A-Za-z]{{2,12}})\s+"
	rf"(?P<rate>{_TABLE_MONEY})\s+"
	rf"(?P<taxable>{_TABLE_MONEY})\s+"
	rf"(?P<vat>{_TABLE_MONEY})\s+"
	rf"(?P<total>{_TABLE_MONEY})\s*$"
)
_CODE_AMOUNT = re.compile(
	rf"^\s*(?P<code>[A-Z][A-Z0-9-]{{2,}})\s+"
	rf"(?P<body>.+?)\s+"
	rf"(?P<qty>\d+(?:\.\d+)?)\s+"
	rf"(?P<rate>{_TABLE_MONEY})\s+"
	rf"(?P<amt>{_TABLE_MONEY})\s*$"
)
_TABLE_STOP = re.compile(
	r"total\s+taxable|grand\s+total|vat\s*@|\bsubtotal\b|\btotal\s+aed\b|\bnotes\b|authorised",
	re.IGNORECASE,
)


def _parse_coded_tax_lines(body: str) -> list[dict[str, Any]]:
	"""# / code / description / qty / UOM / rate / taxable / VAT / total, with no discount column."""
	return _walk_tax_table(body, _CODED_TAX, coded=True)


def _parse_plain_tax_lines(body: str) -> list[dict[str, Any]]:
	"""# / description / qty / UOM / rate / taxable / VAT / total. Descriptions may wrap."""
	return _walk_tax_table(body, _PLAIN_TAX, coded=False)


def _parse_code_amount_lines(body: str) -> list[dict[str, Any]]:
	"""Item code, description, qty, rate, amount. VAT sits in the footer, not on the line."""
	if not re.search(r"\bItem Code\b", body):
		return []
	rows: list[dict[str, Any]] = []
	seen: set[str] = set()
	lines = body.splitlines()
	index = 0
	while index < len(lines):
		match = _CODE_AMOUNT.match(lines[index])
		if not match:
			index += 1
			continue
		code = match.group("code").strip()
		parts = [match.group("body").strip()]
		qty = _money(match.group("qty"))
		rate = _money(match.group("rate"))
		amount = _money(match.group("amt"))
		index += 1
		while index < len(lines):
			nxt = lines[index]
			if (
				not nxt.strip()
				or _CODE_AMOUNT.match(nxt)
				or _TABLE_STOP.search(nxt)
			):
				break
			parts.append(nxt.strip())
			index += 1
		if code in seen or qty <= 0 or abs(round(qty * rate, 2) - amount) > 0.05:
			continue
		seen.add(code)
		name = re.sub(r"\s+", " ", " ".join(parts)).strip(" -")
		rows.append(_exclusive_row(code=code, name=name, qty=qty, uom="Nos", rate=rate, amount=amount))
	return rows if len(rows) >= 2 else []


def _walk_tax_table(body: str, pattern: re.Pattern[str], *, coded: bool) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	seen: set[str] = set()
	lines = body.splitlines()
	index = 0
	while index < len(lines):
		match = pattern.match(lines[index])
		if not match:
			index += 1
			continue
		parts = [match.group("body").strip()]
		code = match.group("code").strip() if coded else ""
		qty = _money(match.group("qty"))
		uom = match.group("uom").strip()
		rate = _money(match.group("rate"))
		taxable = _money(match.group("taxable"))
		vat = _money(match.group("vat"))
		total = _money(match.group("total"))
		index += 1
		while index < len(lines):
			nxt = lines[index]
			if not nxt.strip() or pattern.match(nxt) or _TABLE_STOP.search(nxt) or _CODE_AMOUNT.match(nxt):
				break
			parts.append(nxt.strip())
			index += 1
		if qty <= 0 or not _line_agrees(qty, rate, taxable, vat, total):
			continue
		if coded and (not code or code in seen or _unit_token(code)):
			continue
		name = re.sub(r"\s+", " ", " ".join(parts)).strip(" -")
		if coded:
			seen.add(code)
		rows.append(_exclusive_row(code=code, name=name, qty=qty, uom=uom, rate=rate, amount=taxable))
	return rows if len(rows) >= 2 else []


def _line_agrees(qty: float, rate: float, taxable: float, vat: float, total: float) -> bool:
	if abs(round(qty * rate, 2) - taxable) <= 0.05:
		return True
	return abs(round(taxable + vat, 2) - total) <= 0.05


def _exclusive_row(
	*,
	code: str,
	name: str,
	qty: float,
	uom: str,
	rate: float,
	amount: float,
) -> dict[str, Any]:
	label = name or code
	row: dict[str, Any] = {
		"item_name": label,
		"description": label,
		"qty": qty,
		"quantity": qty,
		"uom": uom or "Nos",
		"stock_uom": uom or "Nos",
		"rate": rate,
		"unit_price": rate,
		"amount": amount,
		"conversion_factor": 1,
		"stock_qty": qty,
		"base_rate": rate,
		"base_amount": amount,
	}
	if code:
		row["item_code"] = code
	return row


def _printed_footer(body: str) -> dict[str, float] | None:
	"""Printed taxable, VAT, and grand total. Each label is read from its own line."""
	layouts = (
		(
			r"Total\s+Taxable\s+Amount\s*:?\s*([\d,]+\.\d{2})",
			r"VAT\s*@\s*5%\s*:?\s*([\d,]+\.\d{2})",
			r"Grand\s+Total\s*\(AED\)\s*:?\s*([\d,]+\.\d{2})",
		),
		(
			r"\bSubtotal\s+([\d,]+\.\d{2})",
			r"\bVAT\s+5%\s+([\d,]+\.\d{2})",
			r"\bTOTAL\s+AED\s+([\d,]+\.\d{2})",
		),
	)
	for net_re, vat_re, grand_re in layouts:
		net = _line_money(body, net_re)
		vat = _line_money(body, vat_re)
		grand = _line_money(body, grand_re)
		if net is None or vat is None or grand is None:
			continue
		if grand <= 0 or abs(round(net + vat, 2) - grand) > 0.05:
			continue
		return {"net": net, "vat": vat, "grand": grand}
	return None


def _line_money(body: str, pattern: str) -> float | None:
	for line in body.splitlines():
		match = re.search(pattern, line, re.IGNORECASE)
		if match:
			return _money(match.group(1))
	return None


def _rows_match_footer(rows: list[dict[str, Any]], footer: dict[str, float] | None) -> bool:
	if not footer:
		return False
	total = round(sum(float(row.get("amount") or 0) for row in rows), 2)
	return abs(total - footer["net"]) <= 0.05


def _stamp_printed_footer(header: dict[str, Any], footer: dict[str, float]) -> None:
	header["net_total"] = footer["net"]
	header["grand_total"] = footer["grand"]
	header["tax_total"] = footer["vat"]
	header["total_taxes_and_charges"] = footer["vat"]


def _letterhead_name(body: str) -> str:
	match = re.search(
		r"(?m)^([A-Z][A-Za-z0-9&.,'()-]{2,}(?:\s+[A-Za-z0-9&.,'()-]+){0,8})\s{2,}TAX\s+INVOICE",
		body,
	)
	if match:
		return _with_trailing_llc(match.group(1), body[match.end() :])
	match = re.search(r"(?m)^([^\n]{4,80})\n[ \t]*TAX\s+INVOICE", body, re.IGNORECASE)
	if match and not re.search(r"\bTRN\b|\bTel\b", match.group(1), re.IGNORECASE):
		return _with_trailing_llc(match.group(1), body[match.end() :])
	banner = re.search(r"(?m)^\s*([A-Z][^|\n]{3,80}?)\s+LLC\s*\|", body)
	if banner:
		return re.sub(r"\s+", " ", banner.group(1)).strip() + " LLC"
	# The seller is the first company line above the tax-invoice title.
	lines = [line.strip() for line in body.splitlines() if line.strip()]
	for index, line in enumerate(lines[:8]):
		if "|" in line or not re.search(r"\bLLC\b|\bL\.L\.C\b", line, re.IGNORECASE):
			continue
		window = " ".join(lines[index : index + 6])
		if re.search(r"TAX\s+INVOICE", window, re.IGNORECASE):
			return re.sub(r"\s+", " ", line).strip()
	return ""


def _with_trailing_llc(name: str, rest: str) -> str:
	"""A wrapped letterhead prints LLC on the next line. Keep it on the supplier name."""
	clean = re.sub(r"\s+", " ", name).strip(" -")
	if re.search(r"\bLLC\b", clean, re.IGNORECASE):
		return clean
	for line in rest.splitlines():
		if not line.strip():
			continue
		if re.fullmatch(r"L\.?L\.?C\.?", line.strip(), re.IGNORECASE):
			return f"{clean} LLC"
		break
	return clean


def _letterhead_completes(current: str, letter: str) -> bool:
	"""The printed letterhead is the same party with the legal suffix the mapper dropped."""
	cur = re.sub(r"\s+", " ", current).strip().lower()
	full = re.sub(r"\s+", " ", letter).strip().lower()
	return bool(cur) and full.startswith(cur) and len(full) > len(cur)


def _bill_to_name(body: str) -> str:
	match = re.search(r"Bill\s*To\s*:?\s*\n+\s*(.+)", body, re.IGNORECASE)
	if not match:
		return ""
	return match.group(1).strip().split("\n")[0].strip()


def _split_trns(body: str) -> tuple[str, str]:
	parts = re.split(r"Bill\s*To", body, maxsplit=1, flags=re.IGNORECASE)

	def first(chunk: str) -> str:
		found = re.search(r"(?:TRN|Tax\s*Registration\s*Number)\s*:?\s*(1\d{14})", chunk)
		return found.group(1) if found else ""

	if len(parts) == 2:
		return first(parts[0]), first(parts[1])
	found = re.findall(r"(?:TRN|Tax\s*Registration\s*Number)\s*:?\s*(1\d{14})", body)
	seller = found[0] if found else ""
	buyer = found[1] if len(found) > 1 else ""
	return seller, buyer


def _fill_printed_header(header: dict[str, Any], body: str, doctype: str) -> None:
	"""Put printed seller, dates, currency, and totals on the header the draft will use."""
	# A VAT amount is not a Purchase Taxes and Charges Template link.
	tax_link = str(header.get("taxes_and_charges") or "").strip().replace(" ", "")
	if tax_link and re.fullmatch(r"[\d,.]+", tax_link):
		header.pop("taxes_and_charges", None)
	purchase = doctype.startswith("Purchase") or doctype == "Supplier Quotation"
	seller_trn, buyer_trn = _split_trns(body)
	if purchase:
		current = str(header.get("supplier") or "").strip()
		letter = _letterhead_name(body)
		bill_to = _bill_to_name(body)
		if letter and (
			not current
			or _unit_token(current)
			or (bill_to and current.lower() == bill_to.lower())
			or _letterhead_completes(current, letter)
		):
			header["supplier"] = letter
		tax = re.sub(r"\s+", "", str(header.get("tax_id") or ""))
		if seller_trn and (not tax or (buyer_trn and tax == buyer_trn)):
			header["tax_id"] = seller_trn
	if not str(header.get("currency") or "").strip() and re.search(r"\bAED\b|\(AED\)", body):
		header["currency"] = "AED"
	if not str(header.get("bill_no") or "").strip():
		match = re.search(r"Invoice\s*No\.?\s*:?\s*([A-Z0-9][A-Z0-9/-]*)", body, re.IGNORECASE)
		if not match:
			match = re.search(r"Invoice\s*#\D{0,40}(\d{3,})", body, re.IGNORECASE)
		if match:
			header["bill_no"] = match.group(1)
	if not str(header.get("posting_date") or "").strip():
		match = re.search(
			r"Invoice\s*Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-][A-Za-z]{3,9}[/-]\d{4})",
			body,
			re.IGNORECASE,
		)
		if not match:
			match = re.search(r"Date\s*Time\D{0,40}(\d{1,2}[/-]\d{1,2}[/-]\d{4})", body, re.IGNORECASE)
		if match:
			parsed = _parse_ocr_date(match.group(1))
			if parsed:
				header["posting_date"] = parsed
	if not str(header.get("due_date") or "").strip():
		match = re.search(
			r"Due\s*Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-][A-Za-z]{3,9}[/-]\d{4})",
			body,
			re.IGNORECASE,
		)
		if match:
			parsed = _parse_ocr_date(match.group(1))
			if parsed:
				header["due_date"] = parsed
	if not str(header.get("net_total") or "").strip():
		match = re.search(r"Total\s+Taxable\s+Amount\s+([\d,]+\.\d{2})", body, re.IGNORECASE)
		if match:
			header["net_total"] = _money(match.group(1))
	if not str(header.get("grand_total") or "").strip():
		match = re.search(r"Grand\s+Total\s*\(AED\)\s+([\d,]+\.\d{2})", body, re.IGNORECASE)
		if match:
			header["grand_total"] = _money(match.group(1))
	if not _emirate(header):
		head = body.split("Item Code", 1)[0]
		found = [name for name in EMIRATES if re.search(rf"\b{re.escape(name)}\b", head, re.IGNORECASE)]
		if len(found) == 1:
			header["vat_emirate"] = found[0]


def normalize_extract(extracted: dict[str, Any], *, promote_items: bool = True) -> None:
	"""Promote OCR/LLM aliases onto ERPNext Links before match and proposals.

	IDP often leaves bill_to / billing_address instead of supplier or customer.
	Without this pass, missing_masters stays empty and Scan never proposes create.

	Call with promote_items=False before item-name lookup so existing catalog
	rows still match; then call promote_unresolved_items afterward.
	"""
	if not extracted.get("success"):
		return
	data = extracted.get("extracted_data")
	if not isinstance(data, dict):
		return
	header = data.get("header")
	if not isinstance(header, dict):
		return
	doctype = str(data.get("doctype") or "")
	_promote_header_scalars(header, doctype)
	_promote_party(header, doctype)
	_promote_address(header, doctype)
	_promote_phone(header)
	_promote_totals(header)
	_scrub_contact_noise(header)
	_scrub_address_links(header)
	_sanitize_header_values(header)
	_sanitize_item_values(data)
	_ensure_line_from_total(data)
	if promote_items:
		items = data.get("items")
		if isinstance(items, list):
			promote_unresolved_items(items)


def promote_unresolved_items(items: list[Any]) -> None:
	"""After name lookup, copy printed names onto item_code so Link checks can propose create."""
	_promote_item_codes(items)


def _promote_header_scalars(header: dict[str, Any], doctype: str) -> None:
	for field, aliases in _HEADER_ALIASES.items():
		if field in ("posting_date", "transaction_date"):
			# Prefer the date field the target DocType uses.
			if doctype.startswith("Purchase Order") or doctype in (
				"Sales Order",
				"Quotation",
				"Supplier Quotation",
			):
				if field == "posting_date":
					continue
			elif field == "transaction_date":
				continue
		if str(header.get(field) or "").strip():
			continue
		value = _alias_value(header, aliases)
		if value:
			header[field] = value


def _promote_party(header: dict[str, Any], doctype: str) -> None:
	link = _PARTY_BY_DOCTYPE.get(doctype)
	if not link:
		return
	if str(header.get(link) or "").strip():
		return
	primary = _SUPPLIER_ALIASES if link == "supplier" else _CUSTOMER_ALIASES
	value = _alias_value(header, primary)
	if value:
		header[link] = value


def _promote_address(header: dict[str, Any], doctype: str = "") -> None:
	if str(header.get("address_line1") or "").strip():
		return
	link = _PARTY_BY_DOCTYPE.get(doctype)
	if link == "supplier":
		aliases = [*_SELLER_ADDRESS_ALIASES, "address", "address_line1"]
	elif link == "customer":
		aliases = [*_BUYER_ADDRESS_ALIASES, "address", "address_line1"]
	else:
		aliases = _ADDRESS_ALIASES
	raw = _alias_value(header, aliases)
	if not raw:
		return
	line1, city, state = _split_address(raw)
	header["address_line1"] = line1 or raw
	if city and not header.get("city"):
		header["city"] = city
	if state and not header.get("state") and not header.get("vat_emirate"):
		header["state"] = state
		header["vat_emirate"] = state


def _promote_phone(header: dict[str, Any]) -> None:
	if str(header.get("phone") or header.get("mobile_no") or "").strip():
		return
	value = _alias_value(header, _PHONE_ALIASES)
	if value:
		header["phone"] = value


def _promote_item_codes(items: list[Any]) -> None:
	"""When OCR only printed a name, put a short code on item_code and keep the label as name."""
	for row in items:
		if not isinstance(row, dict):
			continue
		label = str(row.get("item_name") or row.get("description") or "").strip()
		existing = str(row.get("item_code") or "").strip()
		if existing and not _looks_like_description(existing):
			if not row.get("item_name") and label:
				row["item_name"] = label
			continue
		source = existing or label
		if not source:
			continue
		clean_name = _clean_item_label(source)
		row["item_name"] = clean_name or source
		row["item_code"] = _slug_code(clean_name or source)


def _alias_value(header: dict[str, Any], aliases: tuple[str, ...]) -> str:
	lowered = {str(k).strip().lower().replace(" ", "_"): v for k, v in header.items()}
	for alias in aliases:
		key = alias.lower().replace(" ", "_")
		value = lowered.get(key)
		if value in (None, ""):
			continue
		text = str(value).strip()
		if text:
			return text
	return ""


def _split_address(raw: str) -> tuple[str, str, str]:
	"""Best-effort line1 / city / emirate from a single billing_address string."""
	parts = [p.strip() for p in re.split(r",|\n", raw) if p and p.strip()]
	if not parts:
		return raw.strip(), "", ""
	state = ""
	city = ""
	for part in reversed(parts):
		token = part.strip()
		lower = token.lower().replace(".", "")
		if lower in {"uae", "united arab emirates", "u a e"}:
			continue
		if token.isdigit() or lower.startswith("po box"):
			continue
		for emirate in EMIRATES:
			compact = emirate.lower().replace(" ", "")
			if emirate.lower() in lower or lower in emirate.lower() or compact in lower.replace(" ", ""):
				state = emirate
				break
		if state:
			break
	if state:
		compact_state = state.lower().replace(" ", "")
		parts = [
			p
			for p in parts
			if state.lower() not in p.lower()
			and compact_state not in p.lower().replace(" ", "")
			and p.lower().replace(".", "") not in {"uae", "united arab emirates"}
		]
	parts = [p for p in parts if not p.strip().isdigit() and not p.strip().lower().startswith("po box")]
	if parts:
		# Last remaining segment often the city / area.
		city_candidate = parts[-1]
		if len(parts) > 1 and len(city_candidate) < 40:
			city = city_candidate
			parts = parts[:-1]
	line1 = ", ".join(parts) if parts else raw.strip()
	# Short campus codes (DDP, DIFC) are not cities — prefer the emirate.
	if city and state and city.isupper() and len(city) <= 5:
		city = state
	return line1, city, state


def normalize_missing(rows: Any) -> list[dict[str, str]]:
	"""Turn IDP missing_masters into {doctype, name, field} rows."""
	out: list[dict[str, str]] = []
	seen: set[tuple[str, str, str]] = set()
	for row in rows or []:
		if isinstance(row, str):
			token = row.strip()
			if not token:
				continue
			if token in CREATABLE or token in {"Account", "Cost Center", "Company", "UOM", "Item Group"}:
				doctype, field, name = token, "", ""
			elif token in _FIELD_TO_DOCTYPE:
				doctype = _FIELD_TO_DOCTYPE[token]
				field, name = token, ""
			else:
				doctype = token
				field, name = "", token
		elif isinstance(row, dict):
			doctype = str(row.get("doctype") or "").strip()
			name = str(row.get("name") or "").strip()
			field = str(row.get("field") or "").strip()
			if not doctype and field:
				doctype = _FIELD_TO_DOCTYPE.get(field, "")
			if not doctype:
				continue
		else:
			continue
		key = (doctype, name, field)
		if key in seen:
			continue
		seen.add(key)
		out.append({"doctype": doctype, "name": name, "field": field})
	return out


def split_missing(rows: Any) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
	"""Creatable proposals vs hard blockers."""
	creatable: list[dict[str, str]] = []
	blocked: list[dict[str, str]] = []
	for row in normalize_missing(rows):
		if row["doctype"] in CREATABLE:
			creatable.append(row)
		else:
			blocked.append(row)
	return creatable, blocked


def link_readable(doctype: str, name: str | None) -> bool:
	"""True when this user may read the named document.

	``db.exists`` ignores company tenancy. A supplier tagged to another company
	still exists, and Purchase Invoice then raises an empty PermissionError.
	Callers: party_by_trn, bind_parties_by_trn, _create_item, scope_extract_to_company.
	"""
	import frappe

	if not name or not frappe.db.exists(doctype, name):
		return False
	return bool(frappe.has_permission(doctype, "read", name))


def party_by_trn(doctype: str, trn: str | None) -> str | None:
	"""Match Supplier or Customer by normalized tax_id, for this company only."""
	if doctype not in ("Supplier", "Customer"):
		return None
	from taxmate.uae.validation import normalize_trn

	cleaned = normalize_trn(trn)
	if not cleaned:
		return None
	import frappe

	# Static SQL per doctype — table name is never user input.
	query = {
		"Supplier": "select name from `tabSupplier` where replace(ifnull(tax_id, ''), ' ', '') = %s",
		"Customer": "select name from `tabCustomer` where replace(ifnull(tax_id, ''), ' ', '') = %s",
	}[doctype]
	for (name,) in frappe.db.sql(query, cleaned):
		if link_readable(doctype, name):
			return name
	return None


def bind_parties_by_trn(extracted: dict[str, Any]) -> None:
	"""Rewrite header party Links when a TRN on the extract matches an existing party."""
	if not extracted.get("success"):
		return
	data = extracted.get("extracted_data") or {}
	header = data.get("header")
	if not isinstance(header, dict):
		return
	trn = _header_trn(header)
	for doctype, field in _PARTY_LINK.items():
		raw = str(header.get(field) or "").strip()
		if not raw:
			continue
		import frappe

		if link_readable(doctype, raw):
			continue
		matched = (
			party_by_trn(doctype, trn)
			or party_by_trn(doctype, raw)
			or _usable_party_by_name(doctype, raw)
		)
		if matched:
			header[field] = matched
		elif frappe.db.exists(doctype, raw):
			# Same legal name, other company. Leave the link empty so this
			# company gets its own supplier instead of a permission error on save.
			header.pop(field, None)


def _header_trn(header: dict[str, Any]) -> str:
	for key in ("tax_id", "supplier_trn", "customer_trn", "trn", "vat_number", "gstin"):
		value = str(header.get(key) or "").strip()
		if value:
			return value
	return ""


def scope_extract_to_company(extracted: dict[str, Any]) -> None:
	"""Drop links this user cannot read.

	Another company's supplier still matches by name. Saving that link raises
	an empty PermissionError, which the desk used to show as a failed file read.
	"""
	if not extracted.get("success"):
		return
	data = extracted.get("extracted_data")
	if not isinstance(data, dict):
		return
	changed = False
	header = data.get("header")
	if isinstance(header, dict):
		trn = _header_trn(header)
		for doctype, field in _PARTY_LINK.items():
			raw = str(header.get(field) or "").strip()
			if not raw:
				continue
			if link_readable(doctype, raw):
				continue
			matched = party_by_trn(doctype, trn) or _usable_party_by_name(doctype, raw)
			if matched:
				header[field] = matched
			else:
				# Keep the printed name off the Link. The document name is unique
				# site-wide, so this company needs its own supplier record.
				printed = extracted.setdefault("_printed_parties", {})
				if isinstance(printed, dict):
					printed[field] = raw
				header.pop(field, None)
			changed = True
	items = data.get("items")
	if isinstance(items, list):
		for row in items:
			if not isinstance(row, dict):
				continue
			code = str(row.get("item_code") or "").strip()
			if code and not link_readable("Item", code):
				import frappe

				# A printed SKU that does not exist yet is created later.
				# A code that exists for another company must not be reused.
				if not frappe.db.exists("Item", code):
					row["_printed_item_code"] = code
				row.pop("item_code", None)
				changed = True
	if changed:
		from taxmate.idp.post_map import refresh_validation

		refresh_validation(extracted)


def align_scanned_items(extracted: dict[str, Any]) -> None:
	"""Point existing items at a fitting leaf group when they sit in the bucket group."""
	data = extracted.get("extracted_data") or {}
	for row in data.get("items") or []:
		if not isinstance(row, dict):
			continue
		code = str(row.get("item_code") or "").strip()
		if not link_readable("Item", code):
			continue
		label = str(row.get("item_name") or row.get("description") or code)
		_align_item_group(code, label, "")


def party_proposals_for_company(extracted: dict[str, Any]) -> list[dict[str, Any]]:
	"""Confirmed supplier/customer cards for parties this company still does not have."""
	rows: list[dict[str, Any]] = []
	for row in build_proposals(extracted):
		if row.get("doctype") not in ("Supplier", "Customer"):
			continue
		copied = dict(row)
		copied["confirmed"] = True
		rows.append(copied)
	return rows


def build_proposals(extracted: dict[str, Any]) -> list[dict[str, Any]]:
	"""One consent card per missing creatable master. Prefills what the file carried."""
	validation = extracted.get("validation") or {}
	creatable, _blocked = split_missing(validation.get("missing_masters"))
	data = extracted.get("extracted_data") or {}
	items = [row for row in (data.get("items") or []) if isinstance(row, dict)]
	if not creatable and not (extracted.get("_printed_parties") or {}):
		return []
	header = dict(data.get("header") or {})
	proposals: list[dict[str, Any]] = []
	seen: set[str] = set()
	for row in creatable:
		doctype = row["doctype"]
		if doctype == "UOM":
			proposal = _uom_proposal(row)
		elif doctype in ("Supplier", "Customer"):
			proposal = _party_proposal(doctype, row, header)
		elif doctype == "Item":
			proposal = _item_proposal(row, items)
		else:
			continue
		if not proposal or proposal["key"] in seen:
			continue
		seen.add(proposal["key"])
		proposals.append(proposal)
	_append_printed_party(extracted, proposals, seen)
	proposals.sort(key=lambda card: {"UOM": 0, "Supplier": 1, "Customer": 2, "Item": 3}.get(card["doctype"], 9))
	return proposals


def _append_printed_party(
	extracted: dict[str, Any], proposals: list[dict[str, Any]], seen: set[str]
) -> None:
	"""Propose a party when the only match belongs to another company.

	Schema then reports a missing field, not a missing master, so the card
	would otherwise never appear.
	"""
	data = extracted.get("extracted_data") or {}
	header = data.get("header") if isinstance(data.get("header"), dict) else {}
	link = _PARTY_BY_DOCTYPE.get(str(data.get("doctype") or ""))
	if not link or str(header.get(link) or "").strip():
		return
	raw = str((extracted.get("_printed_parties") or {}).get(link) or "").strip()
	if not raw:
		return
	party_doctype = "Supplier" if link == "supplier" else "Customer"
	if any(row.get("doctype") == party_doctype for row in proposals):
		return
	proposal = _party_proposal(party_doctype, {"name": raw, "field": link, "doctype": party_doctype}, header)
	if proposal and proposal["key"] not in seen:
		seen.add(proposal["key"])
		proposals.append(proposal)


def _uom_proposal(missing: dict[str, str]) -> dict[str, Any] | None:
	name = str(missing.get("name") or "").strip()
	if not name:
		return None
	return {
		"key": f"uom:{name}",
		"doctype": "UOM",
		"link_field": str(missing.get("field") or "uom"),
		"title": name,
		"source_fields": {"uom_name": name},
		"required_fields": [_field("uom_name", "idp.field.uom", name)],
		"optional_fields": [],
		"consent_label_key": "idp.field.uom",
		"confirmed": False,
	}


def _party_address_line(doctype: str, header: dict[str, Any]) -> str:
	aliases = _SELLER_ADDRESS_ALIASES if doctype == "Supplier" else _BUYER_ADDRESS_ALIASES
	raw = _alias_value(header, aliases)
	if raw:
		return raw
	# Fall back to promoted address_line1 only when no opposing party address is present.
	opposing = _BUYER_ADDRESS_ALIASES if doctype == "Supplier" else _SELLER_ADDRESS_ALIASES
	if _alias_value(header, opposing):
		return ""
	return str(header.get("address_line1") or header.get("address") or "").strip()


def _party_proposal(doctype: str, missing: dict[str, str], header: dict[str, Any]) -> dict[str, Any] | None:
	link_field = missing.get("field") or _PARTY_LINK[doctype]
	raw_name = str(missing.get("name") or header.get(link_field) or "").strip()
	if not raw_name:
		return None
	name_field = "supplier_name" if doctype == "Supplier" else "customer_name"
	type_field = "supplier_type" if doctype == "Supplier" else "customer_type"
	trn = _header_trn(header)
	addr = _party_address_line(doctype, header)
	line1, city, state = _split_address(addr) if addr else ("", "", "")
	source = {
		name_field: raw_name,
		type_field: "Company",
		"tax_id": trn,
		"address_line1": line1 or addr,
		"city": str(header.get("city") or "").strip() or city,
		"state": _emirate(header) or state,
		"email_id": _safe_email(header.get("email_id") or header.get("email")),
		"phone": str(header.get("phone") or header.get("mobile_no") or "").strip(),
	}
	required = [
		_field(name_field, _PARTY_LABEL.get(name_field, f"idp.field.{name_field}"), source[name_field]),
		_field(type_field, "idp.field.partyType", source[type_field], options=["Company", "Individual"]),
	]
	optional = [
		_field("address_line1", "idp.field.addressLine", source["address_line1"]),
		_field("city", "idp.field.city", source["city"]),
		_field("state", "idp.field.emirate", source["state"], options=list(EMIRATES)),
		_field("tax_id", "f.customerTrn" if doctype == "Customer" else "idp.field.trn", source["tax_id"]),
		_field("email_id", "idp.field.email", source["email_id"]),
		_field("phone", "idp.field.phone", source["phone"]),
	]
	return {
		"key": f"{doctype.lower()}:{raw_name}",
		"doctype": doctype,
		"link_field": link_field,
		"title": raw_name,
		"source_fields": source,
		"required_fields": required,
		"optional_fields": optional,
		"consent_label_key": "idp.propose.supplier" if doctype == "Supplier" else "idp.propose.customer",
		"confirmed": False,
	}


def _item_proposal(missing: dict[str, str], items: list[dict[str, Any]]) -> dict[str, Any] | None:
	raw = str(missing.get("name") or "").strip()
	row = _item_row_for(raw, items)
	raw_label = str((row or {}).get("item_name") or (row or {}).get("description") or raw).strip()
	label = _clean_item_label(raw_label) or raw_label
	if not label:
		return None
	existing = str((row or {}).get("item_code") or "").strip()
	code = existing if existing and not _looks_like_description(existing) else _slug_code(label)
	uom = str((row or {}).get("uom") or (row or {}).get("stock_uom") or "Nos").strip() or "Nos"
	# Item Group is a tree leaf. Do not copy Stock Settings' first leaf onto goods.
	group = item_group_for_label(label)
	source = {
		"item_code": code,
		"item_name": label,
		"item_group": group,
		"stock_uom": uom,
	}
	required = [
		_field("item_code", "idp.field.itemCode", source["item_code"]),
		_field("item_name", "idp.field.itemName", source["item_name"]),
		_field("stock_uom", "idp.field.uom", source["stock_uom"]),
	]
	leaves = leaf_item_groups()
	optional = [
		_field(
			"item_group",
			"idp.field.itemGroup",
			source["item_group"],
			options=leaves or None,
		)
	]
	return {
		"key": f"item:{label}",
		"doctype": "Item",
		"link_field": "item_code",
		"link_index": items.index(row) if row in items else None,
		"title": label,
		"source_fields": source,
		"required_fields": required,
		"optional_fields": optional,
		"consent_label_key": "idp.propose.item",
		"confirmed": True,
	}


def _item_row_for(raw: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
	needle = raw.lower()
	for row in items:
		for key in ("item_code", "item_name", "description"):
			if str(row.get(key) or "").strip().lower() == needle:
				return row
	for row in items:
		if not row.get("item_code"):
			return row
	return items[0] if items else None


def _emirate(header: dict[str, Any]) -> str:
	for key in ("vat_emirate", "emirate", "state"):
		value = str(header.get(key) or "").strip()
		if value in EMIRATES:
			return value
	return ""


def _field(field: str, label_key: str, value: str, options: list[str] | None = None) -> dict[str, Any]:
	row: dict[str, Any] = {"field": field, "label_key": label_key, "value": value or ""}
	if options:
		row["options"] = options
	return row


def _promote_totals(header: dict[str, Any]) -> None:
	"""Fill grand_total from net/total_due when OCR only printed one amount."""
	if not str(header.get("grand_total") or "").strip():
		for key in ("net_total", "total_due", "amount_due", "total"):
			value = header.get(key)
			if value not in (None, ""):
				header["grand_total"] = value
				break
	if not str(header.get("net_total") or "").strip() and header.get("grand_total") not in (None, ""):
		header["net_total"] = header["grand_total"]


def _ensure_line_from_total(data: dict[str, Any]) -> None:
	"""When OCR lost the line table, seed one service row from the document total."""
	items = data.get("items")
	if isinstance(items, list) and any(
		isinstance(row, dict)
		and (str(row.get("item_code") or row.get("item_name") or row.get("description") or "").strip())
		for row in items
	):
		return
	header = data.get("header") if isinstance(data.get("header"), dict) else {}
	total = header.get("grand_total") or header.get("net_total")
	if total in (None, ""):
		return
	label = str(header.get("remarks") or header.get("bill_no") or "Services as per document").strip()
	data["items"] = [
		{
			"item_name": label if not label.startswith("SOC_") else "Services as per document",
			"description": label,
			"qty": 1,
			"rate": total,
			"amount": total,
			"uom": "Nos",
		}
	]


_ADDRESS_LINK_FIELDS: tuple[str, ...] = (
	"supplier_address",
	"customer_address",
	"shipping_address",
	"billing_address",
	"billing_address_name",
)


def _scrub_address_links(header: dict[str, Any]) -> None:
	"""Drop free-text values parked on Address Link fields (they are not Address names).

	OCR often parks the full street line on billing_address. Schema then reports a
	missing Address master, which blocked Save with idp.notice.masters even though
	party create attaches a real Address from the proposal fields.
	"""
	for key in _ADDRESS_LINK_FIELDS:
		value = str(header.get(key) or "").strip()
		if not value:
			continue
		if key == "billing_address" or "," in value or len(value) > 60 or "\n" in value:
			header.pop(key, None)


def release_address_links(extracted: dict[str, Any]) -> None:
	"""Strip Address Link blockers so Scan can propose Supplier/Customer/Item create."""
	data = extracted.get("extracted_data")
	header = data.get("header") if isinstance(data, dict) else None
	if isinstance(header, dict):
		_scrub_address_links(header)
	validation = extracted.get("validation")
	if not isinstance(validation, dict):
		return
	rows = validation.get("missing_masters")
	if not isinstance(rows, list):
		return
	validation["missing_masters"] = [
		row
		for row in rows
		if not (isinstance(row, dict) and str(row.get("doctype") or "") == "Address")
	]


# A currency code is not a Company. The model often parks "AED" there.
_CURRENCY_CODES: frozenset[str] = frozenset(
	{
		"AED",
		"USD",
		"EUR",
		"GBP",
		"SAR",
		"INR",
		"QAR",
		"OMR",
		"BHD",
		"KWD",
		"CNY",
		"JPY",
		"CHF",
		"AUD",
		"CAD",
	}
)


def release_currency_company(extracted: dict[str, Any]) -> None:
	"""Move a currency code off company so it cannot block the draft as a missing Company."""
	data = extracted.get("extracted_data")
	header = data.get("header") if isinstance(data, dict) else None
	if isinstance(header, dict):
		_release_currency_company(header)
	validation = extracted.get("validation")
	if not isinstance(validation, dict):
		return
	rows = validation.get("missing_masters")
	if not isinstance(rows, list):
		return
	validation["missing_masters"] = [
		row
		for row in rows
		if not (
			isinstance(row, dict)
			and row.get("doctype") == "Company"
			and str(row.get("name") or "").strip().upper() in _CURRENCY_CODES
		)
	]


def _release_currency_company(header: dict[str, Any]) -> None:
	currency = str(header.get("currency") or header.get("Currency") or "").strip().upper()
	for key in list(header):
		if str(key).strip().lower().replace(" ", "_") != "company":
			continue
		raw = str(header.get(key) or "").strip()
		code = raw.upper()
		if code not in _CURRENCY_CODES and code != currency:
			continue
		header.pop(key, None)
		if not currency and code in _CURRENCY_CODES:
			header["currency"] = code
			currency = code


def _sanitize_header_values(header: dict[str, Any]) -> None:
	"""Normalize OCR dates and amounts so schema validation stops blocking save."""
	_release_currency_company(header)
	for key in ("posting_date", "transaction_date", "due_date", "bill_date", "date"):
		if key not in header and key != "date":
			continue
		raw = header.get(key) if key != "date" else header.get("posting_date") or header.get("date")
		if raw in (None, ""):
			continue
		parsed = _parse_ocr_date(str(raw))
		if parsed:
			if key == "date":
				header["posting_date"] = parsed
			else:
				header[key] = parsed
	# Promote date alias onto posting_date when still missing.
	if not str(header.get("posting_date") or "").strip() and header.get("date"):
		parsed = _parse_ocr_date(str(header.get("date")))
		if parsed:
			header["posting_date"] = parsed
	for key in ("net_total", "grand_total", "total", "total_due", "amount_due", "subtotal"):
		if key not in header or header.get(key) in (None, ""):
			continue
		num = _parse_ocr_amount(header.get(key))
		if num is not None:
			header[key] = num
	if header.get("currency") in (None, ""):
		# common OCR miss on receipts
		pass


def _sanitize_item_values(data: dict[str, Any]) -> None:
	items = data.get("items")
	if not isinstance(items, list):
		return
	for row in items:
		if not isinstance(row, dict):
			continue
		for key in ("qty", "quantity", "received_qty", "rate", "unit_price", "amount", "line_total"):
			if key not in row or row.get(key) in (None, ""):
				continue
			num = _parse_ocr_amount(row.get(key))
			if num is not None:
				row[key] = num
		# Align qty aliases for purchase receipt validators.
		qty = row.get("qty")
		if qty in (None, "") and row.get("quantity") not in (None, ""):
			row["qty"] = row["quantity"]
		if row.get("received_qty") in (None, "") and row.get("qty") not in (None, ""):
			row["received_qty"] = row["qty"]
		if row.get("rate") in (None, "") and row.get("unit_price") not in (None, ""):
			row["rate"] = row["unit_price"]
		if not row.get("stock_uom"):
			row["stock_uom"] = row.get("uom") or "Nos"
		if not row.get("uom"):
			row["uom"] = row.get("stock_uom") or "Nos"
	_fill_zero_rates_from_total(data)


def _fill_zero_rates_from_total(data: dict[str, Any]) -> None:
	"""Purchase OCR often leaves rate=0 while the header still has the bill total."""
	items = [row for row in (data.get("items") or []) if isinstance(row, dict)]
	if not items:
		return
	header = data.get("header") if isinstance(data.get("header"), dict) else {}
	total = _parse_ocr_amount(header.get("grand_total") or header.get("net_total") or header.get("total"))
	if total is None or total <= 0:
		return
	if any(float(row.get("rate") or 0) > 0 or float(row.get("amount") or 0) > 0 for row in items):
		return
	if len(items) == 1:
		qty = float(items[0].get("qty") or items[0].get("quantity") or 1) or 1
		items[0]["qty"] = qty
		items[0]["rate"] = total / qty
		items[0]["amount"] = total
		items[0]["unit_price"] = items[0]["rate"]
		return
	share = total / len(items)
	for row in items:
		qty = float(row.get("qty") or row.get("quantity") or 1) or 1
		row["qty"] = qty
		row["rate"] = share / qty
		row["amount"] = share
		row["unit_price"] = row["rate"]
	_fill_zero_rates_from_total(data)


def _fill_zero_rates_from_total(data: dict[str, Any]) -> None:
	"""Purchase OCR often leaves rate=0 while the header still has the bill total."""
	items = [row for row in (data.get("items") or []) if isinstance(row, dict)]
	if not items:
		return
	header = data.get("header") if isinstance(data.get("header"), dict) else {}
	total = _parse_ocr_amount(header.get("grand_total") or header.get("net_total") or header.get("total"))
	if total is None or total <= 0:
		return
	if any(float(row.get("rate") or 0) > 0 or float(row.get("amount") or 0) > 0 for row in items):
		return
	if len(items) == 1:
		qty = float(items[0].get("qty") or items[0].get("quantity") or 1) or 1
		items[0]["qty"] = qty
		items[0]["rate"] = total / qty
		items[0]["amount"] = total
		items[0]["unit_price"] = items[0]["rate"]
		return
	share = total / len(items)
	for row in items:
		qty = float(row.get("qty") or row.get("quantity") or 1) or 1
		row["qty"] = qty
		row["rate"] = share / qty
		row["amount"] = share
		row["unit_price"] = row["rate"]


def _parse_ocr_amount(value: Any) -> float | None:
	text = str(value or "").strip()
	if not text:
		return None
	cleaned = text.replace(",", "").replace("AED", "").replace(" ", "")
	try:
		return float(cleaned)
	except ValueError:
		return None


def _parse_ocr_date(value: str) -> str:
	"""Return YYYY-MM-DD when OCR printed a long date, else the original if already ISO."""
	text = (value or "").strip()
	if not text:
		return ""
	if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
		return text
	# UAE tax invoices print the day first: 09/10/2026 is 9 October 2026.
	slash = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
	if slash:
		day = int(slash.group(1))
		month = int(slash.group(2))
		year = int(slash.group(3))
		if year < 100:
			year += 2000
		if 1 <= day <= 31 and 1 <= month <= 12:
			return f"{year:04d}-{month:02d}-{day:02d}"
		return ""
	# 29-Sep-2026
	named_slash = re.fullmatch(r"(\d{1,2})[/-]([A-Za-z]{3,9})[/-](\d{2,4})", text)
	if named_slash:
		text = f"{named_slash.group(1)} {named_slash.group(2)} {named_slash.group(3)}"
	# 18th August,2026 / 18 August 2026 / 18th Aug'26
	m = re.search(
		r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})'?[,\s]+(\d{2,4})",
		text,
	)
	if not m:
		return ""
	day = int(m.group(1))
	month_token = m.group(2)[:3].lower()
	year = int(m.group(3))
	if year < 100:
		year += 2000
	months = {
		"jan": 1,
		"feb": 2,
		"mar": 3,
		"apr": 4,
		"may": 5,
		"jun": 6,
		"jul": 7,
		"aug": 8,
		"sep": 9,
		"oct": 10,
		"nov": 11,
		"dec": 12,
	}
	month = months.get(month_token)
	if not month or day < 1 or day > 31:
		return ""
	return f"{year:04d}-{month:02d}-{day:02d}"


def _scrub_contact_noise(header: dict[str, Any]) -> None:
	"""Drop OCR values wrongly parked on contact fields (e.g. requisition → email)."""
	for key in ("email_id", "email"):
		if key in header:
			clean = _safe_email(header.get(key))
			if clean:
				header[key] = clean
			else:
				header.pop(key, None)


def _safe_email(value: Any) -> str:
	"""Drop OCR noise that is clearly not an email (requisition refs, names, etc.)."""
	text = str(value or "").strip()
	if not text or "@" not in text:
		return ""
	local, _, domain = text.partition("@")
	if not local or "." not in domain or " " in text or "/" in text:
		return ""
	return text


def _looks_like_description(value: str) -> bool:
	"""True when OCR dumped a line description into item_code instead of a SKU."""
	text = value.strip()
	if not text:
		return False
	if len(text) > 40:
		return True
	if " " in text and len(text) > 24:
		return True
	lower = text.lower()
	if any(token in lower for token in (" from ", " to ", " with ", " actionable ", " orch")):
		return True
	return False


def _clean_item_label(label: str) -> str:
	"""Drop leading qty and trailing service-window clauses from OCR line text."""
	text = re.sub(r"\s+", " ", (label or "").strip())
	if not text:
		return ""
	# "300 Critical Device with …" → drop leading quantity.
	text = re.sub(r"^\d{1,6}\s+", "", text)
	# Drop trailing "from 15th Aug'26 to 14thAug'29" style windows.
	text = re.sub(
		r"\s+from\s+\d{1,2}\w{0,2}\s+\w{3}'?\d{2}\s+to\s+\d{1,2}\w{0,2}\s*\w{3}'?\d{2}\s*$",
		"",
		text,
		flags=re.IGNORECASE,
	)
	text = re.sub(r"\s+from\s+.+\s+to\s+.+$", "", text, flags=re.IGNORECASE)
	# Prefer the clause before the first comma when OCR packed marketing copy.
	if "," in text:
		head = text.split(",", 1)[0].strip()
		if len(head) >= 8:
			text = head
	words = text.split()
	# A wrapped service line is still one item. Only cut a long OCR paragraph.
	if len(words) > 16:
		text = " ".join(words[:16])
	return text.strip(" -,") or label.strip()


# Printed words → fragments of a leaf Item Group name. Item is the stock master.
# Item Group is the tree. "Consulting Services" is not a dairy item.
_ITEM_GROUP_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
	(("ice cream", "icecream", "frozen"), ("frozen",)),
	(("milk", "laban", "labneh", "yoghurt", "yogurt", "cheese", "butter", "cream", "ghee", "egg"), ("dairy",)),
	(("juice", "soda", "coffee", "tea", "cola", "beverage"), ("beverage", "drink")),
	(("bread", "bakery", "cake", "bun"), ("bakery",)),
	(("chicken", "mutton", "beef", "meat", "poultry"), ("meat", "poultry")),
	(("fish", "shrimp", "prawn", "seafood"), ("seafood", "fish")),
	(("vegetable", "fruit", "produce", "tomato", "onion", "potato"), ("produce", "vegetable", "fruit")),
	(("snack", "chocolate", "biscuit", "chips", "confection"), ("snack", "confection")),
	(("rice", "flour", "grain", "lentil"), ("rice", "grain", "flour")),
	(("cooking oil", "olive oil", "sunflower"), ("oil",)),
	(("spice", "condiment", "sauce"), ("spice", "condiment")),
	(("detergent", "cleaner", "soap"), ("clean", "household")),
	(("consulting", "retainer", "professional fee"), ("consulting",)),
	(("service charge", "services"), ("service",)),
)


def _has_token(text: str, token: str) -> bool:
	# Optional plural so "eggs" still matches the egg hint.
	return re.search(rf"(?<![a-z0-9]){re.escape(token)}s?(?![a-z0-9])", text) is not None


def leaf_item_groups() -> list[str]:
	"""Leaf Item Groups only. Group nodes cannot be an Item's item_group."""
	try:
		import frappe

		return frappe.get_all(
			"Item Group", filters={"is_group": 0}, pluck="name", order_by="name asc"
		)
	except Exception:
		return []


def _generic_item_group() -> str:
	"""Stock Settings, else the oldest leaf. A bucket, not a match for the line."""
	try:
		import frappe

		group = frappe.db.get_single_value("Stock Settings", "item_group")
		if group:
			return str(group)
		return str(
			frappe.db.get_value("Item Group", {"is_group": 0}, "name", order_by="creation asc") or ""
		)
	except Exception:
		return ""


def _default_item_group() -> str:
	return _generic_item_group()


def _is_leaf_group(name: str) -> bool:
	if not name:
		return False
	try:
		import frappe

		if not frappe.db.exists("Item Group", name):
			return False
		return not frappe.db.get_value("Item Group", name, "is_group")
	except Exception:
		return False


def _is_dump_group(name: str) -> bool:
	"""True for the site-wide fallback and for a services group used as a bucket."""
	if not name or name == _generic_item_group():
		return True
	folded = name.lower()
	return "consulting" in folded or folded in {"services", "service"}


def item_group_for_label(label: str) -> str:
	"""Leaf Item Group whose name fits the printed item. Empty when nothing fits."""
	text = (label or "").lower()
	if not text:
		return ""
	leaves = leaf_item_groups()
	for words, fragments in _ITEM_GROUP_HINTS:
		if not any(_has_token(text, word) for word in words):
			continue
		matches = [name for name in leaves if any(frag in name.lower() for frag in fragments)]
		if not matches:
			continue
		for frag in fragments:
			tight = [name for name in matches if frag in name.lower()]
			if tight:
				return sorted(tight, key=lambda name: (len(name), name))[0]
		return sorted(matches, key=lambda name: (len(name), name))[0]
	return ""


def resolve_item_group(label: str, requested: str | None) -> str:
	"""Leaf group for this item. A services bucket does not win over a dairy match."""
	specific = item_group_for_label(label)
	asked = (requested or "").strip()
	if asked and _is_leaf_group(asked) and not _is_dump_group(asked):
		return asked
	if specific:
		return specific
	if asked and _is_leaf_group(asked):
		return asked
	return _generic_item_group()


def _slug_code(label: str) -> str:
	slug = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").upper()
	return (slug[:20] or "ITEM")[:140]


def proposals_complete(proposals: list[dict[str, Any]] | None) -> bool:
	"""True when every proposal is confirmed and every required field has a value."""
	if not proposals:
		return True
	for row in proposals:
		if not row.get("confirmed"):
			return False
		for field in row.get("required_fields") or []:
			if not str(field.get("value") or "").strip():
				return False
	return True


def merge_proposal_values(
	proposals: list[dict[str, Any]], updates: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
	"""Apply the clerk's consent and typed values onto the review proposals."""
	by_key = {str(row.get("key") or ""): row for row in (updates or []) if isinstance(row, dict)}
	out: list[dict[str, Any]] = []
	for base in proposals:
		row = dict(base)
		patch = by_key.get(str(row.get("key") or ""))
		if not patch:
			out.append(row)
			continue
		row["confirmed"] = bool(patch.get("confirmed"))
		values = dict(row.get("source_fields") or {})
		for bucket in ("required_fields", "optional_fields"):
			patched = {
				str(f.get("field")): str(f.get("value") or "")
				for f in (patch.get(bucket) or [])
				if isinstance(f, dict)
			}
			fields = []
			for field in row.get(bucket) or []:
				entry = dict(field)
				name = str(entry.get("field") or "")
				if name in patched:
					entry["value"] = patched[name][:140]
					values[name] = entry["value"]
				fields.append(entry)
			row[bucket] = fields
		row["source_fields"] = values
		out.append(row)
	return out


def create_confirmed(
	proposals: list[dict[str, Any]],
	*,
	can_create: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
	"""Insert confirmed masters. Returns {ok, created: {link_key: name}, error_key?}."""
	import frappe

	created: dict[str, str] = {}
	savepoint = "taxmate_idp_masters"
	frappe.db.savepoint(savepoint)

	def fail(error_key: str, detail: str | None = None) -> dict[str, Any]:
		frappe.db.rollback(save_point=savepoint)
		out: dict[str, Any] = {"ok": False, "error_key": error_key, "created": {}}
		if detail:
			out["detail"] = str(detail)[:400]
		return out

	# Units first, then the party, then items that stock in those units.
	ordered = sorted(
		proposals,
		key=lambda row: {"UOM": 0, "Supplier": 1, "Customer": 2, "Item": 3}.get(str(row.get("doctype") or ""), 9),
	)
	for row in ordered:
		if not row.get("confirmed"):
			return fail("idp.propose.needConsent")
		doctype = str(row.get("doctype") or "")
		if doctype not in CREATABLE:
			return fail("idp.notice.masters")
		if can_create and not can_create(doctype):
			return fail("idp.denied")
		if not frappe.has_permission(doctype, "create"):
			return fail("idp.denied")
		# Blank party Type on the card — treat as Company (ERPNext default).
		for field in row.get("required_fields") or []:
			if not isinstance(field, dict):
				continue
			name = str(field.get("field") or "")
			if name in ("supplier_type", "customer_type") and not str(field.get("value") or "").strip():
				field["value"] = "Company"
		for field in row.get("required_fields") or []:
			if not str(field.get("value") or "").strip():
				return fail("idp.propose.needFields")
		values = _values_from_proposal(row)
		try:
			if doctype == "UOM":
				name = _create_uom(values)
				created[f"uom:{name}"] = name
			elif doctype == "Supplier":
				created["supplier"] = _create_supplier(values)
			elif doctype == "Customer":
				created["customer"] = _create_customer(values)
			elif doctype == "Item":
				name = _create_item(values)
				created["item_code"] = name
				idx = row.get("link_index")
				if idx is not None:
					created[f"item:{idx}"] = name
		except frappe.PermissionError:
			return fail(
				"idp.denied",
				"This draft was not saved. A supplier, customer, or item on it belongs to another company.",
			)
		except Exception as exc:
			frappe.log_error(title="TaxMate IDP master create failed", message=frappe.get_traceback())
			return fail("idp.propose.failed", str(exc) or None)
	return {"ok": True, "created": created}


def _values_from_proposal(row: dict[str, Any]) -> dict[str, str]:
	values = {str(k): str(v or "").strip() for k, v in (row.get("source_fields") or {}).items()}
	for bucket in ("required_fields", "optional_fields"):
		for field in row.get(bucket) or []:
			name = str(field.get("field") or "")
			if name:
				values[name] = str(field.get("value") or "").strip()
	return values


def _stamp_custom_company(payload: dict[str, Any]) -> dict[str, Any]:
	"""Tag masters with the clerk's active company before insert.

	Accountants with Company User Permissions cannot insert Supplier / Customer /
	Item when custom_company is blank — Frappe denies create even though role
	perms allow it. That surfaced as idp.denied ("You cannot run that scan.").
	"""
	import frappe

	from taxmate.utils.company import get_default_company

	meta = frappe.get_meta(str(payload.get("doctype") or ""))
	if not meta.has_field("custom_company"):
		return payload
	company = get_default_company()
	if company and frappe.db.exists("Company", company):
		payload["custom_company"] = company
	return payload


def _disambiguated_party_name(legal: str) -> str:
	"""Buying Settings names a supplier by its name, which is unique on the site.

	Another company's row already holds that name. This company gets its own
	record, with the company abbreviation on the name.
	"""
	import frappe

	from taxmate.utils.company import get_default_company

	company = get_default_company() or ""
	abbr = frappe.db.get_value("Company", company, "abbr") if company else ""
	token = str(abbr or "CO").strip() or "CO"
	return f"{legal.strip()} - {token}"[:140]


def _create_supplier(values: dict[str, str]) -> str:
	import frappe

	name = values.get("supplier_name") or ""
	existing = _existing_party("Supplier", name, values.get("tax_id"))
	if existing:
		return existing
	if frappe.db.exists("Supplier", name):
		name = _disambiguated_party_name(name)
		existing = _existing_party("Supplier", name, values.get("tax_id"))
		if existing:
			return existing
	group = (
		frappe.db.get_single_value("Buying Settings", "supplier_group")
		or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		or "All Supplier Groups"
	)
	doc = frappe.get_doc(
		_stamp_custom_company(
			{
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_type": values.get("supplier_type") or "Company",
				"supplier_group": group,
				"tax_id": values.get("tax_id") or None,
				"country": "United Arab Emirates",
			}
		)
	)
	try:
		doc.insert()
	except frappe.DuplicateEntryError:
		usable = _usable_party_by_name("Supplier", name)
		if usable:
			return usable
		raise
	if _has_address(values):
		_attach_address_contact("Supplier", doc.name, name, values)
	return doc.name


def ensure_named_items(items: list[Any]) -> None:
	"""Give a printed line an item code. Match by name, otherwise create it."""
	for row in items:
		if not isinstance(row, dict) or str(row.get("item_code") or "").strip():
			continue
		name = str(row.get("item_name") or row.get("description") or "").strip()
		if not name:
			continue
		group = item_group_for_label(name) or _generic_item_group()
		printed = str(row.pop("_printed_item_code", "") or "").strip()
		row["item_code"] = _create_item(
			{
				"item_name": name,
				"item_code": printed or _slug_code(name),
				"item_group": group,
				"stock_uom": str(row.get("uom") or row.get("stock_uom") or "Nos"),
			}
		)


def keep_supplier_invoice_date(header: dict[str, Any], doctype: str) -> None:
	"""ERPNext replaces the posting date unless Edit Posting Date is set.

	The printed invoice date is both the posting date and the supplier invoice date.
	The due date is checked against that date, so a scan today must not move it to today.
	"""
	if doctype != "Purchase Invoice":
		return
	printed = str(header.get("posting_date") or "").strip()
	if not printed:
		return
	header["set_posting_time"] = 1
	if not str(header.get("bill_date") or "").strip():
		header["bill_date"] = printed


def fold_printed_discounts(header: dict[str, Any], items: list[Any]) -> None:
	"""A tax invoice prints a line discount. ERPNext's row discount is per unit and rounds the net off.

	The line rates stay as printed. The discount total is applied once on the net total.
	"""
	total = 0.0
	for row in items:
		if not isinstance(row, dict):
			continue
		disc = float(row.get("discount_amount") or 0)
		rate = float(row.get("rate") or 0)
		qty = float(row.get("qty") or 0)
		if disc <= 0 or qty <= 0:
			continue
		total += disc if disc > rate else disc * qty
		row.pop("discount_amount", None)
	if total <= 0:
		return
	if not str(header.get("apply_discount_on") or "").strip():
		header["apply_discount_on"] = "Net Total"
	header["discount_amount"] = round(float(header.get("discount_amount") or 0) + total, 2)


def bind_typed_customer(header: dict[str, Any], doctype: str) -> None:
	"""Resolve a customer the clerk typed on a sale. Create one when it is new."""
	if doctype not in ("Sales Invoice", "Sales Order", "Quotation", "Delivery Note"):
		return
	typed = str(header.get("customer") or "").strip()
	if not typed:
		return
	import frappe

	if frappe.db.exists("Customer", typed):
		header["customer"] = typed
		return
	found = frappe.db.get_value("Customer", {"customer_name": typed}, "name")
	if found:
		header["customer"] = found
		return
	header["customer"] = _create_customer({"customer_name": typed, "customer_type": "Individual"})


def _create_customer(values: dict[str, str]) -> str:
	import frappe

	name = values.get("customer_name") or ""
	existing = _existing_party("Customer", name, values.get("tax_id"))
	if existing:
		return existing
	if frappe.db.exists("Customer", name):
		name = _disambiguated_party_name(name)
		existing = _existing_party("Customer", name, values.get("tax_id"))
		if existing:
			return existing
	group = (
		frappe.db.get_single_value("Selling Settings", "customer_group")
		or frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		or "All Customer Groups"
	)
	territory = frappe.db.get_single_value("Selling Settings", "territory") or frappe.db.get_value(
		"Territory", {"is_group": 0}, "name"
	)
	doc = frappe.get_doc(
		_stamp_custom_company(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": values.get("customer_type") or "Company",
				"customer_group": group,
				"territory": territory,
				"tax_id": values.get("tax_id") or None,
			}
		)
	)
	try:
		doc.insert()
	except frappe.DuplicateEntryError:
		usable = _usable_party_by_name("Customer", name)
		if usable:
			return usable
		raise
	if _has_address(values):
		_attach_address_contact("Customer", doc.name, name, values)
	return doc.name


def _create_uom(values: dict[str, str]) -> str:
	import frappe

	name = (values.get("uom_name") or values.get("uom") or "").strip()
	if not name:
		frappe.throw("Unit of measure is required")
	if frappe.db.exists("UOM", name):
		return name
	doc = frappe.get_doc({"doctype": "UOM", "uom_name": name})
	try:
		doc.insert()
	except frappe.DuplicateEntryError:
		# Another clerk saved the same unit between the exists check and insert.
		if frappe.db.exists("UOM", name):
			return name
		raise
	return doc.name


def _company_item_code(code: str) -> str:
	"""Item codes are unique on the site. Another company's item keeps its code."""
	import frappe

	from taxmate.utils.company import get_default_company

	company = get_default_company() or ""
	abbr = frappe.db.get_value("Company", company, "abbr") if company else ""
	token = re.sub(r"[^A-Za-z0-9]", "", str(abbr or ""))[:8] or "CO"
	return f"{code[:130]}-{token}"[:140]


def _align_item_group(code: str, label: str, requested: str) -> None:
	"""Move an item off a services bucket when the printed name fits a real leaf."""
	import frappe

	current = str(frappe.db.get_value("Item", code, "item_group") or "")
	chosen = resolve_item_group(label, requested or current)
	if not chosen or chosen == current or not _is_dump_group(current):
		return
	if not frappe.has_permission("Item", "write", code):
		return
	frappe.db.set_value("Item", code, "item_group", chosen)


def _create_item(values: dict[str, str]) -> str:
	import frappe

	raw_code = values.get("item_code") or values.get("item_name") or "ITEM"
	# Spaces / punctuation break Item naming for some sites; slug when needed.
	code = raw_code if re.fullmatch(r"[A-Za-z0-9_-]+", raw_code) else _slug_code(raw_code)
	label = values.get("item_name") or code
	asked = values.get("item_group") or ""
	if frappe.db.exists("Item", code):
		if link_readable("Item", code):
			_align_item_group(code, label, asked)
			return code
		code = _company_item_code(code)
		if frappe.db.exists("Item", code) and link_readable("Item", code):
			_align_item_group(code, label, asked)
			return code
	by_name = frappe.db.get_value("Item", {"item_name": values.get("item_name")}, "name")
	if by_name and link_readable("Item", by_name):
		_align_item_group(by_name, label, asked)
		return by_name
	group = resolve_item_group(label, asked)
	if not group or not _is_leaf_group(group):
		frappe.throw("Choose a leaf item group for this item")
	uom = (values.get("stock_uom") or "Nos").strip() or "Nos"
	if not frappe.db.exists("UOM", uom):
		uom = _create_uom({"uom_name": uom})
	doc = frappe.get_doc(
		_stamp_custom_company(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": values.get("item_name") or code,
				"item_group": group,
				"stock_uom": uom,
				"is_stock_item": 0,
			}
		)
	)
	try:
		doc.insert()
	except frappe.DuplicateEntryError:
		if link_readable("Item", code):
			_align_item_group(code, label, asked)
			return code
		scoped = _company_item_code(code)
		if scoped != code and link_readable("Item", scoped):
			return scoped
		if scoped != code and not frappe.db.exists("Item", scoped):
			retried = dict(values)
			retried["item_code"] = scoped
			return _create_item(retried)
		raise
	return doc.name


def _usable_party_by_name(doctype: str, name: str) -> str | None:
	"""Same display name, but only a party this company may read."""
	import frappe

	if link_readable(doctype, name):
		return name
	display = "supplier_name" if doctype == "Supplier" else "customer_name"
	for candidate in frappe.get_all(doctype, filters={display: name}, pluck="name"):
		if link_readable(doctype, candidate):
			return candidate
	return None


def _existing_party(doctype: str, name: str, tax_id: str | None) -> str | None:
	matched = party_by_trn(doctype, tax_id)
	if matched:
		return matched
	return _usable_party_by_name(doctype, name)


def _has_address(values: dict[str, str]) -> bool:
	return bool(
		(values.get("address_line1") or "").strip()
		and (values.get("city") or "").strip()
		and (values.get("state") or "").strip()
	)


def _attach_address_contact(link_doctype: str, link_name: str, title: str, values: dict[str, str]) -> None:
	import frappe
	from frappe import _

	line1 = values.get("address_line1") or ""
	city = values.get("city") or ""
	state = values.get("state") or ""
	if not (line1 and city and state):
		frappe.throw(_("Address line, city, and emirate are required"))
	addr = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Billing",
			"address_line1": line1,
			"city": city,
			"state": state,
			"country": "United Arab Emirates",
			"email_id": values.get("email_id") or None,
			"phone": values.get("phone") or None,
			"links": [{"link_doctype": link_doctype, "link_name": link_name}],
		}
	)
	if frappe.get_meta("Address").has_field("emirate"):
		addr.set("emirate", state)
	addr.insert()
	primary: dict[str, Any] = {}
	if link_doctype == "Supplier":
		primary["supplier_primary_address"] = addr.name
	else:
		primary["customer_primary_address"] = addr.name
	email = values.get("email_id") or ""
	phone = values.get("phone") or ""
	if email or phone:
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": title,
				"email_id": email or None,
				"mobile_no": phone or None,
				"links": [{"link_doctype": link_doctype, "link_name": link_name}],
			}
		)
		contact.insert()
		if link_doctype == "Supplier":
			primary["supplier_primary_contact"] = contact.name
		else:
			primary["customer_primary_contact"] = contact.name
	frappe.db.set_value(link_doctype, link_name, primary, update_modified=False)


def apply_created_links(extracted: dict[str, Any], created: dict[str, str]) -> None:
	"""Point the extract header/items at masters just created.

	Always overwrite Link values. A second LLM read often leaves a different
	party/item string than the clerk confirmed; keeping the stale name makes
	Save return needConsent and look like a no-op.
	"""
	data = extracted.get("extracted_data") or {}
	header = data.get("header")
	if isinstance(header, dict):
		if created.get("supplier"):
			header["supplier"] = created["supplier"]
		if created.get("customer"):
			header["customer"] = created["customer"]
	items = data.get("items") or []
	default_item = created.get("item_code")
	for idx, row in enumerate(items):
		if not isinstance(row, dict):
			continue
		code = created.get(f"item:{idx}") or default_item
		if code:
			row["item_code"] = code
