import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { useLang } from "../lib/i18n";
import { useSession } from "../lib/session";
import { canOpenPosNext, canViewTeam } from "../lib/roles";
import { buildNav, groupedNav, groupForPath, FeatureFlags, type NavLinkItem } from "../lib/nav";
import { t } from "../i18n/strings";
import GlobalSearch from "./GlobalSearch";
import Notifications from "./Notifications";
import UserMenu from "./UserMenu";
import CompanySwitcher from "./CompanySwitcher";
import MobileNav, { useIsMobileShell } from "./MobileNav";
import "../styles/phone-fixes.css";
import { navIcon, sectionIcon } from "./navIcons";
import { CaptureDesk } from "../screens/dashboard/CaptureDesk";

const RAIL_KEY = "taxmate-rail";
const OPEN_KEY = "taxmate-nav-open";

type FlyPlace = { key: string; top: number; maxHeight: number; edge: number; rtl: boolean };

function placeFly(el: HTMLElement, key: string): FlyPlace {
  const rect = el.getBoundingClientRect();
  const rtl = document.documentElement.dir === "rtl";
  const desired = 360;
  let top = rect.top;
  let maxHeight = window.innerHeight - top - 12;
  if (maxHeight < Math.min(desired, 220)) {
    top = Math.max(8, window.innerHeight - 12 - desired);
    maxHeight = window.innerHeight - top - 12;
  }
  return {
    key,
    top,
    maxHeight,
    edge: rtl ? window.innerWidth - rect.left + 10 : rect.right + 10,
    rtl,
  };
}

function RailLink({ n, tip }: { n: NavLinkItem; tip: boolean }) {
  const label = t(n.key);
  const body = (
    <>
      <span className="ic">{navIcon("href" in n ? n.href : n.to)}</span>
      <span>{label}</span>
    </>
  );
  if ("href" in n) {
    return (
      <a href={n.href} data-tip={tip ? label : undefined} className="rlink">
        {body}
      </a>
    );
  }
  return (
    <NavLink
      to={n.to}
      end={n.to === "/"}
      data-tip={tip ? label : undefined}
      className={({ isActive }) => `rlink${isActive ? " on" : ""}`}
    >
      {body}
    </NavLink>
  );
}

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
  const [fly, setFly] = useState<FlyPlace | null>(null);
  const closeFly = useRef<number | null>(null);

  function holdFly() {
    if (closeFly.current) window.clearTimeout(closeFly.current);
    closeFly.current = null;
  }
  function queueFlyClose() {
    holdFly();
    closeFly.current = window.setTimeout(() => setFly(null), 140);
  }
  function openFly(key: string, el: HTMLElement) {
    if (!collapsed) return;
    holdFly();
    setFly(placeFly(el, key));
  }

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

  useEffect(() => {
    setFly(null);
  }, [location.pathname, collapsed]);

  useEffect(() => {
    if (!fly) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFly(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fly]);

  return (
    <div className={`app${collapsed && !mobile ? " collapsed" : ""}${mobile ? " has-mnav" : ""}`}>
      <a className="skip" href="#taxmate-main">{t("a11y.skip")}</a>
      {!mobile && (
      <nav className="rail">
        <div className="rbrand">
          <span className="mark">T</span>
          <span>TaxMate</span>
        </div>
        <div className="rail-body" onScroll={collapsed ? () => setFly(null) : undefined}>
        {top.map((n) => (
          <RailLink key={"href" in n ? n.href : n.to} n={n} tip={collapsed} />
        ))}

        {groups.map((g) => {
          const expanded = !collapsed && !!open[g.key];
          const flying = collapsed && fly?.key === g.key;
          return (
            <div
              className="rgroup"
              key={g.key}
              onMouseLeave={collapsed ? queueFlyClose : undefined}
              onBlur={collapsed ? (e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) queueFlyClose();
              } : undefined}
            >
              {collapsed ? (
                <button
                  type="button"
                  className={`rsec ricon${activeGroup === g.key ? " on" : ""}`}
                  aria-expanded={flying}
                  aria-haspopup="true"
                  aria-label={t(g.key)}
                  onMouseEnter={(e) => { holdFly(); openFly(g.key, e.currentTarget); }}
                  onFocus={(e) => openFly(g.key, e.currentTarget)}
                >
                  <span className="ic">{sectionIcon(g.key)}</span>
                </button>
              ) : (
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
              )}
              {expanded && g.links.map((n) => (
                <RailLink key={"href" in n ? n.href : n.to} n={n} tip={false} />
              ))}
              {flying && fly && (
                <div
                  className="rfly"
                  role="navigation"
                  aria-label={t(g.key)}
                  style={{
                    top: fly.top,
                    maxHeight: fly.maxHeight,
                    ...(fly.rtl ? { right: fly.edge } : { left: fly.edge }),
                  }}
                  onMouseEnter={holdFly}
                >
                  <div className="rfly-title">{t(g.key)}</div>
                  {g.links.map((n) => (
                    <RailLink key={"href" in n ? n.href : n.to} n={n} tip={false} />
                  ))}
                </div>
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
