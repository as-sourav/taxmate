/**
 * List, detail, and draft fields for the eight Desk documents that had no SPA screen.
 * Callers: RegisterList, RegisterDetail, RegisterForm, App.tsx routes.
 * API: taxmate.api.resource.get_list / get / insert / save, plus taxmate.api.linked_docs.
 * User: build Opportunity, Request for Quotation, Shipment, Installation Note,
 * Delivery Trip, Payment Request, and the two subcontracting documents.
 */

export type FieldKind = "text" | "date" | "datetime" | "number" | "select" | "link";

export type FieldSpec = {
  key: string;
  label: string;
  kind: FieldKind;
  link?: string;
  options?: string[];
  required?: boolean;
  readOnly?: boolean;
};

export type RegisterSpec = {
  doctype: string;
  titleKey: string;
  path: string;
  searchField: string;
  listFields: string[];
  columns: { key: string; label: string; field: string; date?: boolean; money?: boolean }[];
  facts: { key: string; label: string; field: string; date?: boolean; money?: boolean }[];
  fields: FieldSpec[];
  linesKey?: string;
  editLines?: boolean;
  suppliers?: boolean;
  submittable: boolean;
  /** True when Desk lets you start a blank document. The others open from a source document. */
  standalone: boolean;
  empty: string;
};

export const REGISTERS: Record<string, RegisterSpec> = {
  opportunity: {
    doctype: "Opportunity",
    titleKey: "Opportunities",
    path: "/opportunities",
    searchField: "party_name",
    listFields: ["name", "party_name", "status", "opportunity_type", "company", "transaction_date"],
    columns: [
      { key: "party", label: "Party", field: "party_name" },
      { key: "type", label: "Type", field: "opportunity_type" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "party", label: "Party", field: "party_name" },
      { key: "from", label: "From", field: "opportunity_from" },
      { key: "type", label: "Type", field: "opportunity_type" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "opportunity_from", label: "Opportunity From", kind: "select", options: ["Lead", "Customer"], required: true },
      { key: "party_name", label: "Party", kind: "link", required: true },
      { key: "opportunity_type", label: "Type", kind: "text" },
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
      { key: "transaction_date", label: "Date", kind: "date", required: true },
      { key: "status", label: "Status", kind: "select", options: ["Open", "Replied", "Quotation", "Converted", "Lost", "Closed"], required: true },
    ],
    linesKey: "items",
    editLines: true,
    submittable: false,
    standalone: true,
    empty: "No opportunities.",
  },
  rfq: {
    doctype: "Request for Quotation",
    titleKey: "Requests for Quotation",
    path: "/request-for-quotations",
    searchField: "name",
    listFields: ["name", "transaction_date", "status", "company"],
    columns: [
      { key: "name", label: "Name", field: "name" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
      { key: "transaction_date", label: "Date", kind: "date", required: true },
    ],
    linesKey: "items",
    editLines: true,
    suppliers: true,
    submittable: true,
    standalone: true,
    empty: "No requests for quotation.",
  },
  shipment: {
    doctype: "Shipment",
    titleKey: "Shipments",
    path: "/shipments",
    searchField: "name",
    listFields: ["name", "status", "pickup_date", "tracking_status"],
    columns: [
      { key: "name", label: "Name", field: "name" },
      { key: "date", label: "Pickup", field: "pickup_date", date: true },
      { key: "tracking", label: "Tracking", field: "tracking_status" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "pickup", label: "Pickup date", field: "pickup_date", date: true },
      { key: "from", label: "Pickup address", field: "pickup_address_name" },
      { key: "to", label: "Delivery address", field: "delivery_address_name" },
      { key: "value", label: "Value of goods", field: "value_of_goods", money: true },
      { key: "tracking", label: "Tracking", field: "tracking_status" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "pickup_address_name", label: "Pickup address", kind: "link", link: "Address", required: true },
      { key: "delivery_address_name", label: "Delivery address", kind: "link", link: "Address", required: true },
      { key: "pickup_date", label: "Pickup date", kind: "date", required: true },
      { key: "value_of_goods", label: "Value of goods", kind: "number", required: true },
      { key: "description_of_content", label: "Description of content", kind: "text", required: true },
    ],
    linesKey: "shipment_delivery_note",
    submittable: true,
    standalone: false,
    empty: "No shipments.",
  },
  installation: {
    doctype: "Installation Note",
    titleKey: "Installation Notes",
    path: "/installation-notes",
    searchField: "customer",
    listFields: ["name", "customer", "inst_date", "status", "company"],
    columns: [
      { key: "customer", label: "Customer", field: "customer" },
      { key: "date", label: "Date", field: "inst_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "customer", label: "Customer", field: "customer" },
      { key: "date", label: "Installation date", field: "inst_date", date: true },
      { key: "territory", label: "Territory", field: "territory" },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "customer", label: "Customer", kind: "link", link: "Customer", required: true },
      { key: "inst_date", label: "Installation date", kind: "date", required: true },
      { key: "territory", label: "Territory", kind: "link", link: "Territory", required: true },
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
    ],
    linesKey: "items",
    submittable: true,
    standalone: false,
    empty: "No installation notes.",
  },
  trip: {
    doctype: "Delivery Trip",
    titleKey: "Delivery Trips",
    path: "/delivery-trips",
    searchField: "name",
    listFields: ["name", "driver", "status", "departure_time", "company"],
    columns: [
      { key: "name", label: "Name", field: "name" },
      { key: "driver", label: "Driver", field: "driver" },
      { key: "when", label: "Departure", field: "departure_time" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "driver", label: "Driver", field: "driver" },
      { key: "vehicle", label: "Vehicle", field: "vehicle" },
      { key: "when", label: "Departure", field: "departure_time" },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
      { key: "driver", label: "Driver", kind: "link", link: "Driver" },
      { key: "vehicle", label: "Vehicle", kind: "link", link: "Vehicle", required: true },
      { key: "departure_time", label: "Departure", kind: "datetime", required: true },
    ],
    linesKey: "delivery_stops",
    submittable: true,
    standalone: false,
    empty: "No delivery trips.",
  },
  paymentRequest: {
    doctype: "Payment Request",
    titleKey: "Payment Requests",
    path: "/payment-requests",
    searchField: "party",
    listFields: ["name", "party", "status", "grand_total", "transaction_date", "reference_name"],
    columns: [
      { key: "party", label: "Party", field: "party" },
      { key: "ref", label: "Reference", field: "reference_name" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "amount", label: "Amount", field: "grand_total", money: true },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "party", label: "Party", field: "party" },
      { key: "type", label: "Type", field: "payment_request_type" },
      { key: "ref", label: "Reference", field: "reference_name" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "amount", label: "Amount", field: "grand_total", money: true },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "party", label: "Party", kind: "text", readOnly: true },
      { key: "grand_total", label: "Amount", kind: "number", readOnly: true },
      { key: "transaction_date", label: "Date", kind: "date" },
      { key: "email_to", label: "Email", kind: "text" },
    ],
    submittable: true,
    standalone: false,
    empty: "No payment requests.",
  },
  subcontractingOrder: {
    doctype: "Subcontracting Order",
    titleKey: "Subcontracting Orders",
    path: "/subcontracting-orders",
    searchField: "supplier",
    listFields: ["name", "supplier", "status", "transaction_date", "company"],
    columns: [
      { key: "supplier", label: "Job worker", field: "supplier" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "supplier", label: "Job worker", field: "supplier" },
      { key: "po", label: "Purchase order", field: "purchase_order" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "warehouse", label: "Job worker warehouse", field: "supplier_warehouse" },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "supplier", label: "Job worker", kind: "link", link: "Supplier", readOnly: true },
      { key: "purchase_order", label: "Purchase order", kind: "text", readOnly: true },
      { key: "supplier_warehouse", label: "Job worker warehouse", kind: "link", link: "Warehouse", required: true },
      { key: "transaction_date", label: "Date", kind: "date", required: true },
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
    ],
    linesKey: "items",
    submittable: true,
    standalone: false,
    empty: "No subcontracting orders.",
  },
  subcontractingInward: {
    doctype: "Subcontracting Inward Order",
    titleKey: "Subcontracting Inward Orders",
    path: "/subcontracting-inward-orders",
    searchField: "customer",
    listFields: ["name", "customer", "status", "transaction_date", "company"],
    columns: [
      { key: "customer", label: "Customer", field: "customer" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    facts: [
      { key: "customer", label: "Customer", field: "customer" },
      { key: "so", label: "Sales order", field: "sales_order" },
      { key: "date", label: "Date", field: "transaction_date", date: true },
      { key: "company", label: "Company", field: "company" },
      { key: "status", label: "Status", field: "status" },
    ],
    fields: [
      { key: "customer", label: "Customer", kind: "link", link: "Customer", readOnly: true },
      { key: "sales_order", label: "Sales order", kind: "text", readOnly: true },
      { key: "transaction_date", label: "Date", kind: "date", required: true },
      { key: "company", label: "Company", kind: "link", link: "Company", required: true },
    ],
    linesKey: "items",
    submittable: true,
    standalone: false,
    empty: "No subcontracting inward orders.",
  },
};
