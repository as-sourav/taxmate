/**
 * App provider assigns the primary TaxMate Owner for the active company.
 * Administrator is never the company owner.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { FormLayout } from "../../components/form";
import { Card, ErrorBox, Field, Loading, PageHead } from "../../components/ui";
import { t } from "../../i18n/strings";
import { DT, METHOD } from "../../lib/frappe";
import { canOnboardCompanyOwner } from "../../lib/roles";
import { useSession } from "../../lib/session";

type CompanyDoc = {
  name: string;
  company_name?: string;
  custom_taxmate_owner?: string | null;
};

export default function OnboardOwner() {
  const nav = useNavigate();
  const session = useSession();
  const allowed = canOnboardCompanyOwner(session);
  const company = session.company || "";
  const onboard = useFrappePostCall<{ message: { name: string; company?: string } }>(
    METHOD.onboardCompanyOwner,
  );
  const companyDoc = useFrappeGetCall<{ message: CompanyDoc }>(
    METHOD.get,
    { doctype: DT.company, name: company },
    allowed && company ? `onboard-company-${company}` : null,
    { revalidateOnFocus: false },
  );
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  if (!session.user) return <Loading />;

  const currentOwner = companyDoc.data?.message?.custom_taxmate_owner || "";
  const companyLabel = companyDoc.data?.message?.company_name || company;
  const ready = allowed && !!company && firstName.trim() && email.trim();

  async function submit() {
    if (!ready) return;
    setBusy(true);
    setDone(null);
    try {
      const res = await onboard.call({
        company,
        email: email.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        mobile_no: mobile.trim(),
        send_welcome_email: 1,
      });
      setDone(res.message?.name || email.trim());
      await companyDoc.mutate();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead
        eyebrow={
          <button type="button" className="btn quiet" onClick={() => nav("/team")}>
            {t("nav.team")}
          </button>
        }
        title={t("team.onboardOwner")}
        actions={
          <button
            type="button"
            className="btn"
            disabled={busy || onboard.loading || !ready}
            onClick={() => void submit()}
          >
            {busy || onboard.loading ? t("soc.saving") : t("team.onboardOwnerSubmit")}
          </button>
        }
      />
      {!allowed && <ErrorBox error={{ message: t("team.denied") }} />}
      {allowed && !company && <ErrorBox error={{ message: t("team.needCompany") }} />}
      {onboard.error && <ErrorBox error={onboard.error} />}
      {done && (
        <p className="muted" style={{ margin: "0 0 12px" }}>
          {t("team.onboardOwnerDone")} ({done})
        </p>
      )}
      <FormLayout>
        <Card>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <p className="muted" style={{ margin: 0 }}>
              {t("team.onboardOwnerHint")}
            </p>
            {company ? (
              <p style={{ margin: 0 }}>
                <strong>{companyLabel}</strong>
              </p>
            ) : null}
            <p className="muted" style={{ margin: 0 }}>
              {currentOwner
                ? `${t("team.currentOwner")}: ${currentOwner}`
                : t("team.noOwnerYet")}
            </p>
            <div className="grid2">
              <Field label={t("team.firstName")} required htmlFor="onboard-first">
                <input
                  id="onboard-first"
                  className="ctl"
                  value={firstName}
                  autoComplete="given-name"
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </Field>
              <Field label={t("team.lastName")} htmlFor="onboard-last">
                <input
                  id="onboard-last"
                  className="ctl"
                  value={lastName}
                  autoComplete="family-name"
                  onChange={(e) => setLastName(e.target.value)}
                />
              </Field>
              <Field label={t("team.col.email")} required htmlFor="onboard-email">
                <input
                  id="onboard-email"
                  className="ctl"
                  type="email"
                  value={email}
                  autoComplete="email"
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field label={t("team.col.mobile")} htmlFor="onboard-mobile">
                <input
                  id="onboard-mobile"
                  className="ctl"
                  type="tel"
                  value={mobile}
                  autoComplete="tel"
                  onChange={(e) => setMobile(e.target.value)}
                />
              </Field>
            </div>
          </form>
        </Card>
      </FormLayout>
    </>
  );
}
