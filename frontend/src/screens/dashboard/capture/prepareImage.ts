/** Decode → optional crop → EXIF-correct → mild contrast → downscale → JPEG → blur gate.
 * Callers: CaptureDesk after CropFrame confirm, or PDF skip-crop path.
 */

const LONG_EDGE = 2400;
const JPEG_QUALITY = 0.85;
const MIN_EDGE = 480;
const MAX_BYTES = 25 * 1024 * 1024;
/** Conservative blur gate; server still re-checks. */
const MIN_SHARPNESS = 2.5;

/** Normalized crop in image space (0–1). */
export type CropRect = { x: number; y: number; w: number; h: number };

export type PrepareResult = { file: File } | { error_key: string };

export type PrepareOptions = {
  /** When set, only that region is kept (after orientation). */
  crop?: CropRect | null;
};

export function isPdfFile(file: File): boolean {
  const name = (file.name || "").toLowerCase();
  const type = (file.type || "").toLowerCase();
  return type === "application/pdf" || name.endsWith(".pdf");
}

export function isImageFile(file: File): boolean {
  if (isPdfFile(file)) return false;
  const type = (file.type || "").toLowerCase();
  const name = (file.name || "").toLowerCase();
  if (type.startsWith("image/")) return true;
  return /\.(jpe?g|png|webp|gif|bmp)$/i.test(name);
}

function varianceOfLaplacianApprox(data: ImageData): number {
  const { data: px, width, height } = data;
  let sum = 0;
  let n = 0;
  for (let y = 1; y < height - 1; y += 2) {
    for (let x = 1; x < width - 1; x += 2) {
      const i = (y * width + x) * 4;
      const c = px[i];
      const r = px[i + 4];
      const d = px[i + width * 4];
      sum += Math.abs(c - r) + Math.abs(c - d);
      n += 2;
    }
  }
  return n ? sum / n : 0;
}

function clampCrop(crop: CropRect): CropRect {
  const x = Math.min(0.92, Math.max(0, crop.x));
  const y = Math.min(0.92, Math.max(0, crop.y));
  const w = Math.min(1 - x, Math.max(0.08, crop.w));
  const h = Math.min(1 - y, Math.max(0.08, crop.h));
  return { x, y, w, h };
}

/** Default inset framing — invites the clerk to tighten around the page. */
export function defaultCropRect(): CropRect {
  return { x: 0.06, y: 0.06, w: 0.88, h: 0.88 };
}

type Decoded = { bitmap: ImageBitmap; close: () => void };

async function decodeViaBitmap(file: File): Promise<Decoded | null> {
  try {
    const opts: ImageBitmapOptions = { imageOrientation: "from-image" };
    const bitmap = await createImageBitmap(file, opts);
    return { bitmap, close: () => bitmap.close() };
  } catch {
    try {
      const bitmap = await createImageBitmap(file);
      return { bitmap, close: () => bitmap.close() };
    } catch {
      return null;
    }
  }
}

async function decodeViaElement(file: File): Promise<Decoded | null> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error("decode"));
      el.src = url;
    });
    const bitmap = await createImageBitmap(img);
    return { bitmap, close: () => bitmap.close() };
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function decodeImage(file: File): Promise<Decoded | null> {
  return (await decodeViaBitmap(file)) ?? (await decodeViaElement(file));
}

function applyMildContrast(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  try {
    const img = ctx.getImageData(0, 0, w, h);
    const px = img.data;
    const factor = 1.12;
    const intercept = 128 * (1 - factor);
    for (let i = 0; i < px.length; i += 4) {
      px[i] = Math.min(255, Math.max(0, px[i] * factor + intercept));
      px[i + 1] = Math.min(255, Math.max(0, px[i + 1] * factor + intercept));
      px[i + 2] = Math.min(255, Math.max(0, px[i + 2] * factor + intercept));
    }
    ctx.putImageData(img, 0, 0);
  } catch {
    /* contrast is best-effort; never fail the read */
  }
}

export async function prepareScanImage(
  file: File,
  options: PrepareOptions = {},
): Promise<PrepareResult> {
  if (!file || file.size <= 0) return { error_key: "idp.emptyFile" };
  if (file.size > MAX_BYTES) return { error_key: "idp.tooLarge" };
  const name = (file.name || "document").trim() || "document";
  const type = (file.type || "").toLowerCase().split(";")[0].trim();
  if (type.includes("heic") || type.includes("heif") || /\.hei[cf]$/i.test(name)) {
    return { error_key: "idp.needJpeg" };
  }
  if (isPdfFile(file)) {
    return { file };
  }

  const decoded = await decodeImage(file);
  if (!decoded) {
    return { error_key: "idp.readFailed" };
  }

  try {
    const { bitmap } = decoded;
    const crop = options.crop ? clampCrop(options.crop) : null;
    const srcX = crop ? Math.round(crop.x * bitmap.width) : 0;
    const srcY = crop ? Math.round(crop.y * bitmap.height) : 0;
    const srcW = crop ? Math.max(1, Math.round(crop.w * bitmap.width)) : bitmap.width;
    const srcH = crop ? Math.max(1, Math.round(crop.h * bitmap.height)) : bitmap.height;

    const scale = Math.min(1, LONG_EDGE / Math.max(srcW, srcH));
    const w = Math.max(1, Math.round(srcW * scale));
    const h = Math.max(1, Math.round(srcH * scale));
    if (Math.min(w, h) < MIN_EDGE) {
      return { error_key: "idp.retake" };
    }

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return { error_key: "idp.readFailed" };
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bitmap, srcX, srcY, srcW, srcH, 0, 0, w, h);
    applyMildContrast(ctx, w, h);

    const sample = ctx.getImageData(0, 0, Math.min(w, 320), Math.min(h, 320));
    if (varianceOfLaplacianApprox(sample) < MIN_SHARPNESS) {
      return { error_key: "idp.retake" };
    }

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) return { error_key: "idp.readFailed" };
    const outName = name.replace(/\.[^.]+$/, "") + ".jpg";
    return { file: new File([blob], outName, { type: "image/jpeg", lastModified: Date.now() }) };
  } finally {
    decoded.close();
  }
}
