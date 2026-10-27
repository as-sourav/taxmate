/** Desk print view. The server checks print permission; the SPA does not add an endpoint.
 * Callers: quotation, sales order, delivery note, invoice, and payment detail screens.
 * API: none. Opens /printview. `_lang` is Frappe's print language (form_dict._lang).
 */

import { getLang, type Lang } from "./i18n";

export function printDocUrl(doctype: string, name: string, format?: string, lang?: Lang): string {
  const p = new URLSearchParams({
    doctype,
    name,
    trigger_print: "1",
    no_letterhead: "0",
    _lang: lang ?? getLang(),
  });
  if (format) p.set("format", format);
  return `/printview?${p.toString()}`;
}
