"""Pure tests for Scan upload MIME prep (no site).

Callers: unittest only. Covers taxmate.idp.upload_prep used by idp_desk.upload.
No data files — synthetic JPEG/PNG/PDF magic bytes only.
User: foolproof Scan so camera MIME quirks do not fail as a generic read error.

Run: PYTHONPATH=apps/taxmate python -m unittest taxmate.tests.test_upload_prep
"""

from __future__ import annotations

import unittest

from taxmate.idp.upload_prep import is_heic, normalize_upload_headers, sniff_mime


class TestUploadPrep(unittest.TestCase):
	def test_sniff_jpeg(self):
		self.assertEqual(sniff_mime(b"\xff\xd8\xff\xe0rest"), ("image/jpeg", ".jpg"))

	def test_sniff_png(self):
		self.assertEqual(sniff_mime(b"\x89PNG\r\n\x1a\nrest"), ("image/png", ".png"))

	def test_sniff_pdf(self):
		self.assertEqual(sniff_mime(b"%PDF-1.4 rest"), ("application/pdf", ".pdf"))

	def test_octet_stream_jpeg_gets_mime_and_ext(self):
		out = normalize_upload_headers("image", "application/octet-stream", b"\xff\xd8\xff\xe0abcd")
		self.assertTrue(out["ok"])
		self.assertEqual(out["content_type"], "image/jpeg")
		self.assertTrue(str(out["file_name"]).endswith(".jpg"))

	def test_image_jpg_alias(self):
		out = normalize_upload_headers("shot.jpg", "image/jpg", b"\xff\xd8\xff\xe0abcd")
		self.assertTrue(out["ok"])
		self.assertEqual(out["content_type"], "image/jpeg")

	def test_empty_rejected(self):
		out = normalize_upload_headers("x.jpg", "image/jpeg", b"")
		self.assertFalse(out["ok"])
		self.assertEqual(out["error_key"], "idp.emptyFile")

	def test_heic_rejected_by_brand(self):
		payload = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
		out = normalize_upload_headers("IMG.HEIC", "image/heic", payload)
		self.assertFalse(out["ok"])
		self.assertEqual(out["error_key"], "idp.needJpeg")
		self.assertTrue(is_heic(payload, "image/heic", "IMG.HEIC"))

	def test_unknown_octet_rejected(self):
		out = normalize_upload_headers("blob", "application/octet-stream", b"not-a-real-file")
		self.assertFalse(out["ok"])
		self.assertEqual(out["error_key"], "idp.file")


if __name__ == "__main__":
	unittest.main()
