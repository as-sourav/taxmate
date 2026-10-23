import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappeAuth } from "frappe-react-sdk";

import { useSession } from "../lib/session";
import { canManageCompany, canOpenDesk, isAppProvider, spaRoleOf } from "../lib/roles";
import { t } from "../i18n/strings";
import { useSwitchLang } from "../lib/useSwitchLang";
import { appearance } from "../lib/theme";
import { persistThemeToggle } from "../lib/uiPrefs";
import { isNative, signalMobile } from "../mobile/platform";

export default function UserMenu() {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const session = useSession();
  const { currentUser, logout } = useFrappeAuth();
  const { lang, toggle: switchLang } = useSwitchLang();
  const [mode, setMode] = useState(appearance);

  useEffect(() => {
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setMode(appearance());
    mq.addEventListener("change", sync);
    window.addEventListener("taxmate-theme", sync);
    return () => {
      mq.removeEventListener("change", sync);
      window.removeEventListener("taxmate-theme", sync);
    };
  }, []);

  const provider = isAppProvider(session);
  const roleLabel = provider ? t("role.provider") : t(`role.${spaRoleOf(session)}`);
  const canSettings = canManageCompany(session);
  const showDesk = canOpenDesk(session) && !isNative();
  const displayName = session.full_name || currentUser || "—";

  const initials = displayName
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");

  // Close on outside click / escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function onPointer(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    const items = menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)");
    items?.[0]?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open]);

  function onMenuKey(event: React.KeyboardEvent<HTMLDivElement>) {
    const items = [...(menuRef.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)") ?? [])];
    if (items.length === 0) return;
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      btnRef.current?.focus();
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    const next =
      event.key === "ArrowDown" ? (index + 1) % items.length
      : event.key === "ArrowUp" ? (index - 1 + items.length) % items.length
      : event.key === "Home" ? 0
      : event.key === "End" ? items.length - 1
      : -1;
    if (next < 0) return;
    event.preventDefault();
    items[next]?.focus();
  }

  async function signOut() {
    if (signingOut) return;
    setSigningOut(true);
    setOpen(false);
    if (isNative()) return signalMobile("logout"); // native: revoke device token, back to sign-in
    try {
      await logout();
    } finally {
      window.location.assign("/login?redirect-to=/taxmate");
    }
  }

  function go(path: string) {
    setOpen(false);
    nav(path);
  }

  function openDesk() {
    setOpen(false);
    // Full navigation — admin console is outside the SPA; gate allows Administrator only.
    window.location.assign("/app");
  }

  return (
    <div className="umwrap" ref={wrapRef}>
      <button
        ref={btnRef}
        type="button"
        className="umavbtn"
        aria-label={`${t("a11y.account")}, ${displayName}`}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls="account-menu"
        onClick={() => setOpen((o) => !o)}
      >
        {initials}
      </button>

      {open && (
        <div id="account-menu" className="umdrop" role="menu" onKeyDown={onMenuKey} ref={menuRef}>
          <div className="umdrop-header" role="presentation">
            <span className="umdrop-name">{displayName}</span>
            <span className="umdrop-role">{roleLabel}</span>
          </div>

          {canSettings && (
            <button
              type="button"
              role="menuitem"
              className="umdrop-item"
              onClick={() => go("/company")}
            >
              <span className="umdrop-ic">
                <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <circle cx="9" cy="9" r="2.5" />
                  <path d="M9 1.5v1.5M9 15v1.5M1.5 9H3M15 9h1.5M4.1 4.1l1.1 1.1M12.8 12.8l1.1 1.1M4.1 13.9l1.1-1.1M12.8 5.2l1.1-1.1" />
                </svg>
              </span>
              {t("user.companySettings")}
            </button>
          )}

          <button
            type="button"
            role="menuitem"
            className="umdrop-item"
            onClick={() => go("/profile")}
          >
            <span className="umdrop-ic">
              <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6">
                <circle cx="9" cy="6.5" r="3" />
                <path d="M2.5 16c0-3.6 2.9-5 6.5-5s6.5 1.4 6.5 5" />
              </svg>
            </span>
            {t("user.editProfile")}
          </button>

          {showDesk && (
            <button
              type="button"
              role="menuitem"
              className="umdrop-item"
              onClick={openDesk}
            >
              <span className="umdrop-ic">
                <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <rect x="2.5" y="2.5" width="5" height="5" rx="1" />
                  <rect x="10.5" y="2.5" width="5" height="5" rx="1" />
                  <rect x="2.5" y="10.5" width="5" height="5" rx="1" />
                  <rect x="10.5" y="10.5" width="5" height="5" rx="1" />
                </svg>
              </span>
              {t("user.openDesk")}
            </button>
          )}

          <div className="umdrop-sep" role="separator" />

          <button
            type="button"
            role="menuitem"
            className="umdrop-item"
            lang={lang === "en" ? "ar" : "en"}
            onClick={() => {
              void switchLang();
            }}
          >
            <span className="umdrop-ic">
              <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                <circle cx="9" cy="9" r="6.2" />
                <path d="M3 9h12M9 2.8c1.6 1.8 2.4 4 2.4 6.2s-.8 4.4-2.4 6.2c-1.6-1.8-2.4-4-2.4-6.2s.8-4.4 2.4-6.2z" />
              </svg>
            </span>
            {lang === "en" ? "عربي" : "English"}
          </button>

          <button
            type="button"
            role="menuitem"
            className="umdrop-item"
            onClick={() => {
              void persistThemeToggle().then(() => setMode(appearance()));
            }}
          >
            <span className="umdrop-ic">
              {mode === "dark" ? (
                <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <circle cx="9" cy="9" r="3.2" />
                  <path d="M9 1.8v1.6M9 14.6v1.6M16.2 9h-1.6M3.4 9H1.8M14.1 3.9l-1.1 1.1M5 13l-1.1 1.1M14.1 14.1 13 13M5 5 3.9 3.9" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M14.5 11.2A6.2 6.2 0 0 1 6.8 3.5 6.4 6.4 0 1 0 14.5 11.2z" />
                </svg>
              )}
            </span>
            {mode === "dark" ? t("a11y.themeLight") : t("a11y.themeDark")}
          </button>

          <div className="umdrop-sep" role="separator" />

          <button
            type="button"
            role="menuitem"
            className="umdrop-item danger"
            onClick={() => void signOut()}
            disabled={signingOut}
          >
            <span className="umdrop-ic">
              <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path d="M7 3H3.5A1.5 1.5 0 002 4.5v9A1.5 1.5 0 003.5 15H7M11.5 5.5L15 9l-3.5 3.5M15 9H7" />
              </svg>
            </span>
            {signingOut ? "…" : t("user.logOut")}
          </button>
        </div>
      )}
    </div>
  );
}
