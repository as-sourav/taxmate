/**
 * Crop the captured photo before OCR prep.
 * Callers: CaptureDesk after Take photo / Choose image.
 * Touch: drag the frame or corners (≥44px hit). Keyboard: Escape cancels.
 */

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { t } from "../../../i18n/strings";
import { defaultCropRect, type CropRect } from "./prepareImage";

type Props = {
  /** Object URL of the source image (parent owns revoke). */
  src: string;
  onConfirm: (crop: CropRect | null) => void;
  onCancel: () => void;
  busy?: boolean;
};

type DragMode =
  | { kind: "move"; ox: number; oy: number; start: CropRect }
  | { kind: "resize"; corner: Corner; start: CropRect }
  | null;

type Corner = "nw" | "ne" | "sw" | "se";

const MIN = 0.12;

export function CropFrame({ src, onConfirm, onCancel, busy }: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [crop, setCrop] = useState<CropRect>(defaultCropRect);
  const [drag, setDrag] = useState<DragMode>(null);
  const [layoutTick, setLayoutTick] = useState(0);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };
    const onResize = () => setLayoutTick((n) => n + 1);
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [onCancel]);

  /** Map pointer into image pixels (0–1), accounting for object-fit:contain letterbox. */
  function clientToNorm(clientX: number, clientY: number): { x: number; y: number } | null {
    const el = stageRef.current;
    const img = el?.querySelector("img");
    if (!el || !img) return null;
    const stage = el.getBoundingClientRect();
    if (stage.width <= 0 || stage.height <= 0) return null;
    const nw = img.naturalWidth || 1;
    const nh = img.naturalHeight || 1;
    const scale = Math.min(stage.width / nw, stage.height / nh);
    const dispW = nw * scale;
    const dispH = nh * scale;
    const offsetX = (stage.width - dispW) / 2;
    const offsetY = (stage.height - dispH) / 2;
    const x = (clientX - stage.left - offsetX) / dispW;
    const y = (clientY - stage.top - offsetY) / dispH;
    return {
      x: Math.min(1, Math.max(0, x)),
      y: Math.min(1, Math.max(0, y)),
    };
  }

  function cropBoxStyle(cropRect: CropRect): CSSProperties {
    const el = stageRef.current;
    const img = el?.querySelector("img");
    if (!el || !img || !img.naturalWidth) {
      return {
        left: `${cropRect.x * 100}%`,
        top: `${cropRect.y * 100}%`,
        width: `${cropRect.w * 100}%`,
        height: `${cropRect.h * 100}%`,
      };
    }
    const stage = el.getBoundingClientRect();
    const nw = img.naturalWidth;
    const nh = img.naturalHeight;
    const scale = Math.min(stage.width / nw, stage.height / nh);
    const dispW = nw * scale;
    const dispH = nh * scale;
    const offsetX = (stage.width - dispW) / 2;
    const offsetY = (stage.height - dispH) / 2;
    return {
      left: `${offsetX + cropRect.x * dispW}px`,
      top: `${offsetY + cropRect.y * dispH}px`,
      width: `${cropRect.w * dispW}px`,
      height: `${cropRect.h * dispH}px`,
    };
  }

  function onPointerDownMove(event: ReactPointerEvent) {
    if (busy) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const p = clientToNorm(event.clientX, event.clientY);
    if (!p) return;
    setDrag({ kind: "move", ox: p.x - crop.x, oy: p.y - crop.y, start: crop });
  }

  function onPointerDownCorner(corner: Corner, event: ReactPointerEvent) {
    if (busy) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ kind: "resize", corner, start: crop });
  }

  function onPointerMove(event: ReactPointerEvent) {
    if (!drag) return;
    const p = clientToNorm(event.clientX, event.clientY);
    if (!p) return;
    if (drag.kind === "move") {
      const w = drag.start.w;
      const h = drag.start.h;
      setCrop({
        x: Math.min(1 - w, Math.max(0, p.x - drag.ox)),
        y: Math.min(1 - h, Math.max(0, p.y - drag.oy)),
        w,
        h,
      });
      return;
    }
    const s = drag.start;
    let { x, y, w, h } = s;
    if (drag.corner.includes("w")) {
      const right = s.x + s.w;
      x = Math.min(right - MIN, Math.max(0, p.x));
      w = right - x;
    }
    if (drag.corner.includes("e")) {
      w = Math.min(1 - s.x, Math.max(MIN, p.x - s.x));
    }
    if (drag.corner.includes("n")) {
      const bottom = s.y + s.h;
      y = Math.min(bottom - MIN, Math.max(0, p.y));
      h = bottom - y;
    }
    if (drag.corner.includes("s")) {
      h = Math.min(1 - s.y, Math.max(MIN, p.y - s.y));
    }
    setCrop({ x, y, w, h });
  }

  function onPointerUp() {
    setDrag(null);
  }

  void layoutTick;

  return (
    <div className="idp-crop" role="group" aria-label={t("idp.crop.title")}>
      <p className="idp-kicker">{t("idp.crop.title")}</p>
      <p className="idp-hint">{t("idp.crop.hint")}</p>
      <div
        ref={stageRef}
        className="idp-crop-stage"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <img
          src={src}
          alt=""
          className="idp-crop-img"
          draggable={false}
          onLoad={() => setLayoutTick((n) => n + 1)}
        />
        <div
          className="idp-crop-box"
          style={cropBoxStyle(crop)}
          onPointerDown={onPointerDownMove}
          role="presentation"
        >
          {(["nw", "ne", "sw", "se"] as Corner[]).map((corner) => (
            <button
              key={corner}
              type="button"
              className={`idp-crop-handle idp-crop-handle-${corner}`}
              aria-label={t("idp.crop.handle")}
              disabled={busy}
              onPointerDown={(event) => onPointerDownCorner(corner, event)}
            />
          ))}
        </div>
      </div>
      <div className="idp-crop-actions">
        <button type="button" className="btn ghost sm" disabled={busy} onClick={onCancel}>
          {t("idp.crop.retake")}
        </button>
        <button
          type="button"
          className="btn ghost sm"
          disabled={busy}
          onClick={() => onConfirm(null)}
        >
          {t("idp.crop.full")}
        </button>
        <button
          type="button"
          className="btn sm"
          disabled={busy}
          onClick={() => onConfirm(crop)}
        >
          {t("idp.crop.use")}
        </button>
      </div>
    </div>
  );
}
