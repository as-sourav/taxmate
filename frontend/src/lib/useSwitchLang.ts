/**
 * Switch en/ar only after Frappe has stored User.language.
 *
 * Screen chrome reads strings.ts immediately. Report columns, month labels,
 * and account names are translated by `_()` on the server, so the SWR cache
 * from the previous language has to be dropped before the tree re-renders.
 * Otherwise the Profit and Loss grid keeps the English payload.
 */
import { useCallback } from "react";
import { useSWRConfig } from "swr";

import { useLang, type Lang } from "./i18n";
import { persistLang } from "./uiPrefs";

export function useSwitchLang(): { lang: Lang; toggle: () => Promise<void> } {
  const { lang, set } = useLang();
  const { cache } = useSWRConfig();

  const toggle = useCallback(async () => {
    const next: Lang = lang === "ar" ? "en" : "ar";
    const saved = await persistLang(next);
    if (!saved) return;
    for (const key of [...cache.keys()]) cache.delete(key);
    set(next);
  }, [cache, lang, set]);

  return { lang, toggle };
}
