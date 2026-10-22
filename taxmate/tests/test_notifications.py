"""Inbox API: own unread logs, open ToDos, company filter, mark-read.

Run: bench --site taxmate.site run-tests --module taxmate.tests.test_notifications
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

import frappe
from frappe.tests.utils import FrappeTestCase

from taxmate.api import get_catalog
from taxmate.api.notifications import list_inbox, mark_all_read, mark_read
from taxmate.utils import company as company_utils


class TestNotificationInbox(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.user_a = self._user("a")
		self.user_b = self._user("b")
		self._saved_company = frappe.defaults.get_defaults_for("Administrator").get(
			company_utils.ACTIVE_COMPANY_KEY
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		if self._saved_company:
			frappe.defaults.set_user_default(
				company_utils.ACTIVE_COMPANY_KEY, self._saved_company, user="Administrator"
			)
		else:
			frappe.defaults.clear_user_default(company_utils.ACTIVE_COMPANY_KEY, user="Administrator")

	def _user(self, suffix: str) -> str:
		email = f"inbox-{suffix}-{uuid.uuid4().hex[:8]}@example.com"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": f"Inbox {suffix}",
				"send_welcome_email": 0,
				"user_type": "System User",
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		return email

	def _log(self, user: str, subject: str, document_type: str | None = None, document_name: str | None = None):
		doc = frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"subject": subject,
				"type": "Alert",
				"document_type": document_type,
				"document_name": document_name,
				"read": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _todo(self, user: str, description: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": user,
				"description": description,
				"status": "Open",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _names(self, payload: dict) -> set[str]:
		return {row["name"] for row in payload["items"]}

	def test_guest_calls_require_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.AuthenticationError):
			list_inbox()
		with self.assertRaises(frappe.AuthenticationError):
			mark_read("missing")
		with self.assertRaises(frappe.AuthenticationError):
			mark_all_read()

	def test_inbox_hides_another_users_rows(self):
		mine = self._log(self.user_a, "Mine")
		theirs = self._log(self.user_b, "Theirs")
		my_todo = self._todo(self.user_a, "My task")
		their_todo = self._todo(self.user_b, "Their task")
		frappe.set_user(self.user_a)
		names = self._names(list_inbox())
		self.assertIn(mine, names)
		self.assertIn(my_todo, names)
		self.assertNotIn(theirs, names)
		self.assertNotIn(their_todo, names)

	def test_mark_read_rejects_another_users_log(self):
		theirs = self._log(self.user_b, "Theirs")
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError):
			mark_read(theirs)
		self.assertEqual(frappe.db.get_value("Notification Log", theirs, "read"), 0)

	def test_mark_read_rejects_missing_name(self):
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError):
			mark_read(f"missing-{uuid.uuid4().hex}")

	def test_mark_read_clears_own_log_from_inbox(self):
		mine = self._log(self.user_a, "Mine")
		frappe.set_user(self.user_a)
		self.assertEqual(mark_read(mine), {"name": mine, "read": 1})
		self.assertEqual(frappe.db.get_value("Notification Log", mine, "read"), 1)
		self.assertNotIn(mine, self._names(list_inbox()))

	def test_mark_all_read_leaves_other_user_unread(self):
		mine = self._log(self.user_a, "Mine")
		theirs = self._log(self.user_b, "Theirs")
		frappe.set_user(self.user_a)
		marked = mark_all_read()
		self.assertGreaterEqual(marked["marked"], 1)
		self.assertEqual(frappe.db.get_value("Notification Log", mine, "read"), 1)
		self.assertEqual(frappe.db.get_value("Notification Log", theirs, "read"), 0)

	def test_todo_title_drops_desk_url(self):
		name = self._todo(
			self.user_a,
			"Review the filing\n\nhttps://books.example/app/uae-esr-filing/ESR-1",
		)
		frappe.set_user(self.user_a)
		row = next(item for item in list_inbox()["items"] if item["name"] == name)
		self.assertNotIn("http", row["title"])
		self.assertNotIn("/app", row["title"])
		self.assertIn("Review the filing", row["title"])
		self.assertFalse(row["can_mark_read"])
		self.assertIsNone(row["route"])

	def test_log_subject_is_plain_text(self):
		name = self._log(self.user_a, "<b>VAT</b> due")
		frappe.set_user(self.user_a)
		row = next(item for item in list_inbox()["items"] if item["name"] == name)
		self.assertEqual(row["title"], "VAT due")
		self.assertNotIn("email_content", row)
		self.assertTrue(row["can_mark_read"])
		self.assertTrue(row["id"].startswith("log:"))

	def test_other_company_document_is_omitted(self):
		companies = frappe.get_all("Company", pluck="name", limit=2)
		if len(companies) < 2:
			self.skipTest("needs two companies")
		home, other = companies[0], companies[1]
		account = frappe.db.get_value("Account", {"company": other, "is_group": 0}, "name")
		if not account:
			self.skipTest("needs a leaf account on the second company")
		company_utils.set_active_company(home)
		linked = self._log("Administrator", "Other company", "Account", account)
		loose = self._log("Administrator", "No document")
		names = self._names(list_inbox())
		self.assertNotIn(linked, names)
		self.assertIn(loose, names)

	def test_mark_all_read_leaves_other_company_unread(self):
		companies = frappe.get_all("Company", pluck="name", limit=2)
		if len(companies) < 2:
			self.skipTest("needs two companies")
		home, other = companies[0], companies[1]
		home_account = frappe.db.get_value("Account", {"company": home, "is_group": 0}, "name")
		other_account = frappe.db.get_value("Account", {"company": other, "is_group": 0}, "name")
		if not home_account or not other_account:
			self.skipTest("needs a leaf account on each company")
		company_utils.set_active_company(home)
		visible = self._log("Administrator", "Home", "Account", home_account)
		hidden = self._log("Administrator", "Away", "Account", other_account)
		mark_all_read()
		self.assertEqual(frappe.db.get_value("Notification Log", visible, "read"), 1)
		self.assertEqual(frappe.db.get_value("Notification Log", hidden, "read"), 0)

	def test_catalog_lists_inbox_methods(self):
		names = {row["name"] for row in get_catalog()["actions"]}
		self.assertIn("list_inbox", names)
		self.assertIn("mark_read", names)
		self.assertIn("mark_all_read", names)

	def test_esr_route_stays_inside_the_spa(self):
		company = company_utils.get_default_company() or frappe.db.get_value("Company", {}, "name")
		self.assertTrue(company)
		year = 1800 + (uuid.uuid4().int % 100)
		filing = frappe.get_doc(
			{
				"doctype": "UAE ESR Filing",
				"company": company,
				"financial_year_start": f"{year}-01-01",
				"financial_year_end": f"{year}-12-31",
				"regulatory_authority": "Inbox Test Authority",
			}
		).insert(ignore_permissions=True)
		self._log(self.user_a, "ESR due", "UAE ESR Filing", filing.name)
		frappe.set_user(self.user_a)
		row = next(item for item in list_inbox()["items"] if item["document_name"] == filing.name)
		self.assertEqual(row["route"], f"/esr/{quote(filing.name, safe='')}")
		self.assertNotIn("/app", row["route"])

	def test_arabic_vat_reminder_uses_the_user_language(self):
		from taxmate.uae_vat.notifications import vat_201_reminder_text

		frappe.translate.clear_cache()
		frappe.local.lang = "ar"
		text = vat_201_reminder_text(
			"Al Madina Hypermarket LLC", "2026-09-30", "2026-10-28", today="2026-10-01"
		)
		self.assertIn("ضريبة القيمة المضافة", text)
		self.assertIn("Al Madina Hypermarket LLC", text)
		self.assertNotIn("Prepare the accountant pack", text)
