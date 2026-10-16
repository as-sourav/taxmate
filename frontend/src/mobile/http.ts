/**
 * fetch for callers that skip frappe-react-sdk (multipart uploads).
 * Web: plain fetch. Native: workspace origin only, TaxMate token, no cookies.
 */
import { t } from "../i18n/strings";
import { isNative, MOBILE_BUILD, signalMobile } from "./platform";
import { authHeader, getWorkspace } from "./session";

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!MOBILE_BUILD || !isNative()) return fetch(path, init);
  return nativeFetch(path, init);
}

async function nativeFetch(path: string, init: RequestInit): Promise<Response> {
  const workspace = getWorkspace();
  if (!workspace) throw new Error(t("mob.err.noWorkspace"));
  const url = new URL(path, `${workspace}/`);
  if (url.origin !== new URL(workspace).origin) {
    throw new Error(`apiFetch refused a request to ${url.origin}: not the workspace`);
  }
  const headers = new Headers(init.headers);
  headers.delete("X-Frappe-CSRF-Token");
  const auth = authHeader();
  if (auth) headers.set("Authorization", auth);
  headers.set("Accept", "application/json");
  const res = await fetch(url.toString(), { ...init, headers, credentials: "omit" });
  if (res.status === 401) {
    signalMobile("auth-lost");
    return res;
  }
  if (!res.ok) {
    try {
      const data = (await res.clone().json()) as { exc_type?: string };
      if (data?.exc_type === "AuthenticationError") signalMobile("auth-lost");
    } catch {
      /* non-JSON */
    }
  }
  return res;
}

/** Absolute workspace file URL for <img> on native; relative path on web. */
export function fileUrl(path: string): string {
  if (!MOBILE_BUILD || !isNative() || !path.startsWith("/") || path.startsWith("//")) return path;
  const workspace = getWorkspace();
  return workspace ? `${workspace}${path}` : path;
}
