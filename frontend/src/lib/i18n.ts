/**
 * Locale + direction. Arabic is a v1 constraint, so `dir` is set on <html>
 * and every layout rule is logical-first.
 *
 * Strings live in flat dictionaries keyed identically, so a missing Arabic
 * key silently falls back to English rather than rendering blank.
 *
 * Language lives in React context so switching en/ar re-renders the tree
 * (rail, search, and the active screen), not only AppShell.
 */
import { createContext, createElement, useContext, useMemo, useState, type ReactNode } from "react";

export type Lang = "en" | "ar";

const STORE_KEY = "taxmate-lang";
let current: Lang = "en";

try {
  const saved = localStorage.getItem(STORE_KEY);
  if (saved === "ar" || saved === "en") current = saved;
} catch {
  /* private window or blocked storage — English it is */
}

export function getLang(): Lang {
  return current;
}

export function getLocale(): string {
  return current === "ar" ? "ar-AE" : "en-GB";
}

export function setLang(lang: Lang): void {
  current = lang;
  try {
    localStorage.setItem(STORE_KEY, lang);
  } catch {
    /* ignore */
  }
  applyDir();
}

export function applyDir(): void {
  const root = document.documentElement;
  root.setAttribute("dir", current === "ar" ? "rtl" : "ltr");
  root.setAttribute("lang", current);
}

type LangCtx = { lang: Lang; set: (lang: Lang) => void };

const LangContext = createContext<LangCtx>({ lang: "en", set: () => {} });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => getLang());
  const value = useMemo<LangCtx>(
    () => ({
      lang,
      set: (next: Lang) => {
        setLang(next);
        setLangState(next);
      },
    }),
    [lang],
  );
  return createElement(LangContext.Provider, { value }, children);
}

export function useLang(): LangCtx {
  return useContext(LangContext);
}

type Dict = Record<string, string>;

/** Sales Invoice book. The section is Sales; the link still names the document. */
const SALES_INVOICE_LABEL = { en: "Sales Invoices", ar: "فواتير المبيعات" };

export function makeT(en: Dict, ar: Dict) {
  return (key: string): string => {
    if (key === "nav.invoices" || key === "inv.title") {
      return current === "ar" ? SALES_INVOICE_LABEL.ar : SALES_INVOICE_LABEL.en;
    }
    return current === "ar" ? (ar[key] ?? en[key] ?? key) : (en[key] ?? key);
  };
}

/** Pick the localised field off a record, e.g. customer_name vs its Arabic twin. */
export function pick<T>(enVal: T, arVal?: T): T {
  return current === "ar" && arVal != null ? arVal : enVal;
}
