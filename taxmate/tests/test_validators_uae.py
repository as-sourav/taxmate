"""Table-driven UAE validator tests.

Callers: python -m unittest taxmate.tests.test_validators_uae.
User: "Implement the plan as specified, it is attached for your reference."
"""

from __future__ import annotations

import unittest
from datetime import date

from taxmate.idp.validators_uae import (
	score_fields,
	validate_bill_date,
	validate_currency,
	validate_totals,
	validate_trn,
	validate_vat_amount,
)


class TestTrn(unittest.TestCase):
	def test_ok(self):
		self.assertTrue(validate_trn("100123456789012")[0])

	def test_bad_prefix(self):
		ok, flag = validate_trn("200123456789012")
		self.assertFalse(ok)
		self.assertEqual(flag, "trn_format")


class TestVatAndTotals(unittest.TestCase):
	def test_vat_5pct(self):
		self.assertTrue(validate_vat_amount(1000, 50)[0])

	def test_vat_mismatch(self):
		self.assertEqual(validate_vat_amount(1000, 40)[1], "vat_math")

	def test_totals(self):
		self.assertTrue(validate_totals(1000, 50, 1050)[0])


class TestDateCurrency(unittest.TestCase):
	def test_date_future(self):
		ok, flag = validate_bill_date("2028-01-01", today=date(2026, 10, 17))
		self.assertFalse(ok)
		self.assertEqual(flag, "date_future")

	def test_currency(self):
		self.assertTrue(validate_currency("AED")[0])


class TestScoreFields(unittest.TestCase):
	def test_flags_lower_confidence(self):
		scores = score_fields(
			{
				"supplier_trn": "bad",
				"bill_no": "INV-1",
				"bill_date": "2026-01-01",
				"currency": "AED",
				"net_total": 100,
				"tax_total": 5,
				"grand_total": 105,
			}
		)
		self.assertFalse(scores["supplier_trn"]["ok"])


if __name__ == "__main__":
	unittest.main()
