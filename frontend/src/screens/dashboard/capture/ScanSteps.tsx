/**
 * Horizontal step rail for Scan-to-draft.
 * Callers: CaptureDesk CapturePanel (under title).
 * Distinct from ScanProgress (OCR stage chips during reading).
 * No data I/O — presentational only.
 * User: "Rebuilt the complete UI/UX for this feature… classy, modern and professional."
 */

import { t } from "../../../i18n/strings";

export type ScanStepId = "capture" | "frame" | "read" | "review";

const STEPS: { id: ScanStepId; labelKey: string }[] = [
  { id: "capture", labelKey: "idp.step.capture" },
  { id: "frame", labelKey: "idp.step.frame" },
  { id: "read", labelKey: "idp.step.read" },
  { id: "review", labelKey: "idp.step.review" },
];

const ORDER: ScanStepId[] = ["capture", "frame", "read", "review"];

type Props = {
  current: ScanStepId;
  /** When true, Frame is skipped (PDF / non-image). */
  skipFrame?: boolean;
};

export function ScanSteps({ current, skipFrame }: Props) {
  const visible = skipFrame ? STEPS.filter((s) => s.id !== "frame") : STEPS;
  const curIdx = ORDER.indexOf(current);

  return (
    <nav className="idp-steps" aria-label={t("idp.stages")}>
      <ol className="idp-steps-list">
        {visible.map((step, index) => {
          const stepIdx = ORDER.indexOf(step.id);
          const state =
            stepIdx < curIdx ? "done" : stepIdx === curIdx ? "active" : "pending";
          return (
            <li
              key={step.id}
              className="idp-steps-item"
              data-state={state}
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="idp-steps-num" aria-hidden="true">
                {state === "done" ? (
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path
                      d="M2.5 6.2L4.8 8.5L9.5 3.5"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  index + 1
                )}
              </span>
              <span className="idp-steps-label">{t(step.labelKey)}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
