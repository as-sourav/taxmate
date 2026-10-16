/**
 * Team list — compact rows like a Frappe List View.
 * Role editing lives on TeamDetail tabs (Details / Roles / Access).
 * Catalog: list_users. User is not a resource doctype.
 * Roster is scoped to the session active company.
 */
import { useFrappeGetCall } from "frappe-react-sdk";
import { useNavigate } from "react-router-dom";

import { DataTable, type Column } from "../../components/DataTable";
import { Card, ErrorBox, Loading, PageHead, Pill } from "../../components/ui";
import { t } from "../../i18n/strings";
import { METHOD } from "../../lib/frappe";
import { canManageUsers, canOnboardCompanyOwner, canViewTeam, type SpaRole } from "../../lib/roles";
import { useSession } from "../../lib/session";

export type TeamUser = {
  name: string;
  email?: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  mobile_no?: string | null;
  language?: string | null;
  enabled?: number;
  spa_role?: SpaRole;
  spa_roles?: SpaRole[];
  extra_roles?: string[];
  last_active?: string | null;
  last_login?: string | null;
  creation?: string | null;
  /** False when this person also works for a company the caller does not own. */
  can_manage?: boolean;
  /** Active company the roster was loaded for. */
  company?: string | null;
};

function roleLabels(u: TeamUser): string[] {
  const spa = (u.spa_roles?.length ? u.spa_roles : [u.spa_role || "viewer"]) as SpaRole[];
  return [...spa.map((r) => t(`role.${r}`)), ...(u.extra_roles ?? []).map((r) => t(`role.${r}`))];
}

export default function TeamList() {
  const nav = useNavigate();
  const session = useSession();
  const owner = canManageUsers(session);
  const provider = canOnboardCompanyOwner(session);
  const allowed = canViewTeam(session);
  const company = session.company || "";
  const list = useFrappeGetCall<{ message: TeamUser[] }>(
    METHOD.listUsers,
    undefined,
    allowed && company ? `team-users-${company}` : null,
    { revalidateOnFocus: false },
  );
  const rows = allowed ? (list.data?.message ?? []) : [];

  if (!session.user) return <Loading />;

  const columns: Column<TeamUser>[] = [
    { key: "name", header: t("team.col.name"), cell: (u) => u.full_name || u.name },
    { key: "email", header: t("team.col.email"), className: "mono", cell: (u) => u.email || u.name },
    { key: "mobile", header: t("team.col.mobile"), cell: (u) => u.mobile_no || "—" },
    {
      key: "role",
      header: t("team.col.role"),
      cell: (u) => (
        <span className="team-pills">
          {roleLabels(u).map((label) => (
            <Pill key={label} cls="p-open">{label}</Pill>
          ))}
        </span>
      ),
    },
    {
      key: "enabled",
      header: t("team.col.status"),
      cell: (u) => (
        <Pill cls={u.enabled ? "p-done" : "p-flat"}>
          {u.enabled ? t("team.active") : t("team.disabled")}
        </Pill>
      ),
    },
  ];

  return (
    <>
      <PageHead
        title={t("team.title")}
        actions={
          owner ? (
            <button type="button" className="btn" onClick={() => nav("/team/new")}>
              {t("team.invite")}
            </button>
          ) : provider ? (
            <button type="button" className="btn" onClick={() => nav("/team/onboard-owner")}>
              {t("team.onboardOwner")}
            </button>
          ) : null
        }
      />
      {provider && (
        <p className="muted" style={{ margin: "0 0 12px" }}>
          {t("team.onboardOwnerHint")}
        </p>
      )}
      {!allowed && !provider && <ErrorBox error={{ message: t("team.denied") }} />}
      {allowed && !company && <ErrorBox error={{ message: t("team.needCompany") }} />}
      {allowed && company ? (
        <p className="muted" style={{ margin: "0 0 12px" }}>
          {t("team.companyScope").replace("{company}", company)}
        </p>
      ) : null}
      {list.error && <ErrorBox error={list.error} onRetry={() => list.mutate()} />}
      {allowed && company && (
        <Card bodyClass={null as unknown as string}>
          <DataTable<TeamUser>
            rows={rows}
            rowKey={(u) => u.name}
            state={{ isLoading: list.isLoading, error: null, onRetry: () => list.mutate() }}
            emptyLabel={t("team.empty")}
            columns={columns}
            onOpen={(u) => nav(`/team/${encodeURIComponent(u.name)}`)}
          />
        </Card>
      )}
    </>
  );
}
