

import { isNative } from "../../../mobile/platform";

export type CameraPick =
  | { ok: true; file: File }
  | { ok: false; error_key: string; detail?: string };

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

    const { Camera, CameraResultType, CameraSource } =
      await import("@capacitor/camera");

    const perm = await Camera.requestPermissions({
      permissions: ["camera"],
    });

    if (perm.camera !== "granted" && perm.camera !== "limited") {
      return { ok: false, error_key: "idp.cameraDenied" };
    }

    const photo = await Camera.getPhoto({
      quality: 85,
      resultType: CameraResultType.Base64,
      source: CameraSource.Camera,
      correctOrientation: true,
    });

    if (!photo.base64String) {
      return { ok: false, error_key: "idp.emptyFile" };
    }

    const binary = atob(photo.base64String);
    const bytes = new Uint8Array(binary.length);

    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    const mime =
      photo.format?.toLowerCase() === "png"
        ? "image/png"
        : "image/jpeg";

    const file = new File(
      [bytes],
      `scan-${Date.now()}.${mime === "image/png" ? "png" : "jpg"}`,
      { type: mime, lastModified: Date.now() },
    );

    return { ok: true, file };
  } catch (err: unknown) {
    const raw = err instanceof Error ? err.message : String(err);
    const msg = raw.toLowerCase();

    console.error("takePhoto failed:", err);

    if (msg.includes("cancel")) {
      return { ok: false, error_key: "idp.emptyFile", detail: raw };
    }

    if (
      msg.includes("denied") ||
      msg.includes("permission") ||
      msg.includes("unauthorized")
    ) {
      return { ok: false, error_key: "idp.cameraDenied", detail: raw };
    }

    return {
      ok: false,
      error_key: "idp.readFailed",
      detail: raw,
    };
  }
}
