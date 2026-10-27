/** Print this TaxMate format. An Arabic screen also offers an English copy. */
import { useLang } from "../lib/i18n";
import { printDocUrl } from "../lib/printDoc";
import { t } from "../i18n/strings";
import { isNative } from "../mobile/platform";

export function PrintLangButtons({
  doctype,
  name,
  format,
}: {
  doctype: string;
  name: string;
  format: string;
}) {
  const { lang } = useLang();
  if (isNative() || !name) return null;
  const open = (printLang: "en" | "ar") =>
    window.open(printDocUrl(doctype, name, format, printLang), "_blank", "noopener");
  if (lang !== "ar") {
    return (
      <button type="button" className="btn ghost" onClick={() => open("en")}>
        {t("inv.print")}
      </button>
    );
  }
  return (
    <>
      <button type="button" className="btn ghost" onClick={() => open("ar")}>
        {t("inv.print")}
      </button>
      <button type="button" className="btn ghost" onClick={() => open("en")}>
        English
      </button>
    </>
  );
}
