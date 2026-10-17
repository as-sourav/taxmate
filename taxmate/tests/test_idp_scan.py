"""Frozen Scan contract tests (no site OCR).

Callers: ``python -m unittest taxmate.tests.test_idp_scan``.
Covers save(scan_id) without re-extract. User: "Implement the plan as specified…"
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestSaveRequiresScanId(unittest.TestCase):
	def test_save_create_rejects_missing_scan_id(self):
		import taxmate.api.idp_desk as desk

		planned = {"ok": True, "doctype": "Purchase Invoice", "route": "/taxmate/purchase-invoices"}
		with patch.object(desk, "_plan", return_value=planned):
			with patch.object(desk, "require_login"):
				out = desk.save(
					action="create",
					target_doctype="Purchase Invoice",
					file_url="/private/files/x.png",
					scan_id=None,
				)
		self.assertFalse(out.get("ok"))
		self.assertEqual(out.get("error_key"), "idp.missing")


class TestFrozenExtractUsedOnSave(unittest.TestCase):
	def test_save_create_does_not_call_read(self):
		import taxmate.api.idp_desk as desk
		from taxmate.idp import scan as scan_mod

		frozen = {
			"success": True,
			"ocr_language": "en",
			"extracted_data": {
				"doctype": "Purchase Invoice",
				"header": {"bill_no": "INV-1", "grand_total": 100},
				"items": [],
			},
			"validation": {"is_valid": True, "errors": [], "warnings": [], "missing_masters": []},
		}
		scan_doc = MagicMock()
		scan_doc.status = scan_mod.READY
		scan_doc.cancel_requested = 0
		scan_doc.file_url = "/private/files/x.png"
		scan_doc.extraction_data = frozen

		planned = {
			"ok": True,
			"doctype": "Purchase Invoice",
			"route": "/taxmate/purchase-invoices",
			"save_key": "idp.saveDraft",
		}

		with (
			patch.object(desk, "require_login"),
			patch.object(desk, "_plan", return_value=planned),
			patch.object(scan_mod, "assert_scan_access", return_value=scan_doc),
			patch.object(scan_mod, "frozen_extracted", return_value=frozen),
			patch.object(desk, "_read") as read_mock,
			patch("taxmate.idp.masters.split_missing", return_value=([], [])),
			patch("taxmate.idp.masters.release_currency_company"),
			patch("taxmate.idp.masters.release_address_links"),
			patch("taxmate.idp.masters.build_proposals", return_value=[]),
			patch("taxmate.idp.masters.proposals_complete", return_value=True),
			patch("taxmate.idp.masters.merge_proposal_values", return_value=[]),
			patch.object(
				desk,
				"draft_instructions",
				return_value={
					"ok": True,
					"doctype": "Purchase Invoice",
					"header": {"bill_no": "INV-1"},
					"items": [],
				},
			),
			patch.object(desk, "finish_draft", return_value=({"bill_no": "INV-1"}, [])),
			patch.object(desk, "_draft_defaults", return_value={}),
			patch.object(desk, "_fills", return_value={}),
			patch.object(desk, "_proposals", return_value=[]),
			patch.object(desk, "_coerce_proposal_defaults", return_value=[]),
			patch.object(desk, "_context", return_value=MagicMock()),
			patch("idp.tools.create_document.create_document") as create_mock,
			patch.object(scan_mod, "mark_scan"),
		):
			create_mock.return_value = MagicMock(
				success=True, data={"name": "PINV-1", "docstatus": 0}
			)
			out = desk._save_create(
				planned,
				"/private/files/x.png",
				fills="{}",
				submit="",
				proposals="[]",
				scan_id="IDPLOG-TEST",
			)

		read_mock.assert_not_called()
		self.assertTrue(out.get("ok"))
		self.assertEqual(out.get("name"), "PINV-1")
		self.assertEqual(out.get("scan_id"), "IDPLOG-TEST")


class TestPipelineVersion(unittest.TestCase):
	def test_pipeline_version_is_int(self):
		from taxmate.idp.scan import PIPELINE_VERSION

		self.assertIsInstance(PIPELINE_VERSION, int)
		self.assertGreaterEqual(PIPELINE_VERSION, 1)


class TestJsonValueForSetValue(unittest.TestCase):
	"""Regression: raw dict into set_value on JSON columns → MariaDB 1064."""

	def test_dict_is_json_encoded(self):
		import json

		from taxmate.idp.jobs import _json_value

		out = _json_value({"uploaded": 141.1})
		self.assertIsInstance(out, str)
		self.assertEqual(json.loads(out), {"uploaded": 141.1})
		# Python dict repr would use single quotes and break SQL.
		self.assertNotIn("'", out)

	def test_none_and_str(self):
		from taxmate.idp.jobs import _json_value

		self.assertEqual(_json_value(None), "{}")
		self.assertEqual(_json_value('{"a": 1}'), '{"a": 1}')


class TestGetScanFailedDetail(unittest.TestCase):
	def test_failed_includes_error_message_detail(self):
		import taxmate.api.idp_desk as desk
		from taxmate.idp import scan as scan_mod

		doc = MagicMock()
		doc.status = scan_mod.FAILED
		doc.error_key = "idp.readFailed"
		doc.error_message = "(1064, \"syntax error near 'uploaded': 1}\")"
		doc.name = "IDPLOG-FAIL"
		doc.file_url = "/private/files/x.png"
		doc.target_doctype = "Purchase Invoice"

		with (
			patch.object(desk, "require_login"),
			patch("taxmate.idp.scan.assert_scan_access", return_value=doc),
			patch(
				"taxmate.idp.scan.scan_payload",
				return_value={"ok": True, "status": scan_mod.FAILED, "scan_id": "IDPLOG-FAIL"},
			),
		):
			out = desk.get_scan("IDPLOG-FAIL", "Purchase Invoice")

		self.assertFalse(out.get("ok"))
		self.assertEqual(out.get("error_key"), "idp.readFailed")
		self.assertIn("1064", out.get("detail") or "")


if __name__ == "__main__":
	unittest.main()
