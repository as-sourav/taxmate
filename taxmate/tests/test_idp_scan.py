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


if __name__ == "__main__":
	unittest.main()
