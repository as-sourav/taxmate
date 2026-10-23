import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";
import { canOpenPosNext, canViewTeam } from "../lib/roles";
import { buildNav, groupedNav, groupForPath, FeatureFlags } from "../lib/nav";
import { t } from "../i18n/strings";
import GlobalSearch from "./GlobalSearch";
import Notifications from "./Notifications";
import UserMenu from "./UserMenu";
import CompanySwitcher from "./CompanySwitcher";
import MobileNav, { useIsMobileShell } from "./MobileNav";
import "../styles/phone-fixes.css";
import { navIcon } from "./navIcons";
import { CaptureDesk } from "../screens/dashboard/CaptureDesk";

const RAIL_KEY = "taxmate-rail";
const OPEN_KEY = "taxmate-nav-open";

function loadOpen(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(OPEN_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed as Record<string, boolean>;
  } catch {
    return {};
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(RAIL_KEY) === "1"; } catch { return false; }
  });
  function toggleCollapsed() {
    setCollapsed((c) => {
      if (!c) setOpen({});
      return !c;
    });
  }
  const { lang } = useLang();
  /**
   * Below 900px the rail is replaced by MobileNav's bottom tab bar. Decided in
   * JS rather than CSS so only one of the two is ever in the DOM — a hidden
   * rail full of links is still a tab stop and still read by screen readers.
   */
  const mobile = useIsMobileShell();
  const [open, setOpen] = useState(loadOpen);
  const location = useLocation();
  const session = useSession();
  const { data: flagData } = useFrappeGetCall<{ message: FeatureFlags }>(
    "taxmate.api.settings.get_feature_flags",
    {},
    "feature-flags",
    { revalidateOnFocus: false }
  );
  const flags: FeatureFlags = flagData?.message ?? {};
  const baseNav = buildNav(flags).filter((n) => {
    if (n.key === "nav.posNext") return canOpenPosNext(session);
    return true;
  });
  const nav = canViewTeam(session)
    ? baseNav
    : baseNav.filter((n) => {
      if (n.type === "section") return n.key !== "nav.company";
      if (n.type === "external") return true;
      return n.to !== "/team";
    });
  const { top, groups } = useMemo(() => groupedNav(nav), [nav]);
  const activeGroup = groupForPath(groups, location.pathname);

  useEffect(() => {
    try { localStorage.setItem(RAIL_KEY, collapsed ? "1" : "0"); } catch { /* ignore */ }
  }, [collapsed]);

  useEffect(() => {
    if (!activeGroup) return;
    setOpen((prev) => (prev[activeGroup] ? prev : { ...prev, [activeGroup]: true }));
  }, [activeGroup]);

  useEffect(() => {
    try { localStorage.setItem(OPEN_KEY, JSON.stringify(open)); } catch { /* ignore */ }
  }, [open]);

  return (
    <div className={`app${collapsed && !mobile ? " collapsed" : ""}${mobile ? " has-mnav" : ""}`}>
      <a className="skip" href="#taxmate-main">{t("a11y.skip")}</a>
      {!mobile && (
      <nav className="rail">
        <div className="rbrand">
          <span className="mark">T</span>
          <span>TaxMate</span>
        </div>
        <div className="rail-body">
        {top.map((n) =>
          n.external ? (
            <a key={n.href} href={n.href} data-tip={t(n.key)} className="rlink">
              <span className="ic">{navIcon(n.href)}</span>
              <span>{t(n.key)}</span>
            </a>
          ) : (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-tip={t(n.key)}
              className={({ isActive }) => `rlink${isActive ? " on" : ""}`}
            >
              <span className="ic">{navIcon(n.to)}</span>
              <span>{t(n.key)}</span>
            </NavLink>
          )
        )}

        {groups.map((g) => {
          const expanded = !collapsed && !!open[g.key];
          return (
            <div className="rgroup" key={g.key}>
              <button
                type="button"
                className="rsec"
                aria-expanded={expanded}
                onClick={() => setOpen((prev) => ({ ...prev, [g.key]: !prev[g.key] }))}
              >
                <span>{t(g.key)}</span>
                <svg className="chev" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                  <path d="M4 2.5 8.5 6 4 9.5" />
                </svg>
              </button>
              {expanded && g.links.map((n) =>
                n.external ? (
                  <a key={n.href} href={n.href} data-tip={t(n.key)} className="rlink">
                    <span className="ic">{navIcon(n.href)}</span>
                    <span>{t(n.key)}</span>
                  </a>
                ) : (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    data-tip={t(n.key)}
                    className={({ isActive }) => `rlink${isActive ? " on" : ""}`}
                  >
                    <span className="ic">{navIcon(n.to)}</span>
                    <span>{t(n.key)}</span>
                  </NavLink>
                )
              )}
            </div>
          );
        })}

        </div>{/* rail-body */}
      </nav>
      )}

      <div className="main">
        <div className="topbar">
          {!mobile && (
          <button type="button" className="iconbtn" onClick={toggleCollapsed} aria-label={t("a11y.toggleMenu")}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M2.5 4.5h13M2.5 9h13M2.5 13.5h13" />
            </svg>
          </button>
          )}
          {mobile && (
          <div className="mnav-brand">
            <span className="mark" aria-hidden="true">T</span>
            <span>TaxMate</span>
          </div>
          )}

          <CompanySwitcher />

          <GlobalSearch />

          <div className="tright">
            <div className="tools">
              <CaptureDesk />
              <Notifications />
            </div>
            <UserMenu />
          </div>
        </div>

        <div className={`page${mobile ? " mnav-pad" : ""}`} id="taxmate-main" tabIndex={-1} key={lang}>{children}</div>
      </div>

      {mobile && <MobileNav top={top} groups={groups} />}
    </div>
  );
}
