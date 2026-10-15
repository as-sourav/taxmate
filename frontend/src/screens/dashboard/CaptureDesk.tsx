/**
 * Scan panel — create a draft from a photo or file via IDP.
 * On mobile/native: Take photo (capture) or Choose file. Desktop: file only.
 * One job only: create. Dialog stays open until Close/Cancel; that aborts work.
 */

import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { useIsMobileShell } from "../../components/MobileNav";
import { METHOD, readableError } from "../../lib/frappe";
import { t } from "../../i18n/strings";
import { apiFetch } from "../../mobile/http";
import { isNative } from "../../mobile/platform";

type Target = {
  doctype: string;
  label_key: string;
  route: string | null;
  ready: boolean;
};

type Action = {
  id: string;
  label_key: string;
  needs_file: boolean;
  needs_query: boolean;
  query_key: string | null;
  pick_key: string;
  run_key: string;
  runnable: boolean;
  pending_key: string;
  targets: Target[];
};

type Stage = { key: string; label_key: string; status?: string };

type Surface = {
  title_key: string;
  notices: string[];
  accept: string[];
  read_stages?: Stage[];
  actions: Action[];
};

type Write = { field: string; label_key: string; value: string; options?: string[] };

type Proposal = {
  key: string;
  doctype: string;
  title: string;
  consent_label_key: string;
  confirmed: boolean;
  required_fields: Write[];
  optional_fields: Write[];
};

type Review = {
  ok?: boolean;
  step?: string;
  error_key?: string | null;
  detail?: string | null;
  lines?: { label_key: string; value: string }[];
  items?: { label: string }[];
  gaps?: string[];
  writes?: Write[];
  proposals?: Proposal[];
  stage_log?: Stage[];
  can_save?: boolean;
  can_submit?: boolean;
  can_delete?: boolean;
  used_llm?: boolean;
  save_key?: string | null;
  route?: string | null;
  name?: string;
  matches?: { name: string; label: string; route: string | null }[];
  diffs?: { label_key: string; before: string; after: string; status: string }[];
};

type Phase = "idle" | "uploading" | "reading" | "saving";

const PREFERRED_TARGET = "Sales Invoice";

export function CaptureDesk() {
  const [open, setOpen] = useState(false);
  const openRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button
        ref={openRef}
        type="button"
        className="btn scanbtn"
        aria-label={t("idp.open")}
        onClick={() => setOpen(true)}
      >
        <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
          <path d="M3.2 6.2V3.4h2.8M14.8 6.2V3.4h-2.8M3.2 11.8v2.8h2.8M14.8 11.8v2.8h-2.8M2.8 9h12.4" />
        </svg>
        <span className="scanbtn-lab">{t("idp.open")}</span>
      </button>
      {open ? (
        <CapturePanel
          onClose={() => {
            setOpen(false);
            openRef.current?.focus();
          }}
        />
      ) : null}
    </>
  );
}

function CapturePanel({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const statusId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lock = useRef(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const nav = useNavigate();
  const mobileShell = useIsMobileShell();
  /** Camera capture on phone/shell and native apps; desktop keeps file-only. */
  const showCamera = mobileShell || isNative();
  const res = useFrappeGetCall<{ message: Surface }>(METHOD.idpSurface, undefined, "idp-surface");
  const surface = res.data?.message;
  const action = surface?.actions?.find((row) => row.id === "create") ?? surface?.actions?.[0] ?? null;
  const stages = surface?.read_stages ?? [];

  const [target, setTarget] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [stageIdx, setStageIdx] = useState(0);
  const [review, setReview] = useState<Review | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [writes, setWrites] = useState<Write[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);

  const busy = phase !== "idle";

  function onPickFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0];
    /* Cancel / empty change must not wipe a prior photo or file. */
    if (!next) return;
    setFile(next);
    setReview(null);
    setProposals([]);
    setFileUrl(null);
    /* Allow picking the same photo again after cancel/replace. */
    event.target.value = "";
  }

  useEffect(() => {
    if (!action || target) return;
    const ready = action.targets.filter((row) => row.ready);
    const preferred = ready.find((row) => row.doctype === PREFERRED_TARGET);
    setTarget((preferred ?? ready[0])?.doctype ?? null);
  }, [action, target]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        abortRef.current?.abort();
        abortRef.current = null;
        lock.current = false;
        onCloseRef.current();
        return;
      }
      if (event.key === "Tab" && panelRef.current) trapTab(event, panelRef.current);
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      abortRef.current?.abort();
      abortRef.current = null;
      lock.current = false;
    };
  }, []);

  useEffect(() => {
    if (!busy || stages.length === 0) return;
    setStageIdx(phase === "uploading" ? 0 : phase === "saving" ? stages.length - 1 : 1);
    const id = window.setInterval(() => {
      setStageIdx((prev) => {
        if (phase === "uploading") return 0;
        if (phase === "saving") return Math.max(stages.length - 1, 0);
        return Math.min(prev + 1, Math.max(stages.length - 2, 0));
      });
    }, 2800);
    return () => window.clearInterval(id);
  }, [busy, phase, stages.length]);

  function requestClose() {
    abortRef.current?.abort();
    abortRef.current = null;
    lock.current = false;
    onClose();
  }

  async function readFile() {
    if (lock.current || !action || !target || !file) return;
    lock.current = true;
    const ac = new AbortController();
    abortRef.current = ac;
    setReview(null);
    setProposals([]);
    setPhase("uploading");
    setStageIdx(0);
    let timedOut = false;
    const slow = window.setTimeout(() => {
      timedOut = true;
      ac.abort();
      lock.current = false;
      setPhase("idle");
      setReview({ ok: false, error_key: "idp.readSlow" });
    }, 100_000);
    try {
      const uploaded = await postFile(file, ac.signal);
      if (ac.signal.aborted) return;
      const url = String(uploaded.file_url || "");
      if (!url) throw new Error(t("idp.readFailed"));
      setFileUrl(url);
      setPhase("reading");
      const result = await postForm(
        METHOD.idpRun,
        {
          action: action.id,
          target_doctype: target,
          file_url: url,
          query: "",
        },
        ac.signal,
      );
      if (ac.signal.aborted || timedOut) return;
      setReview(result);
      setWrites(Array.isArray(result.writes) ? result.writes : []);
      setProposals(Array.isArray(result.proposals) ? cloneProposals(result.proposals) : []);
      setStageIdx(stages.length - 1);
    } catch (err) {
      if (ac.signal.aborted || timedOut) return;
      setReview({ ok: false, error_key: "idp.readFailed", detail: readableError(err).join(" ") });
    } finally {
      window.clearTimeout(slow);
      if (!ac.signal.aborted && !timedOut) {
        lock.current = false;
        setPhase("idle");
      }
      if (abortRef.current === ac) abortRef.current = null;
    }
  }

  async function saveDraft(submit = false) {
    if (lock.current || !action || !target || !fileUrl) return;
    if (!proposalsReady(proposals)) return;
    lock.current = true;
    const ac = new AbortController();
    abortRef.current = ac;
    setPhase("saving");
    try {
      const fills = Object.fromEntries(writes.map((row) => [row.field, row.value]));
      const result = await postForm(
        METHOD.idpSave,
        {
          action: action.id,
          target_doctype: target,
          file_url: fileUrl,
          query: "",
          fills: JSON.stringify(fills),
          proposals: JSON.stringify(proposals),
          submit: submit ? "1" : "",
        },
        ac.signal,
      );
      if (ac.signal.aborted) return;
      if (result.ok && result.route && !result.error_key) {
        setReview(result);
        onClose();
        nav(result.route);
        return;
      }
      // Keep the review cards; only stamp the save failure so the foot can show it.
      setReview((prev) => ({
        ...(prev || {}),
        ...result,
        ok: false,
        error_key: result.error_key || "idp.readFailed",
        detail: result.detail,
        lines: result.lines ?? prev?.lines,
        items: result.items ?? prev?.items,
        gaps: result.gaps ?? prev?.gaps,
        step: result.step || prev?.step || "review",
        can_save: prev?.can_save,
        can_submit: prev?.can_submit,
        save_key: prev?.save_key,
      }));
    } catch (err) {
      if (ac.signal.aborted) return;
      setReview((prev) => ({
        ...(prev || { ok: false }),
        ok: false,
        error_key: "idp.readFailed",
        detail: readableError(err).join(" "),
        step: prev?.step || "review",
      }));
    } finally {
      if (!ac.signal.aborted) {
        lock.current = false;
        setPhase("idle");
      }
      if (abortRef.current === ac) abortRef.current = null;
    }
  }

  const liveStages =
    busy && stages.length > 0
      ? stages.map((row, index) => ({
          ...row,
          status: index < stageIdx ? "done" : index === stageIdx ? "active" : "pending",
        }))
      : review?.stage_log ?? [];

  const reviewReady = proposalsReady(proposals);
  const canSave = Boolean(
    review && reviewReady && (review.can_delete || review.can_save || proposals.length > 0),
  );
  const canSubmit = Boolean(
    review && reviewReady && (review.can_submit || (canSave && proposals.length > 0 && !review.can_delete)),
  );
  const consentPending = proposals.some((row) => !row.confirmed);
  const fieldsPending = proposals.some(
    (row) => row.confirmed && row.required_fields.some((field) => !String(field.value || "").trim()),
  );
  const blockHint = !review
    ? null
    : !reviewReady
      ? consentPending
        ? "idp.propose.needConsent"
        : fieldsPending
          ? "idp.propose.needFields"
          : "idp.propose.needConsent"
      : review.gaps && review.gaps.length > 0
        ? "idp.blocked.gaps"
        : !canSave
          ? "idp.blocked.save"
          : null;

  const statusKey =
    phase === "uploading"
      ? "idp.stage.upload"
      : phase === "reading"
        ? "idp.reading"
        : phase === "saving"
          ? "idp.saving"
          : null;

  const readyTargets = action?.targets.filter((row) => row.ready) ?? [];

  return (
    <div className="idp-back" role="presentation">
      <div
        ref={panelRef}
        className={`idp-panel${busy ? " idp-busy" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={statusKey ? statusId : undefined}
        aria-busy={busy}
      >
        <div className="idp-head">
          <h2 id={titleId}>{t("idp.title")}</h2>
          <button ref={closeRef} type="button" className="btn ghost sm" onClick={requestClose}>
            {busy ? t("idp.cancel") : t("idp.close")}
          </button>
        </div>

        {busy ? (
          <div className="idp-progress" aria-hidden="true">
            <span className="idp-progress-bar" />
          </div>
        ) : null}

        <div className="idp-body">
          {res.error ? <p className="idp-err">{readableError(res.error).join(" ")}</p> : null}
          {!surface && res.isLoading ? <p className="idp-hint">{t("idp.loading")}</p> : null}
          {surface && !action ? <p className="idp-hint">{t("idp.empty")}</p> : null}
          {action && !action.runnable ? <p className="idp-hint">{t(action.pending_key)}</p> : null}

          {action?.runnable && !review ? (
            <div className="idp-form">
              <p className="idp-kicker">{t("idp.pick")}</p>
              <div className="idp-targets" role="group" aria-label={t("idp.pick")}>
                {readyTargets.map((row) => (
                  <button
                    key={row.doctype}
                    type="button"
                    className="btn ghost sm"
                    aria-pressed={target === row.doctype}
                    disabled={busy}
                    onClick={() => setTarget(row.doctype)}
                  >
                    {t(row.label_key)}
                  </button>
                ))}
              </div>

              {showCamera ? (
                <>
                  <div
                    className={`idp-sources${file ? " has-file" : ""}`}
                    role="group"
                    aria-label={t("idp.sources")}
                  >
                    <label className={`idp-drop${file ? " has-file" : ""}`}>
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        disabled={busy}
                        onChange={onPickFile}
                      />
                      <span className="idp-drop-title">{t("idp.camera")}</span>
                      <span className="idp-drop-hint">{t("idp.cameraHint")}</span>
                    </label>
                    <label className={`idp-drop${file ? " has-file" : ""}`}>
                      <input
                        type="file"
                        accept={fileAccept(surface?.accept)}
                        disabled={busy}
                        onChange={onPickFile}
                      />
                      <span className="idp-drop-title">{t("idp.drop")}</span>
                      <span className="idp-drop-hint">{t("idp.dropHint")}</span>
                    </label>
                  </div>
                  {file ? (
                    <p className="idp-picked" role="status" aria-live="polite" title={file.name}>
                      {file.name}
                    </p>
                  ) : null}
                </>
              ) : (
                <label className={`idp-drop${file ? " has-file" : ""}`}>
                  <input
                    type="file"
                    accept={fileAccept(surface?.accept)}
                    disabled={busy}
                    onChange={onPickFile}
                  />
                  <span className="idp-drop-title">{file ? file.name : t("idp.drop")}</span>
                  <span className="idp-drop-hint">{t("idp.dropHint")}</span>
                </label>
              )}

              <button
                type="button"
                className="btn idp-run"
                disabled={busy || !target || !file}
                onClick={() => void readFile()}
              >
                {busy ? t("idp.reading") : t("idp.read")}
              </button>
            </div>
          ) : null}

          {review && !busy ? (
            <div className="idp-job">
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => {
                  setReview(null);
                  setProposals([]);
                  setWrites([]);
                  setFile(null);
                  setFileUrl(null);
                }}
              >
                {t("idp.again")}
              </button>
            </div>
          ) : null}

          {statusKey ? (
            <p id={statusId} className="idp-status" role="status" aria-live="polite">
              {t(statusKey)}
            </p>
          ) : null}

          {liveStages.length > 0 ? <StageList stages={liveStages} /> : null}

          {review ? (
            <ReviewBlock
              review={review}
              writes={writes}
              proposals={proposals}
              onWrite={(field, value) =>
                setWrites((rows) => rows.map((row) => (row.field === field ? { ...row, value } : row)))
              }
              onProposal={setProposals}
              onOpen={nav}
            />
          ) : null}
        </div>

        {review ? (
          <div className="idp-foot">
            {review.error_key && !review.ok ? (
              <p className="idp-err" role="alert">
                {t(review.error_key)}
                {review.detail ? ` — ${review.detail}` : ""}
              </p>
            ) : null}
            {proposals.length > 0 && !(review.error_key && !review.ok) ? (
              <p className="idp-hint">{t("idp.propose.onSave")}</p>
            ) : null}
            {!canSave && review.detail && review.ok !== false ? <p className="idp-hint">{review.detail}</p> : null}
            {blockHint && !canSave && !review.detail ? <p className="idp-hint">{t(blockHint)}</p> : null}
            <div className="idp-jobs">
              <button type="button" className="btn" disabled={busy || !canSave} onClick={() => void saveDraft(false)}>
                {phase === "saving" ? t("idp.saving") : t(review.save_key || "idp.save")}
              </button>
              {canSubmit && !review.can_delete ? (
                <button type="button" className="btn ghost" disabled={busy || !canSave} onClick={() => void saveDraft(true)}>
                  {t("idp.submit")}
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function StageList({ stages }: { stages: Stage[] }) {
  /* Status text above is aria-live; this list is visual only so the 2.8s
     client ticker does not spam screen readers with fake stage changes. */
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

function ReviewBlock({
  review,
  writes,
  proposals,
  onWrite,
  onProposal,
  onOpen,
}: {
  review: Review;
  writes: Write[];
  proposals: Proposal[];
  onWrite: (field: string, value: string) => void;
  onProposal: (rows: Proposal[] | ((prev: Proposal[]) => Proposal[])) => void;
  onOpen: (route: string) => void;
}) {
  return (
    <div className="idp-job" role="status" aria-live="polite">
      {review.error_key ? <p>{t(review.error_key)}</p> : null}
      {review.detail ? <p>{review.detail}</p> : null}
      {review.step === "saved" ? <p>{t("idp.saved")}</p> : null}
      {review.step === "submitted" ? <p>{t("idp.submittedNow")}</p> : null}
      {review.route && review.error_key && review.name ? (
        <button type="button" className="btn ghost" onClick={() => onOpen(review.route as string)}>
          {review.name}
        </button>
      ) : null}
      {review.used_llm ? <p className="idp-kicker">{t("idp.modelUsed")}</p> : null}
      {review.lines && review.lines.length > 0 ? (
        <>
          <p className="idp-kicker">{t("idp.readTitle")}</p>
          <div className="idp-read">
            {review.lines.map((line) => (
              <div key={line.label_key}>
                <span>{fieldLabel(line.label_key)}</span>
                <b>{line.value}</b>
              </div>
            ))}
          </div>
        </>
      ) : null}
      {review.items && review.items.length > 0 ? (
        <ul className="idp-notes">
          {review.items.map((item) => (
            <li key={item.label}>{item.label}</li>
          ))}
        </ul>
      ) : null}
      {review.gaps && review.gaps.length > 0 ? (
        <>
          <p className="idp-kicker">{t("idp.still")}</p>
          <ul className="idp-notes">
            {review.gaps.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
        </>
      ) : null}
      {proposals.length > 0 ? (
        <>
          <p className="idp-kicker">{t("idp.propose.title")}</p>
          {proposals.map((row) => (
            <ProposalCard
              key={row.key}
              proposal={row}
              onChange={(next) =>
                onProposal((rows) => rows.map((item) => (item.key === next.key ? next : item)))
              }
            />
          ))}
        </>
      ) : null}
      {review.step === "review" && writes.length > 0 ? (
        <>
          <p className="idp-kicker">{t("idp.write")}</p>
          {writes.map((row) => {
            const fieldId = `idp-write-${row.field}`;
            return (
              <label className="idp-file" key={row.field} htmlFor={fieldId}>
                {fieldLabel(row.label_key)}
                {row.options && row.options.length > 0 ? (
                  <select
                    id={fieldId}
                    value={row.value}
                    onChange={(event) => onWrite(row.field, event.target.value)}
                  >
                    <option value="" />
                    {row.options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    id={fieldId}
                    type={row.field.endsWith("date") ? "date" : "text"}
                    value={row.value}
                    onChange={(event) => onWrite(row.field, event.target.value)}
                  />
                )}
              </label>
            );
          })}
        </>
      ) : null}
    </div>
  );
}

function RequiredMark() {
  return (
    <span className="req" aria-hidden="true">
      *
    </span>
  );
}

function FieldLabel({ labelKey, required }: { labelKey: string; required?: boolean }) {
  return (
    <span className="idp-label-text">
      {fieldLabel(labelKey)}
      {required ? <RequiredMark /> : null}
    </span>
  );
}

function ProposalCard({
  proposal,
  onChange,
}: {
  proposal: Proposal;
  onChange: (row: Proposal) => void;
}) {
  const consentId = `idp-consent-${proposal.key}`;
  function patchField(bucket: "required_fields" | "optional_fields", field: string, value: string) {
    onChange({
      ...proposal,
      [bucket]: proposal[bucket].map((row) => (row.field === field ? { ...row, value } : row)),
    });
  }
  return (
    <fieldset className="idp-propose">
      <legend>{proposal.title}</legend>
      <label className="idp-consent" htmlFor={consentId}>
        <input
          id={consentId}
          type="checkbox"
          checked={proposal.confirmed}
          onChange={(event) => onChange({ ...proposal, confirmed: event.target.checked })}
        />
        {t(proposal.consent_label_key)}
      </label>
      {[...proposal.required_fields, ...proposal.optional_fields].map((row) => {
        const fieldId = `idp-prop-${proposal.key}-${row.field}`;
        const required = proposal.required_fields.some((item) => item.field === row.field);
        return (
          <label className="idp-file" key={row.field} htmlFor={fieldId}>
            <FieldLabel labelKey={row.label_key} required={required} />
            {row.options && row.options.length > 0 ? (
              <select
                id={fieldId}
                value={row.value}
                required={required}
                onChange={(event) =>
                  patchField(required ? "required_fields" : "optional_fields", row.field, event.target.value)
                }
              >
                <option value="" />
                {row.options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={fieldId}
                type="text"
                value={row.value}
                required={required}
                onChange={(event) =>
                  patchField(required ? "required_fields" : "optional_fields", row.field, event.target.value)
                }
              />
            )}
          </label>
        );
      })}
    </fieldset>
  );
}

function cloneProposals(rows: Proposal[]): Proposal[] {
  return rows.map((row) => ({
    ...row,
    confirmed: Boolean(row.confirmed),
    required_fields: (row.required_fields || []).map((field) => {
      const blank = !String(field.value || "").trim();
      const typeDefault =
        blank && (field.field === "supplier_type" || field.field === "customer_type") ? "Company" : "";
      return { ...field, value: field.value || typeDefault };
    }),
    optional_fields: (row.optional_fields || []).map((field) => ({ ...field, value: field.value || "" })),
  }));
}

function proposalsReady(rows: Proposal[]): boolean {
  if (rows.length === 0) return true;
  return rows.every(
    (row) =>
      row.confirmed &&
      row.required_fields.every((field) => String(field.value || "").trim().length > 0),
  );
}

function fieldLabel(key: string): string {
  const label = t(key);
  if (label !== key) return label;
  const raw = key.startsWith("idp.field.") ? key.slice("idp.field.".length) : key;
  return raw.replaceAll("_", " ");
}

function trapTab(event: KeyboardEvent, root: HTMLElement) {
  const nodes = root.querySelectorAll<HTMLElement>("button, [href], input, select, textarea");
  const list = [...nodes].filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);
  if (list.length === 0) return;
  const first = list[0];
  const last = list[list.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && (active === first || !root.contains(active))) {
    event.preventDefault();
    last.focus();
    return;
  }
  if (!event.shiftKey && (active === last || !root.contains(active))) {
    event.preventDefault();
    first.focus();
  }
}

/** Extensions from the surface plus MIME types Android/iOS WebViews honour. */
function fileAccept(exts: string[] | undefined): string {
  const list = exts?.length ? exts : [".pdf", ".png", ".jpg", ".jpeg"];
  return [...list, "application/pdf", "image/*"].join(",");
}

async function postFile(file: File, signal: AbortSignal): Promise<Record<string, unknown>> {
  const body = new FormData();
  body.append("file", file);
  const res = await apiFetch(`/api/method/${METHOD.idpUpload}`, {
    method: "POST",
    headers: { "X-Frappe-CSRF-Token": window.csrf_token || "" },
    body,
    signal,
  });
  return readMessage(res);
}

async function postForm(
  method: string,
  args: Record<string, string>,
  signal: AbortSignal,
): Promise<Review> {
  const res = await apiFetch(`/api/method/${method}`, {
    method: "POST",
    headers: {
      "X-Frappe-CSRF-Token": window.csrf_token || "",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams(args),
    signal,
  });
  return readMessage(res) as Promise<Review>;
}

async function readMessage(res: Response): Promise<Record<string, unknown>> {
  const data = await res.json();
  if (!res.ok || data.exc) {
    throw new Error(typeof data.message === "string" ? data.message : t("idp.readFailed"));
  }
  return (data.message ?? data) as Record<string, unknown>;
}
