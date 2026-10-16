import { createContext, useContext, useEffect, useRef } from "react";
import { useFrappeGetCall } from "frappe-react-sdk";

import { METHOD } from "./frappe";
import { useLang } from "./i18n";
import { setSiteToday } from "./status";
import { applySessionPrefs } from "./uiPrefs";

export type Session = {
  user: string;
  full_name?: string;
  company?: string | null;
  currency?: string | null;
  country?: string | null;
  roles?: string[];
  spa_role?: "owner" | "accountant" | "clerk" | "viewer" | null;
  spa_roles?: Array<"owner" | "accountant" | "clerk" | "viewer">;
  is_app_provider?: boolean;
  extra_roles?: string[];
  /** The SITE's date, so anything date-driven agrees with the server. */
  today?: string;
  time_zone?: string;
  /** User.language (Language Link). */
  language?: string | null;
  /** User.desk_theme: Light | Dark | Automatic. */
  desk_theme?: string | null;
  /** SPA: en | ar when User.language maps cleanly. */
  lang?: "en" | "ar" | null;
  /** SPA: light | dark | system when desk_theme is set. */
  theme?: "light" | "dark" | "system" | null;
};

const SessionContext = createContext<Session>({ user: "", roles: [] });

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { data } = useFrappeGetCall<{ message: Session }>(METHOD.getSession);
  const session = data?.message ?? { user: "", roles: [] };
  const { set: setLocale } = useLang();
  const appliedFor = useRef<string>("");

  useEffect(() => {
    setSiteToday(session.today);
  }, [session.today]);

  // Once per login: User.language / desk_theme win over device localStorage.
  useEffect(() => {
    if (!session.user) return;
    const key = `${session.user}|${session.lang ?? ""}|${session.theme ?? ""}`;
    if (appliedFor.current === key) return;
    appliedFor.current = key;
    const changed = applySessionPrefs({ lang: session.lang, theme: session.theme });
    if (changed.lang) setLocale(changed.lang);
    if (changed.theme) window.dispatchEvent(new Event("taxmate-theme"));
  }, [session.user, session.lang, session.theme, setLocale]);

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  return useContext(SessionContext);
}
