"""Run TaxMate financial and UAE reports."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from taxmate.api import catalog_reports
from taxmate.api.resource import _parse, assert_company_read, require_login
from taxmate.utils.company import get_default_company
from taxmate.utils.localize import localize_report


def assert_allowed_report(report_name: str) -> None:
	allowed = {row["report"] for row in catalog_reports()}
	if report_name not in allowed:
		frappe.throw(
			_("Report {0} is not part of the TaxMate accounts API").format(report_name),
			frappe.PermissionError,
		)


@frappe.whitelist()
def list_reports() -> list[dict[str, str]]:
	require_login()
	return catalog_reports()


@frappe.whitelist()
def run_report(report_name: str, filters=None, ignore_prepared_report: bool = True) -> dict[str, Any]:
	require_login()
	assert_allowed_report(report_name)
	filters = _as_filter_dict(filters)
	# Sidebar reports follow the company in the header. A caller-supplied
	# company is replaced so one request cannot read another mapped company.
	active = get_default_company()
	if active:
		filters["company"] = active
	assert_company_read(filters.get("company"))
	from frappe.desk.query_report import run

	result = run(
		report_name,
		filters=filters,
		ignore_prepared_report=ignore_prepared_report,
		are_default_filters=False,
	)
	# Report id stays English for the route. The heading and account labels follow User.language.
	if isinstance(result, dict):
		localize_report(report_name, result)
	return result


def _as_filter_dict(filters) -> dict:
	filters = _parse(filters)
	if filters is None:
		return {}
	if isinstance(filters, dict):
		return filters
	frappe.throw(_("filters must be a JSON object"), frappe.ValidationError)
