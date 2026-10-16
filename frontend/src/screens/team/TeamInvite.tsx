/**
 * Invite a teammate. Catalog invite_user — User is not a resource doctype.
 * Roles are multi-select; Frappe unions DocPerms across Has Role rows.
 * Invite always binds the new user to the session active company.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { FormLayout } from "../../components/form";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { t } from "../../i18n/strings";
import { METHOD } from "../../lib/frappe";
import { canManageUsers, SPA_ROLES, type SpaRole } from "../../lib/roles";
import { useSession } from "../../lib/session";

export default function TeamInvite() {
  const nav = useNavigate();
  const session = useSession();
  const owner = canManageUsers(session);
  const company = session.company || "";
  const invite = useFrappePostCall<{ message: { name: string } }>(METHOD.inviteUser);
  const flags = useFrappeGetCall<{ message: { addon_roles?: string[] } }>(
    METHOD.getFeatureFlags,
    undefined,
    "invite-feature-flags",
    { revalidateOnFocus: false },
  );
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [roles, setRoles] = useState<SpaRole[]>(["clerk"]);
  const [extraRoles, setExtraRoles] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const addonRoles = flags.data?.message?.addon_roles ?? [];

  if (!session.user) return <Loading />;

  const ready = owner && !!company && firstName.trim() && email.trim() && roles.length > 0;

  function toggleSpa(role: SpaRole) {
    setRoles((prev) => {
      const next = prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role];
      return next.length ? next : prev;
    });
  }

  function toggleExtra(role: string) {
    setExtraRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    );
  }

  async function submit() {
    if (!ready) return;
    setBusy(true);
    try {
      await invite.call({
        email: email.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        mobile_no: mobile.trim(),
        spa_roles: JSON.stringify(roles),
        extra_roles: JSON.stringify(extraRoles),
        send_welcome_email: 1,
      });
      nav("/team");
    } finally {
      setBusy(false);
    }
  }

  const title = company
    ? t("team.inviteFor").replace("{company}", company)
    : t("team.invite");

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/team")}>
            {t("nav.team")}
          </button>
        }
        title={title}
        actions={
          <>
            <button type="button" className="btn ghost" onClick={() => nav("/team")}>{t("soc.discard")}</button>
            <button
              type="button"
              className="btn"
              disabled={busy || invite.loading || !ready}
              onClick={() => void submit()}
            >
              {busy || invite.loading ? t("soc.saving") : t("team.sendInvite")}
            </button>
          </>
        }
      />
      {!owner && <ErrorBox error={{ message: t("team.denied") }} />}
      {owner && !company && <ErrorBox error={{ message: t("team.needCompany") }} />}
      {invite.error && <ErrorBox error={invite.error} />}
      <FormLayout>
        <Card>
          <form className="stack" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
            {company ? (
              <p className="muted" style={{ margin: 0 }}>
                {t("team.companyScope").replace("{company}", company)}
              </p>
            ) : null}
            <div className="grid2">
              <Field label={t("team.firstName")} required htmlFor="team-first-name">
                <input id="team-first-name" name="first_name" className="ctl" value={firstName}
                  autoComplete="given-name" onChange={(e) => setFirstName(e.target.value)} />
              </Field>
              <Field label={t("team.lastName")} htmlFor="team-last-name">
                <input id="team-last-name" name="last_name" className="ctl" value={lastName}
                  autoComplete="family-name" onChange={(e) => setLastName(e.target.value)} />
              </Field>
              <Field label={t("team.col.email")} required htmlFor="team-email">
                <input id="team-email" name="email" className="ctl" type="email" value={email}
                  autoComplete="email" onChange={(e) => setEmail(e.target.value)} />
              </Field>
              <Field label={t("team.col.mobile")} htmlFor="team-mobile">
                <input id="team-mobile" name="mobile_no" className="ctl" type="tel" value={mobile}
                  autoComplete="tel" onChange={(e) => setMobile(e.target.value)} />
              </Field>
            </div>
            <Field label={t("team.col.role")} required>
              <div className="stack" style={{ gap: 8 }}>
                {SPA_ROLES.map((r) => (
                  <label key={r} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleSpa(r)} />
                    {t(`role.${r}`)}
                  </label>
                ))}
                {addonRoles.length > 0 && (
                  <>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{t("team.roles.addons")}</div>
                    {addonRoles.map((r) => (
                      <label key={r} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <input type="checkbox" checked={extraRoles.includes(r)} onChange={() => toggleExtra(r)} />
                        {t(`role.${r}`)}
                      </label>
                    ))}
                  </>
                )}
              </div>
            </Field>
          </form>
        </Card>
      </FormLayout>
    </>
  );
}
