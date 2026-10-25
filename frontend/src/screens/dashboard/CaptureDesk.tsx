/**
 * Scan panel — create a draft from a photo or file via IDP.
 * On mobile/native: Take photo (capture) or Choose file. Desktop: file only.
 * One job only: create. Dialog stays open until Close/Cancel; that aborts work.
 */

import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useFrappeGetCall } from "frappe-react-sdk";

import { useIsMobileShell } from "../../components/MobileNav";
import { METHOD, readableError } from "../../lib/frappe";
import { t } from "../../i18n/strings";
import { getLang } from "../../lib/i18n";
import { apiFetch } from "../../mobile/http";
import { isNative } from "../../mobile/platform";
import {
  isImageFile,
  isPdfFile,
  prepareScanImage,
  type CropRect,
} from "./capture/prepareImage";
import { cameraAvailable, takePhoto } from "./capture/nativeCamera";
import { CropFrame } from "./capture/CropFrame";
import { ScanProgress } from "./capture/ScanProgress";
import { ScanSteps, type ScanStepId } from "./capture/ScanSteps";

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
  detail_key?: string | null;
  detail?: string | null;
  lines?: { label_key: string; value: string }[];
  items?: { label: string }[];
  gaps?: string[];
  writes?: Write[];
  proposals?: Proposal[];
  stage_log?: Stage[];
  stage_timings?: Record<string, number>;
  status?: string;
  review?: Review;
  field_confidence?: Record<string, { confidence?: number; ok?: boolean; flag?: string | null }>;
  can_save?: boolean;
  can_submit?: boolean;
  can_delete?: boolean;
  used_llm?: boolean;
  save_key?: string | null;
  scan_id?: string | null;
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
        className="iconbtn bordered"
        aria-label={t("idp.open")}
        onClick={() => setOpen(true)}
      >
        <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
          <path d="M3.2 6.2V3.4h2.8M14.8 6.2V3.4h-2.8M3.2 11.8v2.8h2.8M14.8 11.8v2.8h-2.8M2.8 9h12.4" />
        </svg>
      </button>
      {/* Portal to body — topbar/sticky ancestors clip position:fixed and kill scroll. */}
      {open
        ? createPortal(
            <CapturePanel
              onClose={() => {
                setOpen(false);
                openRef.current?.focus();
              }}
            />,
            document.body,
          )
        : null}
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
  const [scanId, setScanId] = useState<string | null>(null);
  const [writes, setWrites] = useState<Write[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  /** Raw image awaiting crop; object URL for CropFrame. */
  const [draft, setDraft] = useState<{ file: File; url: string } | null>(null);
  const [prepBusy, setPrepBusy] = useState(false);

  const busy = phase !== "idle" || prepBusy;

  function clearDraft() {
    setDraft((prev) => {
      if (prev?.url) URL.revokeObjectURL(prev.url);
      return null;
    });
  }

  async function applyPrepared(source: File, crop: CropRect | null) {
    setPrepBusy(true);
    try {
      const prepared = await prepareScanImage(source, { crop });
      if ("error_key" in prepared) {
        setFile(null);
        setFileUrl(null);
        setProposals([]);
        setReview({ ok: false, error_key: prepared.error_key, can_save: false });
        clearDraft();
        return;
      }
      setFile(prepared.file);
      setReview(null);
      setProposals([]);
      setFileUrl(null);
      setScanId(null);
      clearDraft();
    } finally {
      setPrepBusy(false);
    }
  }

  async function beginImageDraft(next: File) {
    if (isPdfFile(next) || !isImageFile(next)) {
      await applyPrepared(next, null);
      return;
    }
    clearDraft();
    setFile(null);
    setReview(null);
    setProposals([]);
    setFileUrl(null);
    setScanId(null);
    setDraft({ file: next, url: URL.createObjectURL(next) });
  }

  async function onPickFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0];
    if (!next) return;
    event.target.value = "";
    await beginImageDraft(next);
  }

  async function onTakePhoto() {
    const shot = await takePhoto();
    if (!shot.ok) {
      setReview({ ok: false, error_key: shot.error_key, can_save: false });
      return;
    }
    await beginImageDraft(shot.file);
  }

  useEffect(() => {
    if (!action || target) return;
    const ready = action.targets.filter((row) => row.ready);
    const preferred = ready.find((row) => row.doctype === PREFERRED_TARGET);
    setTarget((preferred ?? ready[0])?.doctype ?? null);
  }, [action, target]);

  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (draftRef.current) {
          clearDraft();
          return;
        }
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
      if (draftRef.current?.url) URL.revokeObjectURL(draftRef.current.url);
    };
  }, []);

  function requestClose() {
    const id = scanId;
    abortRef.current?.abort();
    abortRef.current = null;
    lock.current = false;
    clearDraft();
    if (id) {
      void postForm(METHOD.idpCancelScan, { scan_id: id }).catch(() => undefined);
    }
    onClose();
  }

  async function pollScan(
    id: string,
    doctype: string,
    signal: AbortSignal,
  ): Promise<Review | null> {
    const started = Date.now();
    const maxMs = 10 * 60 * 1000;
    while (!signal.aborted) {
      if (Date.now() - started > maxMs) {
        await postForm(METHOD.idpCancelScan, { scan_id: id }).catch(() => undefined);
        return { ok: false, error_key: "idp.readSlow", can_save: false, scan_id: id };
      }
      const status = await postForm(
        METHOD.idpGetScan,
        { scan_id: id, target_doctype: doctype },
        signal,
      );
      if (signal.aborted) return null;
      const st = String(status.status || "");
      // Surface stages: upload, ocr, parties, items, review — map server status coarsely.
      if (st === "Extracting" || st === "Reading") setStageIdx(Math.min(1, Math.max(stages.length - 1, 0)));
      else if (st === "Ready" || st === "Review") setStageIdx(Math.max(stages.length - 1, 0));
      if (status.status === "Ready" || status.status === "Review") {
        if (status.review) return status.review as Review;
        return {
          ok: false,
          error_key: String(status.error_key || "idp.readFailed"),
          detail: typeof status.detail === "string" ? status.detail : null,
          can_save: false,
          scan_id: id,
        };
      }
      if (status.status === "Failed" || status.status === "Cancelled") {
        return {
          ok: false,
          error_key: String(status.error_key || (status.status === "Cancelled" ? "cancelled" : "idp.readFailed")),
          detail: typeof status.detail === "string" ? status.detail : null,
          can_save: false,
          scan_id: id,
        };
      }
      if (status.ok === false && status.error_key && status.status !== "Extracting" && status.status !== "Reading") {
        return {
          ok: false,
          error_key: String(status.error_key),
          detail: typeof status.detail === "string" ? status.detail : null,
          can_save: false,
          scan_id: id,
        };
      }
      await new Promise((r) => window.setTimeout(r, 1200));
    }
    return null;
  }

  async function readFile() {
    if (lock.current || !action || !target || !file) return;
    lock.current = true;
    const ac = new AbortController();
    abortRef.current = ac;
    setReview(null);
    setProposals([]);
    setScanId(null);
    setPhase("uploading");
    setStageIdx(0);
    try {
      const uploaded = await postFile(file, ac.signal);
      if (ac.signal.aborted) return;
      if (uploaded.success === false || uploaded.error_key) {
        setReview({
          ok: false,
          error_key: String(uploaded.error_key || "idp.readFailed"),
          detail_key: uploaded.detail_key ? String(uploaded.detail_key) : null,
          detail: uploadDetail(uploaded),
          can_save: false,
        });
        return;
      }
      const url = String(uploaded.file_url || "");
      if (!url) {
        setReview({ ok: false, error_key: "idp.readFailed", detail_key: "idp.readHint", can_save: false });
        return;
      }
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
      if (ac.signal.aborted) return;
      if (result.ok === false && result.error_key) {
        setReview({
          ...result,
          detail: distinctDetail(result),
          can_save: false,
        });
        setWrites([]);
        setProposals([]);
        setStageIdx(stages.length - 1);
        return;
      }
      const id = result.scan_id ? String(result.scan_id) : "";
      setScanId(id || null);
      let reviewResult = result as Review;
      if (result.step === "processing" && id) {
        const polled = await pollScan(id, target, ac.signal);
        if (ac.signal.aborted) return;
        if (!polled) {
          setReview({ ok: false, error_key: "idp.readFailed", can_save: false });
          return;
        }
        reviewResult = polled;
      }
      setReview(reviewResult);
      if (reviewResult.scan_id) setScanId(String(reviewResult.scan_id));
      setWrites(Array.isArray(reviewResult.writes) ? reviewResult.writes : []);
      setProposals(Array.isArray(reviewResult.proposals) ? cloneProposals(reviewResult.proposals) : []);
      setStageIdx(stages.length - 1);
    } catch (err) {
      if (ac.signal.aborted) return;
      const detail = readableError(err).join(" ").trim();
      const useless =
        !detail ||
        detail === t("idp.readFailed") ||
        detail === "Something went wrong." ||
        detail === "Something went wrong";
      setReview({
        ok: false,
        error_key: "idp.readFailed",
        detail_key: "idp.readHint",
        detail: useless ? null : detail,
        can_save: false,
      });
    } finally {
      if (!ac.signal.aborted) {
        lock.current = false;
        setPhase("idle");
      }
      if (abortRef.current === ac) abortRef.current = null;
    }
  }

  async function saveDraft(submit = false) {
    if (lock.current || !action || !target || !fileUrl || !scanId) return;
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
          scan_id: scanId,
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
      // Caller: Save draft button. The file is already read; do not call that a read failure.
      setReview((prev) => ({
        ...(prev || {}),
        ...result,
        ok: false,
        error_key: result.error_key || "idp.propose.failed",
        detail: result.detail,
        lines: result.lines ?? prev?.lines,
        items: result.items ?? prev?.items,
        gaps: result.gaps ?? prev?.gaps,
        step: result.step || prev?.step || "review",
        can_save: prev?.can_save,
        can_submit: prev?.can_submit,
        save_key: prev?.save_key,
      }));
      requestAnimationFrame(() => {
        document.getElementById("idp-save-error")?.focus();
      });
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
  const cropping = Boolean(action?.runnable && !review && draft);
  const capturing = Boolean(action?.runnable && !review && !draft);
  const showReviewFoot = Boolean(
    review && (scanHasContent(review, proposals) || review.ok !== false),
  );
  const showReadFoot = Boolean(capturing && file && !busy);
  const scanStep: ScanStepId = cropping
    ? "frame"
    : review || phase === "saving"
      ? "review"
      : phase === "uploading" || phase === "reading" || file
        ? "read"
        : "capture";
  const panelMode = cropping ? "crop" : review ? "review" : "capture";
  const titleText = cropping ? t("idp.crop.title") : review ? t("idp.step.review") : t("idp.title");

  return (
    <div className="idp-back" role="presentation">
      <div
        ref={panelRef}
        className={`idp-panel idp-panel--${panelMode}${busy ? " idp-busy" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={statusKey ? statusId : undefined}
        aria-busy={busy}
      >
        <div className="idp-head">
          <div className="idp-head-text">
            <h2 id={titleId}>{titleText}</h2>
            {capturing ? <p className="idp-sub">{t("idp.sub")}</p> : null}
          </div>
          <button ref={closeRef} type="button" className="btn ghost sm" onClick={requestClose}>
            {busy ? t("idp.cancel") : t("idp.close")}
          </button>
        </div>

        {!cropping && !review ? (
          <ScanSteps current={scanStep} skipFrame={Boolean(file && isPdfFile(file))} />
        ) : null}

        {busy ? (
          <div className="idp-progress" aria-hidden="true">
            <span className="idp-progress-bar" />
          </div>
        ) : null}

        <div
          className={`idp-body${cropping ? " idp-body--crop" : ""}${showReadFoot || showReviewFoot ? " idp-body--foot" : ""}`}
        >
          {res.error ? <p className="idp-err">{readableError(res.error).join(" ")}</p> : null}
          {!surface && res.isLoading ? <p className="idp-hint">{t("idp.loading")}</p> : null}
          {surface && !action ? <p className="idp-hint">{t("idp.empty")}</p> : null}
          {action && !action.runnable ? <p className="idp-hint">{t(action.pending_key)}</p> : null}

          {cropping && draft ? (
            <CropFrame
              src={draft.url}
              busy={prepBusy}
              onCancel={() => {
                clearDraft();
                setReview(null);
              }}
              onConfirm={(crop) => {
                if (!draft) return;
                void applyPrepared(draft.file, crop);
              }}
            />
          ) : null}

          {capturing ? (
            <div className="idp-form">
              <section className="idp-section" aria-labelledby={`${titleId}-type`}>
                <div className="idp-section-head">
                  <span className="idp-section-num" aria-hidden="true">
                    1
                  </span>
                  <h3 id={`${titleId}-type`} className="idp-section-title">
                    {t("idp.pick")}
                  </h3>
                </div>
                <div className="idp-targets" role="group" aria-label={t("idp.pick")}>
                  {readyTargets.map((row) => (
                    <button
                      key={row.doctype}
                      type="button"
                      className="idp-chip"
                      aria-pressed={target === row.doctype}
                      disabled={busy}
                      onClick={() => setTarget(row.doctype)}
                    >
                      {t(row.label_key)}
                    </button>
                  ))}
                </div>
              </section>

              <section className="idp-section" aria-labelledby={`${titleId}-src`}>
                <div className="idp-section-head">
                  <span className="idp-section-num" aria-hidden="true">
                    2
                  </span>
                  <h3 id={`${titleId}-src`} className="idp-section-title">
                    {t("idp.sources")}
                  </h3>
                </div>

                {showCamera ? (
                  <>
                    <div
                      className={`idp-sources${file ? " has-file" : ""}`}
                      role="group"
                      aria-label={t("idp.sources")}
                    >
                      {cameraAvailable() ? (
                        <button
                          type="button"
                          className={`idp-drop${file ? " has-file" : ""}`}
                          disabled={busy}
                          onClick={() => void onTakePhoto()}
                        >
                          <span className="idp-drop-icon" aria-hidden="true">
                            <CameraIcon />
                          </span>
                          <span className="idp-drop-title">{t("idp.camera")}</span>
                          <span className="idp-drop-hint">{t("idp.cameraHint")}</span>
                        </button>
                      ) : (
                        <label className={`idp-drop${file ? " has-file" : ""}`}>
                          <input
                            type="file"
                            accept="image/*"
                            capture="environment"
                            disabled={busy}
                            onChange={(e) => void onPickFile(e)}
                          />
                          <span className="idp-drop-icon" aria-hidden="true">
                            <CameraIcon />
                          </span>
                          <span className="idp-drop-title">{t("idp.camera")}</span>
                          <span className="idp-drop-hint">{t("idp.cameraHint")}</span>
                        </label>
                      )}
                      <label className={`idp-drop${file ? " has-file" : ""}`}>
                        <input
                          type="file"
                          accept={fileAccept(surface?.accept)}
                          disabled={busy}
                          onChange={(e) => void onPickFile(e)}
                        />
                        <span className="idp-drop-icon" aria-hidden="true">
                          <FileIcon />
                        </span>
                        <span className="idp-drop-title">{t("idp.drop")}</span>
                        <span className="idp-drop-hint">{t("idp.dropHint")}</span>
                      </label>
                    </div>
                    {file ? (
                      <p className="idp-picked" role="status" aria-live="polite" title={file.name}>
                        <span className="idp-picked-label">{t("idp.fileLabel")}</span>
                        <span className="idp-picked-name">{file.name}</span>
                      </p>
                    ) : null}
                  </>
                ) : (
                  <label className={`idp-drop idp-drop--solo${file ? " has-file" : ""}`}>
                    <input
                      type="file"
                      accept={fileAccept(surface?.accept)}
                      disabled={busy}
                      onChange={(e) => void onPickFile(e)}
                    />
                    <span className="idp-drop-icon" aria-hidden="true">
                      <FileIcon />
                    </span>
                    <span className="idp-drop-title">{file ? file.name : t("idp.drop")}</span>
                    <span className="idp-drop-hint">{t("idp.dropHint")}</span>
                  </label>
                )}
              </section>

            </div>
          ) : null}

          {statusKey ? (
            <p id={statusId} className="idp-status" role="status" aria-live="polite">
              {t(statusKey)}
            </p>
          ) : null}

          {liveStages.length > 0 ? <ScanProgress stages={liveStages} /> : null}

          {review ? (
            <ReviewBlock
              review={review}
              writes={writes}
              proposals={proposals}
              busy={busy}
              onAgain={() => {
                setReview(null);
                setProposals([]);
                setWrites([]);
                setFile(null);
                setFileUrl(null);
                clearDraft();
              }}
              onWrite={(field, value) =>
                setWrites((rows) => rows.map((row) => (row.field === field ? { ...row, value } : row)))
              }
              onProposal={setProposals}
              onOpen={nav}
            />
          ) : null}
        </div>

        {showReadFoot ? (
          <div className="idp-foot idp-foot--capture">
            {!target ? <p className="idp-foot-hint">{t("idp.needType")}</p> : null}
            <button
              type="button"
              className="btn idp-run"
              disabled={busy || !target || !file}
              onClick={() => void readFile()}
            >
              {t("idp.read")}
            </button>
          </div>
        ) : null}

        {showReviewFoot && review ? (
          <div className="idp-foot">
            {review.error_key && !review.ok && scanHasContent(review, proposals) ? (
              <p id="idp-save-error" className="idp-err" role="alert" tabIndex={-1}>
                {formatScanError(review)}
              </p>
            ) : null}
            {!canSave && review.detail && review.ok !== false ? (
              <p className="idp-foot-hint">{review.detail}</p>
            ) : null}
            {blockHint && !canSave && !review.detail ? (
              <p className="idp-foot-hint">{t(blockHint)}</p>
            ) : null}
            <div className="idp-jobs">
              <button
                type="button"
                className="btn"
                disabled={busy || !canSave}
                onClick={() => void saveDraft(false)}
              >
                {phase === "saving" ? t("idp.saving") : t(review.save_key || "idp.save")}
              </button>
              {canSubmit && !review.can_delete ? (
                <button
                  type="button"
                  className="btn ghost"
                  disabled={busy || !canSave}
                  onClick={() => void saveDraft(true)}
                >
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

function CameraIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8.5h2.2l1.3-2h5l1.3 2H20v10H4z" />
      <circle cx="12" cy="13" r="3.2" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3.5h7l4 4V20.5H7z" />
      <path d="M14 3.5V8h4" />
      <path d="M10 12h6M10 15.5h6" />
    </svg>
  );
}

function ReviewBlock({
  review,
  writes,
  proposals,
  busy,
  onAgain,
  onWrite,
  onProposal,
  onOpen,
}: {
  review: Review;
  writes: Write[];
  proposals: Proposal[];
  busy: boolean;
  onAgain: () => void;
  onWrite: (field: string, value: string) => void;
  onProposal: (rows: Proposal[] | ((prev: Proposal[]) => Proposal[])) => void;
  onOpen: (route: string) => void;
}) {
  const hasContent = scanHasContent(review, proposals);
  const done = review.step === "saved" || review.step === "submitted";

  return (
    <div className="idp-review" role="status" aria-live="polite">
      <div className="idp-review-toolbar">
        {done ? (
          <span className={`idp-badge${review.step === "submitted" ? " idp-badge--ok" : ""}`}>
            {review.step === "submitted" ? t("idp.submittedNow") : t("idp.saved")}
          </span>
        ) : hasContent ? (
          <span className="idp-badge">{t("idp.step.review")}</span>
        ) : null}
        {!busy ? (
          <button type="button" className="idp-link" onClick={onAgain}>
            {t("idp.again")}
          </button>
        ) : null}
      </div>

      {review.error_key && !review.ok && !hasContent ? (
        <p className="idp-err idp-err--block" role="alert">
          {formatScanError(review)}
        </p>
      ) : null}

      {review.route && review.error_key && review.name ? (
        <button type="button" className="btn ghost sm" onClick={() => onOpen(review.route as string)}>
          {review.name}
        </button>
      ) : null}

      {review.lines && review.lines.length > 0 ? (
        <section className="idp-card" aria-label={t("idp.readTitle")}>
          <header className="idp-card-head">
            <h3 className="idp-card-title">{t("idp.readTitle")}</h3>
          </header>
          <dl className="idp-kv">
            {review.lines.map((line) => (
              <div className="idp-kv-row" key={line.label_key}>
                <dt>{fieldLabel(line.label_key)}</dt>
                <dd>{line.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {review.items && review.items.length > 0 ? (
        <section className="idp-card" aria-label={t("idp.stage.items")}>
          <header className="idp-card-head">
            <h3 className="idp-card-title">{t("idp.stage.items")}</h3>
            <span className="idp-card-meta">{review.items.length}</span>
          </header>
          <ul className="idp-line-items">
            {review.items.map((item) => (
              <li key={item.label}>{item.label}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {review.gaps && review.gaps.length > 0 ? (
        <section className="idp-callout idp-callout--warn" aria-label={t("idp.still")}>
          <p className="idp-callout-title">{t("idp.still")}</p>
          <ul className="idp-callout-list">
            {review.gaps.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {proposals.length > 0 ? (
        <section className="idp-card" aria-label={t("idp.propose.title")}>
          <header className="idp-card-head">
            <h3 className="idp-card-title">{t("idp.propose.title")}</h3>
            <span className="idp-card-meta">{t("idp.propose.onSave")}</span>
          </header>
          <div className="idp-propose-stack">
            {proposals.map((row) => (
              <ProposalCard
                key={row.key}
                proposal={row}
                onChange={(next) =>
                  onProposal((rows) => rows.map((item) => (item.key === next.key ? next : item)))
                }
              />
            ))}
          </div>
        </section>
      ) : null}

      {review.step === "review" && writes.length > 0 ? (
        <section className="idp-card" aria-label={t("idp.write")}>
          <header className="idp-card-head">
            <h3 className="idp-card-title">{t("idp.write")}</h3>
          </header>
          <div className="idp-fields">
            {writes.map((row) => {
              const fieldId = `idp-write-${row.field}`;
              return (
                <label className="idp-field" key={row.field} htmlFor={fieldId}>
                  <span className="idp-field-label">{fieldLabel(row.label_key)}</span>
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
          </div>
        </section>
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
      <legend className="idp-propose-title">{proposal.title}</legend>
      <label className="idp-consent" htmlFor={consentId}>
        <input
          id={consentId}
          type="checkbox"
          checked={proposal.confirmed}
          onChange={(event) => onChange({ ...proposal, confirmed: event.target.checked })}
        />
        <span>{proposal.doctype === "UOM" ? unitConsent() : t(proposal.consent_label_key)}</span>
      </label>
      {proposal.confirmed ? (
        <div className="idp-fields">
          {[...proposal.required_fields, ...proposal.optional_fields].map((row) => {
            const fieldId = `idp-prop-${proposal.key}-${row.field}`;
            const required = proposal.required_fields.some((item) => item.field === row.field);
            return (
              <label className="idp-field" key={row.field} htmlFor={fieldId}>
                <span className="idp-field-label">
                  <FieldLabel labelKey={row.label_key} required={required} />
                </span>
                {row.options && row.options.length > 0 ? (
                  <select
                    id={fieldId}
                    value={row.value}
                    required={required}
                    onChange={(event) =>
                      patchField(
                        required ? "required_fields" : "optional_fields",
                        row.field,
                        event.target.value,
                      )
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
                      patchField(
                        required ? "required_fields" : "optional_fields",
                        row.field,
                        event.target.value,
                      )
                    }
                  />
                )}
              </label>
            );
          })}
        </div>
      ) : null}
    </fieldset>
  );
}

function cloneProposals(rows: Proposal[]): Proposal[] {
  return rows.map((row) => {
    const required_fields = (row.required_fields || []).map((field) => {
      const blank = !String(field.value || "").trim();
      const typeDefault =
        blank && (field.field === "supplier_type" || field.field === "customer_type") ? "Company" : "";
      return { ...field, value: field.value || typeDefault };
    });
    const filled = required_fields.every((field) => String(field.value || "").trim().length > 0);
    return {
      ...row,
      confirmed: Boolean(row.confirmed) || filled,
      required_fields,
      optional_fields: (row.optional_fields || []).map((field) => ({ ...field, value: field.value || "" })),
    };
  });
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
  return [...list, "application/pdf", "image/jpeg", "image/png", "image/webp", "image/*"].join(",");
}

/** Normalize camera quirks client-side before upload; reject HEIC/empty/huge early. */
function scanHasContent(review: Review, proposals: Proposal[]): boolean {
  return Boolean(
    (review.lines && review.lines.length > 0) ||
      (review.items && review.items.length > 0) ||
      (review.writes && review.writes.length > 0) ||
      proposals.length > 0,
  );
}

/** One user-facing line; never repeats the same sentence twice. */
function unitConsent(): string {
  return getLang() === "ar" ? "إنشاء وحدة القياس هذه؟" : "Create this unit?";
}

function plainDetail(detail: string): string {
  const text = detail
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (/entered multiple times/i.test(text)) {
    return "The same item is on more than one line. Check the item and the unit on each row.";
  }
  return text;
}

function formatScanError(review: Review): string {
  const detail = plainDetail((review.detail || "").trim());
  // The file was read. Saying it could not be read hides the real save failure.
  if (detail && /this draft was not saved/i.test(detail)) return detail;
  if (detail && review.error_key === "idp.readFailed" && /permission denied/i.test(detail)) {
    return "This draft was not saved. A supplier, customer, or item on it belongs to another company. Save the draft again.";
  }
  const head = review.error_key ? t(review.error_key) : "";
  const hint = review.detail_key ? t(review.detail_key) : "";
  const parts: string[] = [];
  if (head) parts.push(head);
  for (const part of [hint, detail]) {
    if (part && !parts.includes(part)) parts.push(part);
  }
  return parts.join(" — ") || t("idp.readFailed");
}

function distinctDetail(review: Review): string | null {
  const detail = (review.detail || "").trim();
  if (!detail) return null;
  if (review.error_key && detail === t(review.error_key)) return null;
  if (review.detail_key && detail === t(review.detail_key)) return null;
  return detail;
}

function uploadDetail(uploaded: Record<string, unknown>): string | null {
  const raw = uploaded.detail;
  if (typeof raw !== "string") return null;
  const detail = raw.trim();
  if (!detail) return null;
  const key = uploaded.error_key ? t(String(uploaded.error_key)) : t("idp.readFailed");
  return detail === key ? null : detail;
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
  signal?: AbortSignal,
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
  /* Callers: postFile / postForm. Soft IDP errors use error_key; HTTP failures throw. */
  const data = await res.json();
  const message = data.message ?? data;
  if (!res.ok || data.exc) {
    if (
      message &&
      typeof message === "object" &&
      !Array.isArray(message) &&
      ("error_key" in message || "success" in message)
    ) {
      return message as Record<string, unknown>;
    }
    const lines = readableError(data).join(" ").trim();
    throw new Error(lines || t("idp.readFailed"));
  }
  if (message && typeof message === "object" && !Array.isArray(message)) {
    return message as Record<string, unknown>;
  }
  return (data as Record<string, unknown>) ?? {};
}
