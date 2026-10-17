/** Downscale / JPEG re-encode / blur gate before Scan upload. */

const LONG_EDGE = 2800;
const JPEG_QUALITY = 0.85;
const MIN_EDGE = 480;
const MAX_BYTES = 25 * 1024 * 1024;

export type PrepareResult = { file: File } | { error_key: string };

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

export async function prepareScanImage(file: File): Promise<PrepareResult> {
  if (!file || file.size <= 0) return { error_key: "idp.emptyFile" };
  if (file.size > MAX_BYTES) return { error_key: "idp.tooLarge" };
  const name = (file.name || "document").trim() || "document";
  const type = (file.type || "").toLowerCase().split(";")[0].trim();
  if (type.includes("heic") || type.includes("heif") || /\.hei[cf]$/i.test(name)) {
    return { error_key: "idp.needJpeg" };
  }
  if (type === "application/pdf" || /\.pdf$/i.test(name)) {
    return { file };
  }

  try {
    const bitmap = await createImageBitmap(file);
    try {
      const scale = Math.min(1, LONG_EDGE / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      if (Math.min(w, h) < MIN_EDGE) {
        return { error_key: "idp.retake" };
      }
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return { error_key: "idp.readFailed" };
      ctx.drawImage(bitmap, 0, 0, w, h);
      const sample = ctx.getImageData(0, 0, Math.min(w, 320), Math.min(h, 320));
      if (varianceOfLaplacianApprox(sample) < 2.5) {
        return { error_key: "idp.retake" };
      }
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
      );
      if (!blob) return { error_key: "idp.readFailed" };
      const outName = name.replace(/\.[^.]+$/, "") + ".jpg";
      return { file: new File([blob], outName, { type: "image/jpeg", lastModified: Date.now() }) };
    } finally {
      bitmap.close();
    }
  } catch {
    let nextType = type || "image/jpeg";
    if (nextType === "image/jpg") nextType = "image/jpeg";
    return { file: new File([file], name, { type: nextType, lastModified: file.lastModified }) };
  }
}
