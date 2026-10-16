import { createContext, useContext, useEffect } from "react";
import { useFrappeGetCall } from "frappe-react-sdk";

import { METHOD } from "./frappe";
import { setSiteToday } from "./status";

export type Session = {
  user: string;
  full_name?: string;
  company?: string | null;
  currency?: string | null;
  country?: string | null;
  roles?: string[];
  spa_role?: "owner" | "accountant" | "clerk" | "viewer" | null;
  spa_roles?: Array<"owner" | "accountant" | "clerk" | "viewer">;
  is_app_provider?: boolean;
  extra_roles?: string[];
  /** The SITE's date, so anything date-driven agrees with the server. */
  today?: string;
  time_zone?: string;
};

const SessionContext = createContext<Session>({ user: "", roles: [] });

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { data } = useFrappeGetCall<{ message: Session }>(METHOD.getSession);
  const session = data?.message ?? { user: "", roles: [] };
  useEffect(() => { setSiteToday(session.today); }, [session.today]);
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  return useContext(SessionContext);
}
