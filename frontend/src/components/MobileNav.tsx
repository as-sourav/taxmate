/**
 * Phone navigation: a fixed bottom tab bar plus a "More" sheet of secondary
 * destinations (tabs: Home / Sales / Money; More uses MOBILE_MORE_KEEP in nav.ts).
 *
 * Why this exists: below 900px the rail used to become a horizontal scrolling
 * strip with its section headers hidden, which made Purchase, Stock,
 * Accounting, Masters and Compliance unreachable on a phone. Below 900px the
 * rail is now not rendered at all and this takes its place.
 *
 * The breakpoint is evaluated in JS (matchMedia), not only in CSS, so the rail
 * and the tab bar are never both in the DOM. Callers: AppShell.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { t } from "../i18n/strings";
import { useLang } from "../lib/i18n";
import {
  filterNavForMobileMore,
  mobileTabForPath,
  type MobileTabId,
  type NavGroup,
  type NavLinkItem,
} from "../lib/nav";
import { useMedia } from "../lib/useMedia";
import { navIcon } from "./navIcons";

import "../styles/shell-mobile.css";

export const MOBILE_SHELL_QUERY = "(max-width: 900px)";

/** True on phone/narrow layouts, where the rail is replaced by the tab bar. */
export function useIsMobileShell(): boolean {
  return useMedia(MOBILE_SHELL_QUERY);
}

const TABS: { id: MobileTabId; to: string; key: string }[] = [
  { id: "home", to: "/", key: "m.tab.home" },
  { id: "sales", to: "/invoices", key: "m.tab.sales" },
  { id: "money", to: "/payments", key: "m.tab.money" },
];

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function MoreIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 7h16M4 12h16M4 17h10" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

type Section = { key: string | null; links: NavLinkItem[] };

export default function MobileNav({ top, groups }: { top: NavLinkItem[]; groups: NavGroup[] }) {
  const location = useLocation();
  const { lang } = useLang();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const moreRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // While the sheet is open no route tab is lit — "More" owns the active state.
  const activeTab = open ? null : mobileTabForPath(location.pathname);

  const close = useCallback((restoreFocus = true) => {
    setOpen(false);
    setQuery("");
    if (restoreFocus) {
      // After the sheet unmounts, or the focus lands on a node being removed.
      requestAnimationFrame(() => moreRef.current?.focus());
    }
  }, []);

  // Route change closes the sheet — including the navigation a sheet link causes.
  useEffect(() => {
    setOpen(false);
    setQuery("");
  }, [location.pathname]);

  // Escape anywhere, and focus into the filter when the sheet opens.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, close]);

  const sections = useMemo<Section[]>(() => {
    // Presentation-only: rail still gets the full AppShell nav.
    const phone = filterNavForMobileMore(top, groups);
    const all: Section[] = [];
    if (phone.top.length) all.push({ key: null, links: phone.top });
    for (const g of phone.groups) all.push({ key: g.key, links: g.links });

    const q = query.trim().toLowerCase();
    if (!q) return all;

    return all
      .map((s) => {
        // A section whose own label matches keeps all of its links.
        const sectionHit = s.key ? t(s.key).toLowerCase().includes(q) : false;
        const links = sectionHit ? s.links : s.links.filter((l) => t(l.key).toLowerCase().includes(q));
        return { key: s.key, links };
      })
      .filter((s) => s.links.length > 0);
    // `t` reads the module-level locale, so a language switch must recompute.
  }, [top, groups, query, lang]);

  // Simple focus trap: Tab wraps within the sheet while it is open.
  function onSheetKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (e.key !== "Tab") return;
    const root = sheetRef.current;
    if (!root) return;
    const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    );
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    const current = document.activeElement as HTMLElement | null;
    const inside = !!current && root.contains(current);
    if (e.shiftKey) {
      if (!inside || current === first) {
        e.preventDefault();
        last.focus();
      }
      return;
    }
    if (!inside || current === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function renderLink(item: NavLinkItem) {
    const label = t(item.key);
    if (item.external) {
      return (
        <a key={item.href} href={item.href} className="msheet-link" onClick={() => close(false)}>
          <span className="ic">{navIcon(item.href)}</span>
          <span className="msheet-ltext">{label}</span>
        </a>
      );
    }
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.to === "/"}
        className={({ isActive }) => `msheet-link${isActive ? " on" : ""}`}
        onClick={() => close(false)}
      >
        <span className="ic">{navIcon(item.to)}</span>
        <span className="msheet-ltext">{label}</span>
      </NavLink>
    );
  }

  return (
    <>
      <nav className="mnav" aria-label={t("m.menu")} data-testid="mobile-tabs">
        {TABS.map((tab) => (
          <Link
            key={tab.id}
            to={tab.to}
            data-tab={tab.id}
            className={`mnav-tab${activeTab === tab.id ? " on" : ""}`}
            aria-current={activeTab === tab.id ? "page" : undefined}
          >
            <span className="mnav-ic">{navIcon(tab.to)}</span>
            <span className="mnav-label">{t(tab.key)}</span>
          </Link>
        ))}
        <button
          type="button"
          ref={moreRef}
          data-tab="more"
          className={`mnav-tab${open ? " on" : ""}`}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => (open ? close() : (setQuery(""), setOpen(true)))}
        >
          <span className="mnav-ic">
            <MoreIcon />
          </span>
          <span className="mnav-label">{t("m.tab.more")}</span>
        </button>
      </nav>

      {open && (
        <>
          <button
            type="button"
            className="msheet-scrim"
            aria-label={t("m.close")}
            tabIndex={-1}
            onClick={() => close()}
          />
          <div
            className="msheet"
            role="dialog"
            aria-modal="true"
            aria-label={t("m.more.title")}
            ref={sheetRef}
            onKeyDown={onSheetKeyDown}
          >
            <div className="msheet-head">
              <div className="msheet-grip" aria-hidden="true" />
              <div className="msheet-hrow">
                <h2 className="msheet-title">{t("m.more.title")}</h2>
                <button type="button" className="msheet-close" aria-label={t("m.close")} onClick={() => close()}>
                  <CloseIcon />
                </button>
              </div>
              <input
                ref={inputRef}
                className="msheet-search"
                type="search"
                value={query}
                placeholder={t("m.more.search")}
                aria-label={t("m.more.search")}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>

            <div className="msheet-body">
              {sections.length === 0 ? (
                <p className="msheet-none">{t("m.more.none")}</p>
              ) : (
                sections.map((s) => (
                  <div key={s.key ?? "__top"} className="msheet-group">
                    {s.key && <div className="msheet-sec">{t(s.key)}</div>}
                    <div className="msheet-grid">{s.links.map((l) => renderLink(l))}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
