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
      resultType: CameraResultType.Uri,
      source: CameraSource.Camera,
      correctOrientation: true,
    });
    const url = photo.webPath || photo.path;
    if (!url) return { ok: false, error_key: "idp.emptyFile" };
    const res = await fetch(url);
    const blob = await res.blob();
    const file = new File([blob], `scan-${Date.now()}.jpg`, {
      type: blob.type || "image/jpeg",
    });
    return { ok: true, file };
  } catch (err) {
    const msg = String(err || "").toLowerCase();
    if (msg.includes("cancel") || msg.includes("user")) {
      return { ok: false, error_key: "idp.emptyFile" };
    }
    if (msg.includes("permission") || msg.includes("denied")) {
      return { ok: false, error_key: "idp.cameraDenied" };
    }
    return { ok: false, error_key: "idp.readFailed" };
  }
}
