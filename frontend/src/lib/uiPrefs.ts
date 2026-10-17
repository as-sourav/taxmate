/**
 * Persist SPA language/theme onto Frappe User (language + desk_theme).
 * SessionProvider applies User → SPA on load; toggles call persist* after local apply.
 *
 * Callers: useSwitchLang, AppShell theme toggle, session applySessionPrefs.
 */
import { apiFetch } from "../mobile/http";
import { isNative, MOBILE_BUILD } from "../mobile/platform";
import { authHeader } from "../mobile/session";
import { METHOD } from "./frappe";
import { getLang, setLang, type Lang } from "./i18n";
import { appearance, getTheme, setTheme, type Theme } from "./theme";

export type UiPrefsPayload = {
  language?: string | null;
  desk_theme?: string | null;
  lang?: Lang | null;
  theme?: Theme | null;
};

function csrf(): string {
  const t = window.csrf_token;
  return t && !t.startsWith("{{") ? t : "";
}

async function postPrefs(body: Record<string, string>): Promise<UiPrefsPayload | null> {
  try {
    const res = await apiFetch(`/api/method/${METHOD.updateUiPreferences}`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(csrf() ? { "X-Frappe-CSRF-Token": csrf() } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    const json = (await res.json()) as { message?: UiPrefsPayload };
    return json.message ?? null;
  } catch {
    return null;
  }
}

/** Apply User prefs onto local SPA state. Returns what changed. */
export function applySessionPrefs(prefs: {
  lang?: string | null;
  theme?: string | null;
}): { lang?: Lang; theme?: Theme } {
  const out: { lang?: Lang; theme?: Theme } = {};
  if (prefs.lang === "en" || prefs.lang === "ar") {
    if (getLang() !== prefs.lang) {
      setLang(prefs.lang);
      out.lang = prefs.lang;
    }
  }
  if (prefs.theme === "light" || prefs.theme === "dark" || prefs.theme === "system") {
    if (getTheme() !== prefs.theme) {
      setTheme(prefs.theme);
      out.theme = prefs.theme;
    }
  }
  return out;
}

/**
 * Save User.language first. Local strings flip only after Frappe accepts it.
 * Before sign-in the phone has no device token, so chrome switches locally only.
 */
export async function persistLang(lang: Lang): Promise<boolean> {
  if (MOBILE_BUILD && isNative() && !authHeader()) {
    setLang(lang);
    return true;
  }
  const saved = await postPrefs({ language: lang });
  if (!saved) return false;
  setLang(lang);
  return true;
}

export async function persistTheme(theme: Theme): Promise<void> {
  setTheme(theme);
  await postPrefs({ theme });
}

export async function persistThemeToggle(): Promise<"light" | "dark"> {
  const next = appearance() === "dark" ? "light" : "dark";
  await persistTheme(next);
  return next;
}
