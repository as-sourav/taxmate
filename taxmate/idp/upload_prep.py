"""Prepare an uploaded Scan file before IDP validates MIME/size.

Camera WebViews often send ``application/octet-stream``, ``image/jpg``, or
HEIC. IDP only accepts a fixed MIME set — normalize when we can, reject with
a clear key when we cannot.

Callers: taxmate.api.idp_desk.upload. Grep found no prior upload_prep module.
No dated data files — in-memory bytes only (e.g. JPEG magic ``FF D8 FF``).
"""

from __future__ import annotations

from typing import Any

# Sniff → (mime, extension)
_MAGIC: list[tuple[bytes, str, str]] = [
	(b"%PDF", "application/pdf", ".pdf"),
	(b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
	(b"\xff\xd8\xff", "image/jpeg", ".jpg"),
]

_ALIAS_MIME = {
	"image/jpg": "image/jpeg",
	"image/pjpeg": "image/jpeg",
	"image/x-png": "image/png",
}


def sniff_mime(content: bytes) -> tuple[str, str] | None:
	"""Return (mime, ext) from magic bytes, or None."""
	if not content:
		return None
	for magic, mime, ext in _MAGIC:
		if content.startswith(magic):
			return mime, ext
	# RIFF....WEBP
	if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
		return "image/webp", ".webp"
	return None


def is_heic(content: bytes, content_type: str, file_name: str) -> bool:
	"""True when the payload is HEIC/HEIF (not accepted by IDP OCR)."""
	ctype = (content_type or "").lower()
	name = (file_name or "").lower()
	if "heic" in ctype or "heif" in ctype or name.endswith((".heic", ".heif")):
		return True
	# ISO BMFF: ....ftypheic / ftypheif / ftypmif1
	if len(content) >= 12 and content[4:8] == b"ftyp":
		brand = content[8:12].lower()
		if brand in {b"heic", b"heif", b"mif1", b"msf1", b"hevx"}:
			return True
	return False


def normalize_upload_headers(file_name: str, content_type: str, content: bytes) -> dict[str, Any]:
	"""Decide MIME + filename for IDP, or an error_key for the SPA."""
	name = (file_name or "document").strip() or "document"
	ctype = (content_type or "").lower().split(";")[0].strip()

	if not content:
		return {"ok": False, "error_key": "idp.emptyFile"}

	if is_heic(content, ctype, name):
		return {"ok": False, "error_key": "idp.needJpeg"}

	ctype = _ALIAS_MIME.get(ctype, ctype)
	sniffed = sniff_mime(content)

	if ctype in {"", "application/octet-stream", "binary/octet-stream"}:
		if not sniffed:
			return {"ok": False, "error_key": "idp.file"}
		ctype, ext = sniffed
		if "." not in name:
			name = f"{name}{ext}"
	elif sniffed and ctype.startswith("image/") and sniffed[0] != ctype:
		# Trust magic over a wrong camera Content-Type.
		ctype, ext = sniffed
		if not name.lower().endswith(ext) and "." not in name:
			name = f"{name}{ext}"
	elif sniffed is None and ctype not in {
		"application/pdf",
		"image/png",
		"image/jpeg",
		"image/webp",
		"image/tiff",
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		"application/vnd.ms-excel",
		"text/csv",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	}:
		return {"ok": False, "error_key": "idp.file"}

	# Ensure image/jpeg uploads have a usable extension for IDP's fallback map.
	if ctype == "image/jpeg" and not name.lower().endswith((".jpg", ".jpeg")):
		name = f"{name}.jpg"
	if ctype == "image/png" and not name.lower().endswith(".png"):
		name = f"{name}.png"
	if ctype == "application/pdf" and not name.lower().endswith(".pdf"):
		name = f"{name}.pdf"

	return {"ok": True, "file_name": name, "content_type": ctype, "content": content}
