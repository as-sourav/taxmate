/**
 * Catalog CRUD hooks. Screens must not call /api/resource or Desk methods.
 * These wrap taxmate.api.resource.* listed in get_catalog().
 */
import { useEffect, useMemo } from "react";
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk";

import { DT, METHOD } from "./frappe";
import { useSession } from "./session";
import { hardReload } from "../mobile/platform";

type OrderBy = { field: string; order?: "asc" | "desc" };

type ListOpts = {
  fields?: (string | Record<string, string>)[];
  filters?: unknown;
  orFilters?: unknown;
  orderBy?: OrderBy;
  limit?: number;
  limit_start?: number;
  groupBy?: string;
};

function owningCompanyOf(doc: unknown): string | null {
  if (!doc || typeof doc !== "object") return null;
  const row = doc as Record<string, unknown>;
  for (const key of ["company", "representative_company", "custom_company"]) {
    const value = row[key];
    if (typeof value === "string" && value) return value;
  }
  return null;
}

export function useDocList<T>(doctype: string, opts: ListOpts = {}, key?: string | null) {
  const params = {
    doctype,
    fields: opts.fields ? JSON.stringify(opts.fields) : undefined,
    filters: opts.filters ? JSON.stringify(opts.filters) : undefined,
    or_filters: opts.orFilters ? JSON.stringify(opts.orFilters) : undefined,
    order_by: opts.orderBy
      ? `${opts.orderBy.field} ${opts.orderBy.order ?? "desc"}`
      : undefined,
    limit_start: opts.limit_start,
    limit_page_length: opts.limit ?? 20,
    group_by: opts.groupBy,
  };
  const call = useFrappeGetCall<{ message: T[] }>(
    METHOD.getList,
    params,
    key === null ? null : (key ?? `list-${doctype}-${JSON.stringify(params)}`),
  );
  return {
    data: call.data?.message,
    error: call.error,
    isLoading: call.isLoading,
    mutate: call.mutate,
  };
}

/** City from the linked Address. primary_address is an HTML display and is not the city. */
export function useAddressCities(names: Array<string | undefined>) {
  const unique = [...new Set(names.filter((name): name is string => !!name))].sort();
  const list = useDocList<{ name: string; city?: string }>(
    DT.address,
    {
      fields: ["name", "city"],
      filters: [["name", "in", unique.length ? unique : ["__none__"]]],
      limit: Math.max(unique.length, 1),
    },
    unique.length ? `address-cities:${unique.join("\n")}` : null,
  );
  return useMemo(() => {
    const cities = new Map<string, string>();
    for (const row of list.data ?? []) {
      const city = (row.city || "").replace(/<[^>]*>/g, "").trim();
      if (row.name && city) cities.set(row.name, city);
    }
    return cities;
  }, [list.data]);
}

export function useDoc<T>(
  doctype: string,
  name?: string,
  key?: string | null,
  opts?: { isPaused?: () => boolean },
) {
  const session = useSession();
  const paused = opts?.isPaused?.() || !name;
  const call = useFrappeGetCall<{ message: T }>(
    METHOD.get,
    { doctype, name },
    paused ? null : (key ?? `get-${doctype}-${name}`),
  );
  const data = call.data?.message;

  // resource.get may adopt the document's company; refresh like the switcher
  // so the header and cached lists match the document just opened.
  useEffect(() => {
    const company = owningCompanyOf(data);
    if (!company || !session.company || company === session.company) return;
    hardReload();
  }, [data, session.company]);

  return {
    data,
    error: call.error,
    isLoading: call.isLoading,
    mutate: call.mutate,
  };
}

export function useDocCount(
  doctype: string,
  filters?: unknown,
  orFilters?: unknown,
  key?: string | null,
) {
  const paused = key === null;
  const call = useFrappeGetCall<{ message: number }>(
    METHOD.getCount,
    {
      doctype,
      filters: filters ? JSON.stringify(filters) : undefined,
      or_filters: orFilters ? JSON.stringify(orFilters) : undefined,
    },
    paused ? null : (key ?? `count-${doctype}-${JSON.stringify(filters ?? [])}-${JSON.stringify(orFilters ?? [])}`),
  );
  return {
    data: paused ? undefined : (call.data?.message ?? 0),
    error: call.error,
    isLoading: paused || call.isLoading,
    mutate: call.mutate,
  };
}

export function useInsert() {
  const { call, loading, error, reset, isCompleted } = useFrappePostCall<{ message: Record<string, unknown> }>(
    METHOD.insert,
  );
  const createDoc = async (doctype: string, doc: Record<string, unknown>) => {
    const res = await call({ doc: { ...doc, doctype } });
    return res.message;
  };
  return { createDoc, loading, error, reset, isCompleted };
}

export function useSave() {
  const { call, loading, error, reset, isCompleted } = useFrappePostCall<{ message: Record<string, unknown> }>(
    METHOD.save,
  );
  const latest = useFrappePostCall<{ message: Record<string, unknown> }>(METHOD.get);
  const updateDoc = async (doctype: string, name: string, doc: Record<string, unknown>) => {
    const current = await latest.call({ doctype, name });
    const res = await call({ doc: { ...(current.message ?? {}), ...doc, doctype, name } });
    return res.message;
  };
  return { updateDoc, loading, error, reset, isCompleted };
}
