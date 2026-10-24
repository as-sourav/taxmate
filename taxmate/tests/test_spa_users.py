"""SPA team admin tests: invite then set role. User stays off catalog.

Run: bench --site taxmate.site run-tests --module taxmate.tests.test_spa_users
"""

from __future__ import annotations

import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint

from taxmate.api import get_catalog, get_session
from taxmate.api.resource import is_allowed_doctype
from taxmate.api.users import (
	change_password,
	get_profile,
	get_user,
	invite_user,
	list_users,
	onboard_company_owner,
	set_user_enabled,
	set_user_role,
	update_profile,
	update_user,
)
from taxmate.setup.company_owner import OWNER_FIELD, ensure_company_owner_field
from taxmate.setup.spa_roles import MARKER, ensure_spa_roles, spa_role_of


class TestSpaUsers(FrappeTestCase):
	def setUp(self):
		ensure_spa_roles()
		ensure_company_owner_field()
		self._owner_names: list[str] = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in getattr(self, "_owner_names", []):
			self._delete(name)

	def _use_company(self, company: str, user: str | None = None) -> None:
		from taxmate.utils.company import ACTIVE_COMPANY_KEY

		user = user or frappe.session.user
		frappe.defaults.set_user_default(ACTIVE_COMPANY_KEY, company, user)
		frappe.defaults.set_user_default("company", company, user)

	def _company(self) -> str:
		from taxmate.utils.company import get_default_company

		company = get_default_company()
		if not company:
			company = frappe.db.get_value("Company", {}, "name")
			self.assertTrue(company, "site has no company")
			self._use_company(company)
		return company

	def _act_as_company_owner(self, company: str | None = None) -> dict:
		"""Administrator onboards a primary owner, then switch session to them."""
		frappe.set_user("Administrator")
		company = company or self._company()
		self._use_company(company, "Administrator")
		email = f"tm-owner-{uuid.uuid4().hex[:8]}@example.com"
		owner = onboard_company_owner(
			company=company,
			email=email,
			first_name="TaxMate",
			last_name="Owner",
			send_welcome_email=0,
		)
		self._owner_names.append(owner["name"])
		self._use_company(company, owner["name"])
		frappe.set_user(owner["name"])
		return owner

	def _invite(self, spa_role: str = "clerk") -> dict:
		if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
			self._act_as_company_owner()
		email = f"tm-{spa_role}-{uuid.uuid4().hex[:8]}@example.com"
		return invite_user(
			email=email,
			first_name="TaxMate",
			last_name=spa_role.title(),
			spa_role=spa_role,
			send_welcome_email=0,
		)

	def _delete(self, name: str) -> None:
		if name and frappe.db.exists("User", name):
			# Clear company owner link if this user is primary owner.
			for company in frappe.get_all(
				"Company", filters={OWNER_FIELD: name}, pluck="name"
			):
				frappe.db.set_value("Company", company, OWNER_FIELD, None, update_modified=False)
			frappe.db.delete("User Permission", {"user": name})
			frappe.delete_doc("User", name, force=True, ignore_permissions=True)

	def test_session_returns_spa_role(self):
		session = get_session()
		self.assertTrue(session.get("is_app_provider"))
		self.assertFalse(session.get("spa_roles"))
		self.assertIn(session.get("spa_role"), (None, "", False))


	def test_administrator_cannot_invite(self):
		frappe.set_user("Administrator")
		self._company()
		with self.assertRaises(frappe.PermissionError):
			invite_user(
				email=f"tm-admin-invite-{uuid.uuid4().hex[:8]}@example.com",
				first_name="Nope",
				spa_role="clerk",
				send_welcome_email=0,
			)

	def test_onboard_company_owner_maps_user(self):
		frappe.set_user("Administrator")
		company = self._company()
		email = f"tm-onboard-{uuid.uuid4().hex[:8]}@example.com"
		created = onboard_company_owner(
			company=company,
			email=email,
			first_name="Org",
			last_name="Owner",
			send_welcome_email=0,
		)
		try:
			self.assertEqual(created["name"], email)
			self.assertEqual(created["spa_role"], "owner")
			self.assertEqual(frappe.db.get_value("Company", company, OWNER_FIELD), email)
			self.assertIn(MARKER["owner"], frappe.get_roles(email))
			rows = frappe.get_all(
				"User Permission",
				filters={"user": email, "allow": "Company"},
				pluck="for_value",
			)
			self.assertEqual(rows, [company])
			self.assertNotEqual(email, "Administrator")
			frappe.set_user(email)
			self._use_company(company, email)
			clerk = invite_user(
				email=f"tm-clerk-{uuid.uuid4().hex[:8]}@example.com",
				first_name="Clerk",
				spa_role="clerk",
				send_welcome_email=0,
			)
			self.assertEqual(clerk["spa_role"], "clerk")
			self._delete(clerk["name"])
		finally:
			frappe.set_user("Administrator")
			self._delete(email)

	def test_cannot_onboard_administrator_as_owner(self):
		frappe.set_user("Administrator")
		company = self._company()
		with self.assertRaises(frappe.ValidationError):
			onboard_company_owner(
				company=company,
				email="Administrator",
				first_name="Admin",
				send_welcome_email=0,
			)

	def test_catalog_exposes_user_actions_not_user_resource(self):
		catalog = get_catalog()
		doctypes = {row["doctype"] for row in catalog["resources"]}
		self.assertNotIn("User", doctypes)
		self.assertFalse(is_allowed_doctype("User"))
		methods = {row["method"] for row in catalog["actions"]}
		self.assertIn("taxmate.api.users.list_users", methods)
		self.assertIn("taxmate.api.users.get_user", methods)
		self.assertIn("taxmate.api.users.invite_user", methods)
		self.assertIn("taxmate.api.users.onboard_company_owner", methods)
		self.assertIn("taxmate.api.users.update_user", methods)
		self.assertIn("taxmate.api.users.set_user_role", methods)
		self.assertIn("taxmate.api.users.set_user_enabled", methods)
		self.assertIn("taxmate.api.users.reset_user_password", methods)
		self.assertIn("taxmate.api.users.get_profile", methods)
		self.assertIn("taxmate.api.users.update_profile", methods)
		self.assertIn("taxmate.api.users.change_password", methods)

	def test_accounts_manager_can_read_quotation(self):
		# Callers: QuotationList via taxmate.api.resource.get_list.
		# Schema: Custom DocPerm parent=Quotation, role, permlevel 0, if_owner 0.
		row = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "Quotation", "role": "Accounts Manager", "permlevel": 0, "if_owner": 0},
			["read", "select", "create", "submit", "cancel"],
			as_dict=True,
		)
		self.assertIsNotNone(row)
		self.assertEqual(cint(row.read), 1)
		self.assertEqual(cint(row.select), 1)
		self.assertEqual(cint(row.create), 1)
		self.assertEqual(cint(row.submit), 1)
		self.assertEqual(cint(row.cancel), 1)
		clerk = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "Quotation", "role": "Accounts User", "permlevel": 0, "if_owner": 0},
			["read", "create", "cancel"],
			as_dict=True,
		)
		self.assertEqual(cint(clerk.read), 1)
		self.assertEqual(cint(clerk.create), 1)
		self.assertEqual(cint(clerk.cancel), 0)

	def test_invite_then_set_role(self):
		created = self._invite("clerk")
		try:
			self.assertEqual(created["spa_role"], "clerk")
			self.assertEqual(spa_role_of(created["name"]), "clerk")
			roles = frappe.get_roles(created["name"])
			self.assertNotIn("System Manager", roles)
			self.assertIn("TaxMate Accounts User", roles)
			self.assertIn("Accounts User", roles)
			self.assertNotIn("Accounts Manager", roles)
			user = frappe.get_doc("User", created["name"])
			self.assertTrue(user.has_desk_access())
			self.assertEqual(user.redirect_url, "/taxmate")
			updated = set_user_role(user=created["name"], spa_role="accountant")
			self.assertEqual(updated["spa_role"], "accountant")
			self.assertEqual(spa_role_of(created["name"]), "accountant")
			self.assertIn("Accounts Manager", frappe.get_roles(created["name"]))
			self.assertTrue(frappe.get_doc("User", created["name"]).has_desk_access())
			disabled = set_user_enabled(user=created["name"], enabled=0)
			self.assertEqual(disabled["enabled"], 0)
			names = {row["name"] for row in list_users()}
			self.assertIn(created["name"], names)
		finally:
			self._delete(created["name"])

	def test_get_and_update_user(self):
		created = self._invite("clerk")
		try:
			row = get_user(user=created["name"])
			self.assertEqual(row["name"], created["name"])
			self.assertEqual(row["spa_role"], "clerk")
			updated = update_user(
				user=created["name"],
				first_name="Renamed",
				last_name="Teammate",
				mobile_no="+971500000099",
			)
			self.assertEqual(updated["first_name"], "Renamed")
			self.assertEqual(updated["mobile_no"], "+971500000099")
		finally:
			self._delete(created["name"])

	def test_multi_spa_roles_union(self):
		"""Multiple TaxMate markers are stored; Frappe unions DocPerms (highest wins UI)."""
		from taxmate.setup.spa_roles import MARKER, apply_spa_roles, spa_roles_of

		self._act_as_company_owner()
		email = f"tm-multi-{uuid.uuid4().hex[:8]}@example.com"
		created = invite_user(
			email=email,
			first_name="Multi",
			spa_roles=["clerk", "viewer"],
			send_welcome_email=0,
		)
		try:
			self.assertEqual(set(created["spa_roles"]), {"clerk", "viewer"})
			self.assertEqual(created["spa_role"], "clerk")
			roles = set(frappe.get_roles(created["name"]))
			self.assertIn(MARKER["clerk"], roles)
			self.assertIn(MARKER["viewer"], roles)
			updated = set_user_role(
				user=created["name"],
				spa_roles=["accountant", "clerk"],
			)
			self.assertEqual(set(updated["spa_roles"]), {"accountant", "clerk"})
			self.assertEqual(updated["spa_role"], "accountant")
			self.assertEqual(set(spa_roles_of(created["name"])), {"accountant", "clerk"})
			# Union: accountant cancel + clerk create both present via DocPerms
			frappe.set_user(created["name"])
			self.assertTrue(frappe.has_permission("Sales Invoice", "create"))
			self.assertTrue(frappe.has_permission("Sales Invoice", "cancel"))
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])

	def test_spa_roles_have_no_desk_administrator_does(self):
		ensure_spa_roles()
		for name in MARKER.values():
			self.assertEqual(cint(frappe.db.get_value("Role", name, "desk_access")), 0)
		self.assertTrue(frappe.get_doc("User", "Administrator").has_desk_access())

	def test_invite_stores_mobile_and_last_name(self):
		self._act_as_company_owner()
		email = f"tm-full-{uuid.uuid4().hex[:8]}@example.com"
		created = invite_user(
			email=email,
			first_name="Mariam",
			last_name="Hassan",
			mobile_no="+971500000001",
			spa_role="viewer",
			send_welcome_email=0,
		)
		try:
			self.assertEqual(created["last_name"], "Hassan")
			self.assertEqual(created["mobile_no"], "+971500000001")
			self.assertEqual(created["spa_role"], "viewer")
			self.assertFalse(frappe.get_doc("User", created["name"]).has_desk_access())
		finally:
			self._delete(created["name"])

	def test_cannot_change_system_manager(self):
		from frappe.utils import random_string

		email = f"tm-sm-{uuid.uuid4().hex[:8]}@example.com"
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = "Sys"
		user.user_type = "System User"
		user.send_welcome_email = 0
		user.new_password = random_string(16)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.append("roles", {"role": "System Manager"})
		user.save(ignore_permissions=True)
		try:
			# As Administrator (provider), Team writes are denied.
			with self.assertRaises(frappe.PermissionError):
				set_user_role(user=user.name, spa_role="clerk")
			with self.assertRaises(frappe.PermissionError):
				set_user_enabled(user=user.name, enabled=0)
			owner = self._act_as_company_owner()
			with self.assertRaises(frappe.PermissionError):
				set_user_role(user=user.name, spa_role="clerk")
			names = {row["name"] for row in list_users()}
			self.assertNotIn(user.name, names)
		finally:
			frappe.set_user("Administrator")
			self._delete(user.name)

	def test_accounts_manager_role_deletes_a_draft_without_new_perms(self):
		"""Draft delete comes from the standard Accounts Manager role.

		Caller: taxmate.api.resource.delete via PurchaseInvoiceDetail.
		User: use standard Frappe roles. Add the role to the user. Do not add
		permissions onto a role that did not already have them.
		"""
		from taxmate.setup.spa_roles import _perm_values, apply_spa_roles

		self.assertEqual(_perm_values("accountant", "Purchase Invoice")["delete"], 0)
		self.assertEqual(_perm_values("owner", "Purchase Invoice")["delete"], 0)
		self.assertEqual(_perm_values("clerk", "Purchase Invoice")["delete"], 0)
		accountant = self._invite("accountant")
		clerk = self._invite("clerk")
		try:
			self.assertIn("Accounts Manager", frappe.get_roles(accountant["name"]))
			self.assertIn("Accounts User", frappe.get_roles(clerk["name"]))
			self.assertNotIn("Accounts Manager", frappe.get_roles(clerk["name"]))
			frappe.set_user(accountant["name"])
			self.assertTrue(frappe.has_permission("Purchase Invoice", "delete"))
			frappe.set_user(clerk["name"])
			self.assertFalse(frappe.has_permission("Purchase Invoice", "delete"))
			apply_spa_roles(accountant["name"], ["accountant"])
			self.assertIn("Accounts Manager", frappe.get_roles(accountant["name"]))
		finally:
			frappe.set_user("Administrator")
			self._delete(accountant["name"])
			self._delete(clerk["name"])

	def test_accountant_cannot_invite(self):
		accountant = self._invite("accountant")
		try:
			frappe.set_user(accountant["name"])
			with self.assertRaises(frappe.PermissionError):
				invite_user(
					email=f"tm-blocked-{uuid.uuid4().hex[:8]}@example.com",
					first_name="Blocked",
					spa_role="clerk",
					send_welcome_email=0,
				)
			list_users()
		finally:
			frappe.set_user("Administrator")
			self._delete(accountant["name"])

	def test_clerk_cannot_cancel(self):
		from taxmate.api.workflow import cancel, submit

		clerk = self._invite("clerk")
		try:
			frappe.set_user(clerk["name"])
			with self.assertRaises(frappe.PermissionError):
				cancel("Journal Entry", "JE-DOES-NOT-EXIST")
			with self.assertRaises(frappe.PermissionError):
				set_user_role(user=clerk["name"], spa_role="viewer")
		finally:
			frappe.set_user("Administrator")
			self._delete(clerk["name"])

		viewer = self._invite("viewer")
		try:
			frappe.set_user(viewer["name"])
			with self.assertRaises(frappe.PermissionError):
				submit({"doctype": "Journal Entry", "name": "JE-DOES-NOT-EXIST"})
		finally:
			frappe.set_user("Administrator")
			self._delete(viewer["name"])

	def test_clerk_cannot_invite(self):
		clerk = self._invite("clerk")
		try:
			frappe.set_user(clerk["name"])
			with self.assertRaises(frappe.PermissionError):
				invite_user(
					email=f"tm-blocked-{uuid.uuid4().hex[:8]}@example.com",
					first_name="Blocked",
					spa_role="viewer",
					send_welcome_email=0,
				)
			with self.assertRaises(frappe.PermissionError):
				list_users()
		finally:
			frappe.set_user("Administrator")
			self._delete(clerk["name"])

	def test_update_own_profile(self):
		created = self._invite("clerk")
		try:
			frappe.set_user(created["name"])
			row = get_profile()
			self.assertEqual(row["email"], created["name"])
			updated = update_profile(
				first_name="Noura",
				last_name="Ali",
				mobile_no="+971501111111",
			)
			self.assertEqual(updated["first_name"], "Noura")
			self.assertEqual(updated["last_name"], "Ali")
			self.assertEqual(updated["mobile_no"], "+971501111111")
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])

	def test_invited_clerk_can_read_books(self):
		"""Invited clerk can read Sales Invoice / Journal Entry."""
		clerk = self._invite("clerk")
		viewer = self._invite("viewer")
		try:
			frappe.set_user(clerk["name"])
			self.assertTrue(is_allowed_doctype("Sales Invoice"))
			self.assertTrue(frappe.has_permission("Sales Invoice", "read"))
			self.assertTrue(frappe.has_permission("Sales Invoice", "create"))
			self.assertTrue(frappe.has_permission("Journal Entry", "submit"))
			frappe.set_user(viewer["name"])
			self.assertTrue(frappe.has_permission("Sales Invoice", "read"))
			self.assertFalse(frappe.has_permission("Sales Invoice", "write"))
			self.assertFalse(frappe.has_permission("Sales Invoice", "create"))
		finally:
			frappe.set_user("Administrator")
			self._delete(clerk["name"])
			self._delete(viewer["name"])

	def test_change_password_rejects_wrong_current(self):
		created = self._invite("viewer")
		from frappe.utils.password import update_password

		update_password(created["name"], "TaxMate-Old-Pass1!")
		try:
			frappe.set_user(created["name"])
			# 417 ValidationError (not 401 AuthenticationError): mobile treats 401 as a dead device token.
			with self.assertRaises(frappe.ValidationError) as ctx:
				change_password(old_password="wrong", new_password="TaxMate-New-Pass1!")
			self.assertNotIsInstance(ctx.exception, frappe.AuthenticationError)
			self.assertEqual(ctx.exception.http_status_code, 417)
			change_password(old_password="TaxMate-Old-Pass1!", new_password="TaxMate-New-Pass1!")
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])

	def test_owner_is_limited_to_the_active_company(self):
		company = self._company()
		created = self._invite("owner")
		try:
			rows = frappe.get_all(
				"User Permission",
				filters={"user": created["name"], "allow": "Company"},
				pluck="for_value",
			)
			self.assertEqual(rows, [company])
			frappe.set_user(created["name"])
			from taxmate.api.accountant_dashboard import get_accountant_dashboard
			from taxmate.api.clients_dashboard import get_clients_dashboard
			from taxmate.utils.company import user_companies

			self.assertEqual(user_companies(), [company])
			self.assertRaises(frappe.PermissionError, get_clients_dashboard)
			self.assertRaises(frappe.PermissionError, get_accountant_dashboard)
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])

	def test_accountant_maps_to_each_company_and_may_open_owner_dashboard(self):
		names = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(names) < 2:
			self.skipTest("needs two companies")
		first, second = names[0], names[1]
		self._act_as_company_owner(first)
		created = invite_user(
			email=f"tm-accountant-{uuid.uuid4().hex[:8]}@example.com",
			first_name="TaxMate",
			last_name="Accountant",
			spa_role="accountant",
			send_welcome_email=0,
		)
		try:
			frappe.set_user("Administrator")
			owner2 = self._act_as_company_owner(second)
			again = invite_user(
				email=created["name"],
				first_name="TaxMate",
				spa_role="accountant",
				send_welcome_email=0,
			)
			self.assertEqual(again["name"], created["name"])
			rows = set(
				frappe.get_all(
					"User Permission",
					filters={"user": created["name"], "allow": "Company"},
					pluck="for_value",
				)
			)
			self.assertEqual(rows, {first, second})
			# Multi-company accountant is not fully owned by either company owner.
			with self.assertRaises(frappe.PermissionError):
				set_user_role(user=created["name"], spa_role="owner")
			frappe.set_user(created["name"])
			from taxmate.api.owner_dashboard import get_owner_dashboard
			from taxmate.utils.company import get_default_company, set_active_company

			set_active_company(first)
			# Accountant may load the owner KPI dashboard for a mapped company.
			data = get_owner_dashboard(company=get_default_company())
			self.assertEqual(data.get("company") or get_default_company(), first)
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])

	def test_owner_team_list_stays_inside_the_company(self):
		names = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(names) < 2:
			self.skipTest("needs two companies")
		first, second = names[0], names[1]
		owner = self._act_as_company_owner(first)
		home = invite_user(
			email=f"tm-home-{uuid.uuid4().hex[:8]}@example.com",
			first_name="Home",
			spa_role="clerk",
			send_welcome_email=0,
		)
		frappe.set_user("Administrator")
		other_owner = self._act_as_company_owner(second)
		other = invite_user(
			email=f"tm-other-{uuid.uuid4().hex[:8]}@example.com",
			first_name="Other",
			spa_role="clerk",
			send_welcome_email=0,
		)
		try:
			frappe.set_user(owner["name"])
			self._use_company(first, owner["name"])
			listed = {row["name"] for row in list_users()}
			self.assertIn(home["name"], listed)
			self.assertNotIn(other["name"], listed)
		finally:
			frappe.set_user("Administrator")
			self._delete(home["name"])
			self._delete(other["name"])
			self._delete(other_owner["name"])


	def test_accountant_team_list_follows_active_company(self):
		"""Multi-company accountant sees only the active company's roster."""
		names = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(names) < 2:
			self.skipTest("needs two companies")
		first, second = names[0], names[1]
		self._act_as_company_owner(first)
		accountant = invite_user(
			email=f"tm-acc-{uuid.uuid4().hex[:8]}@example.com",
			first_name="TaxMate",
			spa_role="accountant",
			send_welcome_email=0,
		)
		home = invite_user(
			email=f"tm-home-{uuid.uuid4().hex[:8]}@example.com",
			first_name="Home",
			spa_role="clerk",
			send_welcome_email=0,
		)
		frappe.set_user("Administrator")
		self._act_as_company_owner(second)
		invite_user(
			email=accountant["name"],
			first_name="TaxMate",
			spa_role="accountant",
			send_welcome_email=0,
		)
		other = invite_user(
			email=f"tm-other-{uuid.uuid4().hex[:8]}@example.com",
			first_name="Other",
			spa_role="clerk",
			send_welcome_email=0,
		)
		try:
			from taxmate.utils.company import set_active_company

			frappe.set_user(accountant["name"])
			set_active_company(first)
			listed = {row["name"] for row in list_users()}
			self.assertIn(home["name"], listed)
			self.assertNotIn(other["name"], listed)
			self.assertTrue(all(row.get("company") == first for row in list_users()))

			set_active_company(second)
			listed = {row["name"] for row in list_users()}
			self.assertIn(other["name"], listed)
			self.assertNotIn(home["name"], listed)
			self.assertTrue(all(row.get("company") == second for row in list_users()))
		finally:
			frappe.set_user("Administrator")
			self._delete(accountant["name"])
			self._delete(home["name"])
			self._delete(other["name"])

	def test_owner_cannot_manage_other_company_user(self):
		"""Owner of A cannot get/set_role a clerk who only belongs to B."""
		names = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(names) < 2:
			self.skipTest("needs two companies")
		first, second = names[0], names[1]
		owner = self._act_as_company_owner(first)
		frappe.set_user("Administrator")
		self._act_as_company_owner(second)
		other = invite_user(
			email=f"tm-bclerk-{uuid.uuid4().hex[:8]}@example.com",
			first_name="B",
			spa_role="clerk",
			send_welcome_email=0,
		)
		try:
			from taxmate.utils.company import set_active_company

			frappe.set_user(owner["name"])
			self._use_company(first, owner["name"])
			set_active_company(first)
			with self.assertRaises(frappe.ValidationError):
				get_user(user=other["name"])
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				set_user_role(user=other["name"], spa_role="viewer")
		finally:
			frappe.set_user("Administrator")
			self._delete(owner["name"])
			self._delete(other["name"])

	def test_invite_binds_only_active_company(self):
		company = self._company()
		created = self._invite("clerk")
		try:
			rows = frappe.get_all(
				"User Permission",
				filters={"user": created["name"], "allow": "Company"},
				pluck="for_value",
			)
			self.assertEqual(rows, [company])
			self.assertEqual(created.get("company"), company)
		finally:
			self._delete(created["name"])

	def test_lists_follow_the_company_the_user_is_in(self):
		names = frappe.get_all("Company", pluck="name", limit=2, order_by="name asc")
		if len(names) < 2:
			self.skipTest("needs two companies")
		first, second = names[0], names[1]
		self._act_as_company_owner(first)
		created = invite_user(
			email=f"tm-acc2-{uuid.uuid4().hex[:8]}@example.com",
			first_name="TaxMate",
			spa_role="accountant",
			send_welcome_email=0,
		)
		frappe.set_user("Administrator")
		self._act_as_company_owner(second)
		invite_user(
			email=created["name"],
			first_name="TaxMate",
			spa_role="accountant",
			send_welcome_email=0,
		)
		try:
			frappe.set_user(created["name"])
			from taxmate.uae.permissions import get_permission_query_conditions, has_permission
			from taxmate.utils.company import set_active_company

			set_active_company(second)
			invoice = get_permission_query_conditions(doctype="Sales Invoice")
			self.assertIn(second, invoice)
			self.assertNotIn(first, invoice)
			self.assertNotIn("IS NULL", invoice)
			item = get_permission_query_conditions(doctype="Item")
			self.assertIn("custom_company", item)
			self.assertIn(second, item)
			self.assertIn("IS NULL", item)
			self.assertNotIn(first, item)
			group = get_permission_query_conditions(doctype="UAE VAT Group")
			self.assertIn("representative_company", group)
			self.assertIn(second, group)
			rows = frappe.client.get_list(
				"Sales Invoice",
				fields=["name", "company"],
				limit_page_length=20,
			)
			self.assertTrue(all(row.company == second for row in rows))
			items = frappe.client.get_list(
				"Item",
				fields=["name", "custom_company"],
				limit_page_length=50,
			)
			self.assertTrue(all(not row.custom_company or row.custom_company == second for row in items))
			self.assertFalse(
				has_permission(frappe._dict(doctype="Sales Invoice", company=first), "read")
			)
			self.assertTrue(
				has_permission(frappe._dict(doctype="Sales Invoice", company=second), "read")
			)
			self.assertTrue(has_permission(frappe._dict(doctype="Customer", custom_company=None), "read"))
		finally:
			frappe.set_user("Administrator")
			self._delete(created["name"])
