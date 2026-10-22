"""SPA document routes shared by search and the notification inbox.

The map is the detail path for each DocType the React app already renders.
No entry points at Desk /app/.
"""

from __future__ import annotations

from urllib.parse import quote

SPA_DOC_ROUTES: dict[str, str] = {
	"Customer": "/customers/{name}",
	"Supplier": "/suppliers/{name}",
	"Sales Order": "/orders/{name}",
	"Delivery Note": "/delivery-notes/{name}",
	"Sales Invoice": "/invoices/{name}",
	"Purchase Invoice": "/purchase-invoices/{name}",
	"Purchase Order": "/purchase-orders/{name}",
	"Purchase Receipt": "/purchase-receipts/{name}",
	"Stock Entry": "/stock-entries/{name}",
	"Stock Reconciliation": "/stock-reconciliations/{name}",
	"Material Request": "/material-requests/{name}",
	"Quotation": "/quotations/{name}",
	"UAE Incoming Invoice": "/incoming-invoices/{name}",
	"Journal Entry": "/journals/{name}",
	"Account": "/accounts/{name}",
	"Warehouse": "/warehouses/{name}",
	"Sales Taxes and Charges Template": "/tax-templates/sales/{name}",
	"Purchase Taxes and Charges Template": "/tax-templates/purchase/{name}",
	"Payment Entry": "/payments/{name}",
	"Item": "/catalogue/items/{name}",
	"Item Group": "/catalogue/item-groups/{name}",
	"Brand": "/catalogue/brands/{name}",
	"UOM": "/catalogue/uoms/{name}",
	"UAE VAT 201 Filing Log": "/vat-201/{name}",
	"UAE CT Filing Log": "/ct-filings/{name}",
	"UAE ESR Filing": "/esr/{name}",
	"UAE UBO Register": "/ubo/{name}",
	"UAE Late Filing Notice": "/late-filings/{name}",
	"Bank Account": "/bank-accounts/{name}",
	"Mode of Payment": "/modes-of-payment/{name}",
	"Payment Terms Template": "/payment-terms-templates/{name}",
	"Price List": "/price-lists/{name}",
	"Serial No": "/serial-nos/{name}",
	"Batch": "/batches/{name}",
	"Landed Cost Voucher": "/landed-cost-vouchers/{name}",
	"Pricing Rule": "/pricing-rules/{name}",
	"Customer Group": "/customer-groups/{name}",
	"Supplier Group": "/supplier-groups/{name}",
	"Territory": "/territories/{name}",
	"Tax Category": "/tax-categories/{name}",
	"Item Tax Template": "/item-tax-templates/{name}",
	"Address": "/addresses/{name}",
	"Contact": "/contacts/{name}",
	"Fiscal Year": "/fiscal-years/{name}",
	"Terms and Conditions": "/terms-and-conditions/{name}",
	"Supplier Quotation": "/supplier-quotations/{name}",
	"Lead": "/leads/{name}",
	"UAE Related Party": "/uae-related-parties/{name}",
	"UAE VAT Group": "/uae-vat-groups/{name}",
	"UAE Bad Debt Relief": "/uae-bad-debt-relief/{name}",
	"UAE Customs Declaration": "/uae-customs-declarations/{name}",
	"UAE Capital Goods Adjustment": "/uae-capital-goods-adjustments/{name}",
	"BOM": "/boms/{name}",
	"Work Order": "/work-orders/{name}",
	"Pick List": "/pick-lists/{name}",
	"POS Invoice": "/pos-invoices/{name}",
	"POS Profile": "/pos-profiles/{name}",
	"Loyalty Program": "/loyalty-programs/{name}",
	"Loyalty Point Entry": "/loyalty-point-entries/{name}",
	"Currency Exchange": "/currency-exchanges/{name}/edit",
	"Asset Category": "/asset-categories/{name}/edit",
	"Asset": "/assets/{name}",
}


def doc_route(doctype: str | None, name: str | None) -> str | None:
	if not doctype or not name:
		return None
	template = SPA_DOC_ROUTES.get(doctype)
	if not template:
		return None
	return template.format(name=quote(name, safe=""))
