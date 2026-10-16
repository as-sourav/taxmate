/**
 * Team member detail — Frappe User-style tabs: Details | Roles | Access.
 * Catalog: get_user, update_user, set_user_role, set_user_enabled, reset_user_password.
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { FormLayout } from "../../components/form";
import { Card, ErrorBox, Field, Loading, PageHead, Pill } from "../../components/ui";
import { t } from "../../i18n/strings";
import { METHOD } from "../../lib/frappe";
import { canManageUsers, canViewTeam, SPA_ROLES, type SpaRole } from "../../lib/roles";
import { useSession } from "../../lib/session";

import type { TeamUser } from "./TeamList";

type TabId = "details" | "roles" | "access";

export default function TeamDetail() {
  const { name: rawName } = useParams<{ name: string }>();
  const userName = rawName ? decodeURIComponent(rawName) : "";
  const nav = useNavigate();
  const session = useSession();
  const owner = canManageUsers(session);
  const allowed = canViewTeam(session);
  const self = userName === session.user;

  const [tab, setTab] = useState<TabId>("details");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [mobile, setMobile] = useState("");
  const [language, setLanguage] = useState("");
  const [spaRoles, setSpaRoles] = useState<SpaRole[]>([]);
  const [extraRoles, setExtraRoles] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const company = session.company || "";
  const get = useFrappeGetCall<{ message: TeamUser }>(
    METHOD.getUser,
    { user: userName },
    allowed && userName && company ? `team-user-${company}-${userName}` : null,
    { revalidateOnFocus: false },
  );
  const canEdit = owner && !self && get.data?.message?.can_manage !== false;
  const flags = useFrappeGetCall<{ message: { addon_roles?: string[] } }>(
    METHOD.getFeatureFlags,
    undefined,
    "team-detail-flags",
    { revalidateOnFocus: false },
  );
  const updateUser = useFrappePostCall<{ message: TeamUser }>(METHOD.updateUser);
  const setRole = useFrappePostCall<{ message: TeamUser }>(METHOD.setUserRole);
  const setEnabled = useFrappePostCall<{ message: TeamUser }>(METHOD.setUserEnabled);
  const resetPassword = useFrappePostCall<{ message: { ok: string } }>(METHOD.resetUserPassword);

  const doc = get.data?.message;
  const addonRoles = flags.data?.message?.addon_roles ?? [];

  useEffect(() => {
    if (!doc) return;
    setFirstName(doc.first_name || "");
    setLastName(doc.last_name || "");
    setMobile(doc.mobile_no || "");
    setLanguage(doc.language || "");
    setSpaRoles((doc.spa_roles?.length ? doc.spa_roles : [doc.spa_role || "viewer"]) as SpaRole[]);
    setExtraRoles(doc.extra_roles ?? []);
    setNote(null);
  }, [doc]);

  if (!session.user) return <Loading />;
  if (!allowed) return <ErrorBox error={{ message: t("team.denied") }} />;
  if (get.isLoading && !doc) return <Loading />;
  if (get.error) return <ErrorBox error={get.error} onRetry={() => get.mutate()} />;
  if (!doc) return <ErrorBox error={{ message: t("team.empty") }} />;

  function toggleSpa(role: SpaRole) {
    setSpaRoles((prev) => {
      const next = prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role];
      return next.length ? next : prev;
    });
    setNote(null);
  }

  function toggleExtra(role: string) {
    setExtraRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    );
    setNote(null);
  }

  async function saveDetails() {
    if (!canEdit) return;
    setBusy(true);
    setNote(null);
    try {
      await updateUser.call({
        user: userName,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        mobile_no: mobile.trim(),
        language: language.trim(),
      });
      await get.mutate();
      setNote(t("team.saved"));
    } finally {
      setBusy(false);
    }
  }

  async function saveRoles() {
    if (!canEdit || !spaRoles.length) return;
    setBusy(true);
    setNote(null);
    try {
      await setRole.call({
        user: userName,
        spa_roles: JSON.stringify(spaRoles),
        extra_roles: JSON.stringify(extraRoles),
      });
      await get.mutate();
      setNote(t("team.saved"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled() {
    if (!canEdit) return;
    setBusy(true);
    setNote(null);
    try {
      await setEnabled.call({ user: userName, enabled: doc!.enabled ? 0 : 1 });
      await get.mutate();
    } finally {
      setBusy(false);
    }
  }

  async function sendReset() {
    if (!canEdit) return;
    setBusy(true);
    setNote(null);
    try {
      await resetPassword.call({ user: userName });
      setNote(t("team.resetPasswordDone"));
    } finally {
      setBusy(false);
    }
  }

  const err = updateUser.error || setRole.error || setEnabled.error || resetPassword.error;

  const tabs: { id: TabId; label: string }[] = [
    { id: "details", label: t("team.tab.details") },
    { id: "roles", label: t("team.tab.roles") },
    { id: "access", label: t("team.tab.access") },
  ];

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/team")}>
            {t("nav.team")}
          </button>
        }
        title={doc.full_name || doc.name}
        sub={doc.email || doc.name}
        actions={
          <Pill cls={doc.enabled ? "p-done" : "p-flat"}>
            {doc.enabled ? t("team.active") : t("team.disabled")}
          </Pill>
        }
      />
      {err && <ErrorBox error={err} />}
      {note && <p className="od-note">{note}</p>}

      <div className="ftabs" role="tablist" aria-label={t("team.title")}>
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`team-tab-${item.id}`}
            aria-controls={`team-panel-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            className={`ftab${tab === item.id ? " on" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <FormLayout>
        {tab === "details" && (
          <div role="tabpanel" id="team-panel-details" aria-labelledby="team-tab-details">
          <Card title={t("team.tab.details")}>
            <form
              className="stack"
              onSubmit={(e) => {
                e.preventDefault();
                void saveDetails();
              }}
            >
              <div className="grid2">
                <Field label={t("team.firstName")} required htmlFor="tu-first">
                  <input
                    id="tu-first"
                    className="ctl"
                    value={firstName}
                    disabled={!canEdit || busy}
                    onChange={(e) => setFirstName(e.target.value)}
                  />
                </Field>
                <Field label={t("team.lastName")} htmlFor="tu-last">
                  <input
                    id="tu-last"
                    className="ctl"
                    value={lastName}
                    disabled={!canEdit || busy}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </Field>
                <Field label={t("team.col.email")} htmlFor="tu-email">
                  <input id="tu-email" className="ctl readonly" value={doc.email || doc.name} readOnly disabled />
                  <span className="f help">{t("team.emailLocked")}</span>
                </Field>
                <Field label={t("team.col.mobile")} htmlFor="tu-mobile">
                  <input
                    id="tu-mobile"
                    className="ctl"
                    type="tel"
                    value={mobile}
                    disabled={!canEdit || busy}
                    onChange={(e) => setMobile(e.target.value)}
                  />
                </Field>
                <Field label={t("team.language")} htmlFor="tu-lang">
                  <input
                    id="tu-lang"
                    className="ctl"
                    value={language}
                    placeholder="en / ar"
                    disabled={!canEdit || busy}
                    onChange={(e) => setLanguage(e.target.value)}
                  />
                </Field>
              </div>
              {canEdit && (
                <div className="acts">
                  <button type="submit" className="btn" disabled={busy || !firstName.trim()}>
                    {busy ? t("soc.saving") : t("team.saveDetails")}
                  </button>
                </div>
              )}
            </form>
          </Card>
          </div>
        )}

        {tab === "roles" && (
          <div role="tabpanel" id="team-panel-roles" aria-labelledby="team-tab-roles">
          <Card title={t("team.tab.roles")}>
            <div className="stack" style={{ gap: 10 }}>
              {SPA_ROLES.map((role) => (
                <label key={role} className="team-check">
                  <input
                    type="checkbox"
                    checked={spaRoles.includes(role)}
                    disabled={!canEdit || busy}
                    onChange={() => toggleSpa(role)}
                  />
                  {t(`role.${role}`)}
                </label>
              ))}
              {addonRoles.length > 0 && (
                <>
                  <div className="team-addon-label">{t("team.roles.addons")}</div>
                  {addonRoles.map((role) => (
                    <label key={role} className="team-check">
                      <input
                        type="checkbox"
                        checked={extraRoles.includes(role)}
                        disabled={!canEdit || busy}
                        onChange={() => toggleExtra(role)}
                      />
                      {t(`role.${role}`)}
                    </label>
                  ))}
                </>
              )}
              {canEdit && (
                <div className="acts">
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || !spaRoles.length}
                    onClick={() => void saveRoles()}
                  >
                    {busy ? t("soc.saving") : t("team.saveDetails")}
                  </button>
                </div>
              )}
            </div>
          </Card>
          </div>
        )}

        {tab === "access" && (
          <div role="tabpanel" id="team-panel-access" aria-labelledby="team-tab-access">
          <Card title={t("team.tab.access")}>
            <div className="stack" style={{ gap: 14 }}>
              <div className="grid2">
                <Field label={t("team.col.status")}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Pill cls={doc.enabled ? "p-done" : "p-flat"}>
                      {doc.enabled ? t("team.active") : t("team.disabled")}
                    </Pill>
                    {canEdit && (
                      <button type="button" className="btn ghost sm" disabled={busy} onClick={() => void toggleEnabled()}>
                        {doc.enabled ? t("team.disable") : t("team.enable")}
                      </button>
                    )}
                  </div>
                </Field>
                <Field label={t("team.col.lastLogin")}>
                  <input className="ctl readonly" value={doc.last_login || "—"} readOnly disabled />
                </Field>
                <Field label={t("team.col.lastActive")}>
                  <input className="ctl readonly" value={doc.last_active || "—"} readOnly disabled />
                </Field>
              </div>
              {canEdit && (
                <div className="stack" style={{ gap: 6 }}>
                  <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>{t("team.resetPasswordHint")}</p>
                  <div className="acts">
                    <button
                      type="button"
                      className="btn ghost"
                      disabled={busy || !doc.enabled}
                      onClick={() => void sendReset()}
                    >
                      {t("team.resetPassword")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </Card>
          </div>
        )}
      </FormLayout>
    </>
  );
}
