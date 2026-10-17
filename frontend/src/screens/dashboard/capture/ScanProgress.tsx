import { t } from "../../../i18n/strings";

export type Stage = { key: string; label_key: string; status?: string };

/** Visual-only stage list; live status announced separately via aria-live. */
export function ScanProgress({ stages }: { stages: Stage[] }) {
  if (!stages.length) return null;
  return (
    <ol className="idp-stages" aria-hidden="true">
      {stages.map((row) => (
        <li key={row.key} data-status={row.status || "pending"}>
          {t(row.label_key)}
        </li>
      ))}
    </ol>
  );
}
