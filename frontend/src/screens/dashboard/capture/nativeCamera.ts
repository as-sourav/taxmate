/** Native camera pick with explicit permission handling.
 * Callers: CaptureDesk onTakePhoto / cameraAvailable.
 */

import { isNative } from "../../../mobile/platform";

export type CameraPick =
  | { ok: true; file: File }
  | { ok: false; error_key: string };

export function cameraAvailable(): boolean {
  return isNative();
}

export async function takePhoto(): Promise<CameraPick> {
  if (!isNative()) {
    return { ok: false, error_key: "idp.file" };
  }
  try {
    const { Capacitor } = await import("@capacitor/core");
    if (!Capacitor.isNativePlatform()) {
      return { ok: false, error_key: "idp.file" };
    }
    const { Camera, CameraResultType, CameraSource } = await import("@capacitor/camera");
    const perm = await Camera.requestPermissions({ permissions: ["camera"] });
    if (perm.camera !== "granted" && perm.camera !== "limited") {
      return { ok: false, error_key: "idp.cameraDenied" };
    }
    const photo = await Camera.getPhoto({
  quality: 85,
  resultType: CameraResultType.DataUrl,
  source: CameraSource.Camera,
  correctOrientation: true,
});
if (!photo.dataUrl) return { ok: false, error_key: "idp.emptyFile" };
const blob = await (await fetch(photo.dataUrl)).blob();
const file = new File([blob], `scan-${Date.now()}.jpg`, { type: blob.type || "image/jpeg" });
return { ok: true, file };
} catch (err) {
  const raw = String((err as any)?.message ?? err);
  console.error("takePhoto failed:", err);
  const msg = raw.toLowerCase();
  if (msg.includes("denied") || msg.includes("permission")) {
    return { ok: false, error_key: "idp.cameraDenied" };
  }
  if (msg.includes("cancel")) {
    return { ok: false, error_key: "idp.emptyFile" };
  }
  return { ok: false, error_key: "idp.readFailed", detail: raw } as any;
}
}
