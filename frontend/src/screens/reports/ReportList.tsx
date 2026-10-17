/**
 * Reports list — sections, filter, pins, and live status badges.
 *
 * Catalog: taxmate.api.reports.list_reports
 * Badges:  taxmate.api.report_badges.get_report_badges (optional; rows render without them)
 * Pins:    localStorage only
 */

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { METHOD } from "../../lib/frappe";
import { useSession } from "../../lib/session";
import {
  ICON_PATH,
  REPORT_META,
  SECTION_ORDER,
  metaFor,
  readPinned,
  writePinned,
  type ReportSection,
} from "../../lib/reportCatalog";
import { useLang } from "../../lib/i18n";
import { useIsPhone } from "../../lib/useMedia";
import { t } from "../../i18n/strings";
import { ErrorBox, Loading, PageHead, Card } from "../../components/ui";
import "./reports.css";
/* Callers: App.tsx Route /reports. Edit existing ReportList.tsx. */

type CatalogReport = { label: string; report: string };
type Badge = {
  tone: "ok" | "warn" | "bad";
  key: string;
  count?: number;
  amount?: number;
  days?: number;
  period?: string;
  year?: number | string;
};
type BadgePayload = { company: string | null; today?: string; badges: Record<string, Badge> };

const fill = (s: string, vars: Record<string, string | number>) =>
  Object.entries(vars).reduce((acc, [k, v]) => acc.split(`{${k}}`).join(String(v)), s);

function badgeText(b: Badge): string {
  switch (b.key) {
    case "balanced":
      return t("rpt.b.balanced");
    case "outBy":
      return fill(t("rpt.b.outBy"), { v: Math.abs(b.amount ?? 0).toLocaleString() });
    case "filed":
      return b.period ? fill(t("rpt.b.filedPeriod"), { p: b.period }) : t("rpt.b.filed");
    case "draftDue": {
      const p = b.period ?? "";
      if (b.days == null) return fill(t("rpt.b.draft"), { p });
      if (b.days < 0) return fill(t("rpt.b.draftLate"), { p, n: -b.days });
      return fill(t("rpt.b.draftDays"), { p, n: b.days });
    }
    case "needAction":
      return fill(t("rpt.b.needAction"), { n: b.count ?? 0 });
    case "allSent":
      return t("rpt.b.allSent");
    case "openNotices":
      return fill(t("rpt.b.openNotices"), { n: b.count ?? 0 });
    case "noneOpen":
      return t("rpt.b.noneOpen");
    case "filedYear":
      return fill(t("rpt.b.filedYear"), { y: b.year ?? "" });
    case "draftYear": {
      if (b.days != null && b.days < 0) {
        return fill(t("rpt.b.draftYearLate"), { y: b.year ?? "", n: -b.days });
      }
      return fill(t("rpt.b.draftYear"), { y: b.year ?? "" });
    }
    case "toFix":
      return fill(t("rpt.b.toFix"), { n: b.count ?? 0 });
    case "allClear":
      return t("rpt.b.allClear");
    default:
      return "";
  }
}

const TONE_CLASS: Record<Badge["tone"], string> = {
  ok: "p-done",
  warn: "p-warn",
  bad: "p-overdue",
};

export default function ReportList() {
  const nav = useNavigate();
  const phone = useIsPhone();
  const session = useSession();
  const { lang } = useLang();
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [pinned, setPinned] = useState<string[]>(() => readPinned());

  const catalog = useFrappeGetCall<{ message: CatalogReport[] }>(
    METHOD.listReports,
    undefined,
    `reports-catalog-${lang}`,
  );
  const badgeCall = useFrappeGetCall<{ message: BadgePayload }>(
    METHOD.reportBadges,
    { company: session.company },
    session.user ? ["report-badges", session.company ?? ""] : null,
  );
  const badges = badgeCall.data?.message?.badges ?? {};

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      const typing = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement;
      if (e.key === "/" && !typing) {
        e.preventDefault();
        search.current?.focus();
      }
      if (e.key === "Escape" && el === search.current) setQuery("");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const togglePin = (report: string) => {
    setPinned((list) => {
      const next = list.includes(report) ? list.filter((r) => r !== report) : [...list, report];
      writePinned(next);
      return next;
    });
  };

  const sections = useMemo(() => {
    const rows = catalog.data?.message ?? [];
    const q = deferredQuery.trim().toLowerCase();
    const groups = new Map<
      ReportSection,
      { report: string; label: string; desc: string; icon: string; pinned: boolean }[]
    >();

    for (const row of rows) {
      const meta = metaFor(row.report);
      const desc = meta.desc ? t(meta.desc) : "";
      if (q && !`${row.label} ${row.report} ${desc}`.toLowerCase().includes(q)) continue;
      const list = groups.get(meta.section) ?? [];
      list.push({
        report: row.report,
        label: row.label,
        desc,
        icon: ICON_PATH[meta.icon],
        pinned: pinned.includes(row.report),
      });
      groups.set(meta.section, list);
    }

    return SECTION_ORDER.filter((key) => (groups.get(key)?.length ?? 0) > 0).map((key) => {
      const list = [...(groups.get(key) ?? [])].sort((a, b) => Number(b.pinned) - Number(a.pinned));
      const total = (catalog.data?.message ?? []).filter((r) => metaFor(r.report).section === key)
        .length;
      return { key, rows: list, total };
    });
  }, [catalog.data, deferredQuery, pinned]);

  const shown = sections.reduce((n, s) => n + s.rows.length, 0);
  const total = catalog.data?.message?.length ?? 0;
  const q = deferredQuery.trim();

  return (
    <div className="rpt">
      <PageHead
        title={t("rpt.title")}
        sub={phone ? undefined : t("rpt.sub")}
        /* The filter is typed into, not tapped: it stays in the header on a
           phone rather than sitting over the list it is filtering. */
        stickyActions={false}
        actions={
          <label className="rpt-search">
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
              <circle cx="7" cy="7" r="4.5" />
              <path d="M10.5 10.5 14 14" />
            </svg>
            <input
              ref={search}
              className="ctl"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("rpt.filter")}
              aria-label={t("rpt.filter")}
            />
            {!phone && (
              <span className="rpt-kbd" aria-hidden="true">/</span>
            )}
          </label>
        }
      />

      {catalog.error && <ErrorBox error={catalog.error} onRetry={() => catalog.mutate()} />}

      {catalog.isLoading && total === 0 ? (
        <Loading />
      ) : (
        <>
          {sections.map((section) => (
            <Card
              key={section.key}
              title={t(`rpt.s.${section.key}`)}
              hint={
                q
                  ? fill(t("rpt.ofTotal"), { n: section.rows.length, total: section.total })
                  : t(`rpt.sn.${section.key}`)
              }
              bodyClass="rpt-body"
            >
              <div className="rpt-grid">
                {section.rows.map((row) => {
                  const badge = badges[row.report];
                  return (
                    <div key={row.report} className="rpt-row">
                      <button
                        type="button"
                        className="rpt-open"
                        onClick={() => nav(`/reports/${encodeURIComponent(row.report)}`)}
                      >
                        <span
                          className={`rpt-ic${
                            metaFor(row.report).section === "uae" ? " rpt-ic-uae" : ""
                          }`}
                        >
                          <svg
                            className="ic"
                            viewBox="0 0 24 24"
                            width="18"
                            height="18"
                            aria-hidden="true"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d={row.icon} />
                          </svg>
                        </span>
                        <span className="rpt-text">
                          <span className="rpt-name">
                            <span>{row.label}</span>
                            {badge && (
                              <span className={`pill ${TONE_CLASS[badge.tone]}`}>
                                {badgeText(badge)}
                              </span>
                            )}
                          </span>
                          {row.desc && <span className="rpt-desc">{row.desc}</span>}
                        </span>
                        <span className="rpt-go" aria-hidden="true">
                          →
                        </span>
                      </button>
                      <button
                        type="button"
                        className={`rpt-star${row.pinned ? " on" : ""}`}
                        aria-pressed={row.pinned}
                        aria-label={
                          row.pinned
                            ? fill(t("rpt.unpin"), { r: row.label })
                            : fill(t("rpt.pin"), { r: row.label })
                        }
                        onClick={() => togglePin(row.report)}
                      >
                        <svg
                          className="ic"
                          viewBox="0 0 24 24"
                          width="15"
                          height="15"
                          aria-hidden="true"
                          fill={row.pinned ? "currentColor" : "none"}
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.6-4.8 2.6.9-5.4L4.2 9.7l5.4-.8z" />
                        </svg>
                      </button>
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}

          {shown === 0 && (
            <div className="card rpt-empty">
              {total === 0 ? (
                <p className="rpt-empty-t">{t("rpt.none")}</p>
              ) : (
                <>
                  <p className="rpt-empty-t">{fill(t("rpt.noMatch"), { q: query })}</p>
                  <p>{t("rpt.noMatchHint")}</p>
                </>
              )}
            </div>
          )}

          {total > 0 && (
            <p className="rpt-foot">
              {q
                ? fill(t("rpt.matchCount"), { n: shown, total })
                : fill(t("rpt.count"), { n: total })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export const KNOWN_REPORTS = Object.keys(REPORT_META);
