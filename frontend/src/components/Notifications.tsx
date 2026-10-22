import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { t } from "../i18n/strings";
import { METHOD } from "../lib/frappe";
import { getLocale } from "../lib/i18n";
import { useSession } from "../lib/session";

const PANEL_ID = "taxmate-inbox";

type InboxItem = {
  id: string;
  kind: "log" | "todo";
  name: string;
  title: string;
  created: string;
  document_type: string | null;
  document_name: string | null;
  route: string | null;
  can_mark_read: boolean;
};

type Inbox = {
  unread: number;
  has_more: boolean;
  items: InboxItem[];
};

type InboxPayload = { message: Inbox };

type InboxContextValue = {
  state: {
    open: boolean;
    items: InboxItem[];
    unread: number;
    hasMore: boolean;
    loading: boolean;
    error: string | null;
  };
  actions: {
    toggle: () => void;
    close: () => void;
    markRead: (name: string) => void;
    markAllRead: () => void;
    refresh: () => void;
  };
  meta: {
    buttonRef: React.MutableRefObject<HTMLButtonElement | null>;
    panelId: string;
  };
};

const InboxContext = createContext<InboxContextValue | null>(null);

function useInbox(): InboxContextValue {
  const value = useContext(InboxContext);
  if (!value) throw new Error("Inbox controls must render inside Notifications");
  return value;
}

const UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["week", 60 * 60 * 24 * 7],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
  ["second", 1],
];

function relativeTime(created: string): string {
  const then = Date.parse(created.replace(" ", "T"));
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((then - Date.now()) / 1000);
  const format = new Intl.RelativeTimeFormat(getLocale(), { numeric: "auto" });
  const abs = Math.abs(seconds);
  for (const [unit, size] of UNITS) {
    if (abs >= size || unit === "second") return format.format(Math.round(seconds / size), unit);
  }
  return "";
}

function withoutLog(inbox: Inbox, name: string): Inbox {
  const items = inbox.items.filter((row) => !(row.kind === "log" && row.name === name));
  return { ...inbox, items, unread: Math.max(0, inbox.unread - (inbox.items.length - items.length)) };
}

function withoutLogs(inbox: Inbox): Inbox {
  const items = inbox.items.filter((row) => row.kind === "todo");
  return { ...inbox, items, unread: items.length, has_more: false };
}

function InboxProvider({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const [open, setOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, isLoading, mutate } = useFrappeGetCall<InboxPayload>(
    METHOD.listInbox,
    undefined,
    `inbox:${session.company ?? ""}`,
    { refreshInterval: 60_000, revalidateOnFocus: true },
  );
  const markOne = useFrappePostCall(METHOD.markNotificationRead);
  const markAll = useFrappePostCall(METHOD.markAllNotificationsRead);
  const inbox = data?.message;

  const refresh = useCallback(() => {
    setActionError(null);
    void mutate();
  }, [mutate]);

  const toggle = useCallback(() => {
    setOpen((current) => {
      if (!current) void mutate();
      return !current;
    });
  }, [mutate]);

  const close = useCallback(() => setOpen(false), []);

  const markRead = useCallback((name: string) => {
    setActionError(null);
    void (async () => {
      let previous: InboxPayload | undefined;
      await mutate((current) => {
        previous = current;
        if (!current?.message) return current;
        return { message: withoutLog(current.message, name) };
      }, { revalidate: false });
      try {
        await markOne.call({ name });
        void mutate();
      } catch {
        await mutate(previous, { revalidate: false });
        setActionError(t("inbox.error"));
      }
    })();
  }, [markOne, mutate]);

  const markAllRead = useCallback(() => {
    setActionError(null);
    void (async () => {
      let previous: InboxPayload | undefined;
      await mutate((current) => {
        previous = current;
        if (!current?.message) return current;
        return { message: withoutLogs(current.message) };
      }, { revalidate: false });
      try {
        await markAll.call({});
        void mutate();
      } catch {
        await mutate(previous, { revalidate: false });
        setActionError(t("inbox.error"));
      }
    })();
  }, [markAll, mutate]);

  const value = useMemo<InboxContextValue>(() => ({
    state: {
      open,
      items: inbox?.items ?? [],
      unread: inbox?.unread ?? 0,
      hasMore: inbox?.has_more ?? false,
      loading: isLoading && !inbox,
      error: actionError || (error ? t("inbox.error") : null),
    },
    actions: { toggle, close, markRead, markAllRead, refresh },
    meta: { buttonRef, panelId: PANEL_ID },
  }), [open, inbox, isLoading, actionError, error, toggle, close, markRead, markAllRead, refresh]);

  return <InboxContext.Provider value={value}>{children}</InboxContext.Provider>;
}

function Bell() {
  const { state, actions, meta } = useInbox();
  const count = t("a11y.unread").replace("{n}", String(state.unread));
  const label = state.unread > 0 ? `${t("a11y.notifications")}, ${count}` : t("a11y.notifications");
  return (
    <button
      ref={(node) => {
        meta.buttonRef.current = node;
      }}
      type="button"
      className="iconbtn bordered nbell"
      aria-label={label}
      aria-expanded={state.open}
      aria-haspopup="dialog"
      aria-controls={meta.panelId}
      onClick={actions.toggle}
    >
      <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <path d="M9 2.2a4.2 4.2 0 0 0-4.2 4.2c0 3.2-1.1 4.4-1.6 5h11.6c-.5-.6-1.6-1.8-1.6-5A4.2 4.2 0 0 0 9 2.2z" />
        <path d="M7.2 13.6a1.8 1.8 0 0 0 3.6 0" />
      </svg>
      {state.unread > 0 ? <span className="nbadge" aria-hidden="true">{state.unread > 9 ? "9+" : state.unread}</span> : null}
    </button>
  );
}

function InboxSkeleton() {
  return (
    <div className="nlist" aria-busy="true">
      <div className="nskel" />
      <div className="nskel" />
      <div className="nskel" />
    </div>
  );
}

function InboxEmpty() {
  return (
    <div className="nempty">
      <p className="nempty-title">{t("inbox.emptyTitle")}</p>
      <p>{t("inbox.emptyBody")}</p>
    </div>
  );
}

function InboxError() {
  const { actions } = useInbox();
  return (
    <div className="nerr" role="alert">
      <p>{t("inbox.error")}</p>
      <button type="button" className="nmark" onClick={actions.refresh}>{t("inbox.retry")}</button>
    </div>
  );
}

function docLabel(doctype: string | null): string | null {
  if (!doctype) return null;
  const key = `idp.dt.${doctype}`;
  const label = t(key);
  return label === key ? null : label;
}

function InboxRow({ row }: { row: InboxItem }) {
  const { actions } = useInbox();
  const label = docLabel(row.document_type);
  const when = relativeTime(row.created);
  return (
    <div className={`nrow ${row.kind === "todo" ? "nrow-todo" : "nrow-log"}`}>
      <span className="ndot" aria-hidden="true" />
      <div className="nrow-copy">
        {row.route ? (
          <Link to={row.route} className="nrow-main" data-inbox-row onClick={actions.close}>
            {row.title}
          </Link>
        ) : (
          <div className="nrow-main" data-inbox-row tabIndex={0}>{row.title}</div>
        )}
        <p className="nmeta">
          {label ? <span>{label}</span> : <span>{t(row.kind === "todo" ? "inbox.reminder" : "inbox.update")}</span>}
          {when ? <time dateTime={row.created}>{when}</time> : null}
        </p>
      </div>
      {row.can_mark_read ? (
        <button
          type="button"
          className="nmark ncheck"
          onClick={() => actions.markRead(row.name)}
          aria-label={`${t("inbox.markRead")}, ${row.title}`}
          title={t("inbox.markRead")}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M3.2 8.2 6.4 11.4 12.8 4.6" />
          </svg>
        </button>
      ) : null}
    </div>
  );
}

function InboxList() {
  const { state } = useInbox();
  const reminders = state.items.filter((row) => row.kind === "todo");
  const updates = state.items.filter((row) => row.kind === "log");
  const split = reminders.length > 0 && updates.length > 0;
  return (
    <div className="nlist">
      {reminders.length > 0 ? (
        <section className="nsection">
          {split ? <h3 className="nsection-label">{t("inbox.reminders")}</h3> : null}
          {reminders.map((row) => <InboxRow key={row.id} row={row} />)}
        </section>
      ) : null}
      {updates.length > 0 ? (
        <section className="nsection">
          {split ? <h3 className="nsection-label">{t("inbox.updates")}</h3> : null}
          {updates.map((row) => <InboxRow key={row.id} row={row} />)}
        </section>
      ) : null}
      {state.hasMore ? <p className="nmore">{t("inbox.latest")}</p> : null}
    </div>
  );
}

function PanelBody() {
  const { state } = useInbox();
  if (state.error) return <InboxError />;
  if (state.loading) return <InboxSkeleton />;
  if (state.items.length === 0) return <InboxEmpty />;
  return <InboxList />;
}

function Panel() {
  const { state, actions, meta } = useInbox();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(actions.close);
  closeRef.current = actions.close;
  const canMarkAll = state.items.some((row) => row.can_mark_read);

  useEffect(() => {
    if (!state.open) return;
    panelRef.current?.querySelector<HTMLElement>("[data-inbox-row]")?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeRef.current();
      meta.buttonRef.current?.focus();
    }
    function onPointer(event: MouseEvent) {
      const wrap = meta.buttonRef.current?.closest(".nwrap");
      if (wrap && !wrap.contains(event.target as Node)) closeRef.current();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [state.open, meta.buttonRef]);

  function onPanelKey(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Tab") {
      actions.close();
      return;
    }
    const rows = [...(panelRef.current?.querySelectorAll<HTMLElement>("[data-inbox-row]") ?? [])];
    if (rows.length === 0) return;
    const index = rows.indexOf(document.activeElement as HTMLElement);
    const next =
      event.key === "ArrowDown" ? (index + 1) % rows.length
      : event.key === "ArrowUp" ? (index - 1 + rows.length) % rows.length
      : event.key === "Home" ? 0
      : event.key === "End" ? rows.length - 1
      : -1;
    if (next < 0) return;
    event.preventDefault();
    rows[next]?.focus();
  }

  if (!state.open) return null;

  return (
    <div
      ref={panelRef}
      id={meta.panelId}
      className="npanel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="taxmate-inbox-title"
      onKeyDown={onPanelKey}
    >
      <div className="nhead">
        <h2 id="taxmate-inbox-title">{t("a11y.notifications")}</h2>
        {canMarkAll ? (
          <button type="button" className="nmark" onClick={actions.markAllRead}>{t("inbox.markAll")}</button>
        ) : null}
      </div>
      <PanelBody />
    </div>
  );
}

export default function Notifications() {
  return (
    <div className="nwrap">
      <InboxProvider>
        <Bell />
        <Panel />
      </InboxProvider>
    </div>
  );
}
