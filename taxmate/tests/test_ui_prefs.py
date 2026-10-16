"""SPA ↔ User language/theme mapping."""

from __future__ import annotations

import unittest

from taxmate.api.ui_prefs import spa_lang_from_user, spa_theme_from_desk, desk_theme_from_spa


class TestUiPrefsMap(unittest.TestCase):
	def test_lang(self):
		self.assertEqual(spa_lang_from_user("ar"), "ar")
		self.assertEqual(spa_lang_from_user("en"), "en")
		self.assertEqual(spa_lang_from_user("en-GB"), "en")
		self.assertIsNone(spa_lang_from_user(""))
		self.assertIsNone(spa_lang_from_user("fr"))

	def test_theme(self):
		self.assertEqual(spa_theme_from_desk("Dark"), "dark")
		self.assertEqual(spa_theme_from_desk("Light"), "light")
		self.assertEqual(spa_theme_from_desk("Automatic"), "system")
		self.assertIsNone(spa_theme_from_desk(""))
		self.assertEqual(desk_theme_from_spa("dark"), "Dark")
