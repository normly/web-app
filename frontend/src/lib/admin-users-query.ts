// frontend/src/lib/admin-users-query.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PAGE_SIZES, ROLES, type SortKey, type UsersQuery } from "@/lib/admin-api";

const SORT_KEYS: SortKey[] = [
  "email", "first_name", "last_name", "sign_in", "role", "publisher", "last_login_at",
  "created_at", "status",
];
const STATUSES = ["active", "blocked", "invited", "expired"] as const;

export const DEFAULT_USERS_QUERY: UsersQuery = {
  q: "", role: "all", status: "all", sort: "email", order: "asc", page: 1, pageSize: 10,
};

function oneOf<T extends string, F extends string>(
  value: string | null, allowed: readonly T[], fallback: F,
): T | F {
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export function parseUsersQuery(params: URLSearchParams): UsersQuery {
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("page_size"));
  return {
    q: params.get("q") ?? "",
    role: oneOf(params.get("role"), ROLES, "all"),
    status: oneOf(params.get("status"), STATUSES, "all"),
    sort: oneOf(params.get("sort"), SORT_KEYS, "email"),
    order: params.get("order") === "desc" ? "desc" : "asc",
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : 10,
  };
}

export function serializeUsersQuery(query: UsersQuery): string {
  const params = new URLSearchParams();
  const d = DEFAULT_USERS_QUERY;
  if (query.q !== d.q) params.set("q", query.q);
  if (query.role !== d.role) params.set("role", query.role);
  if (query.status !== d.status) params.set("status", query.status);
  if (query.sort !== d.sort) params.set("sort", query.sort);
  if (query.order !== d.order) params.set("order", query.order);
  if (query.page !== d.page) params.set("page", String(query.page));
  if (query.pageSize !== d.pageSize) params.set("page_size", String(query.pageSize));
  return params.toString();
}

export function useUsersQuery() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = React.useMemo(
    () => parseUsersQuery(new URLSearchParams(searchParams.toString())), [searchParams],
  );
  const update = React.useCallback((patch: Partial<UsersQuery>) => {
    // Any change except paging starts again at page 1.
    const next = { ...query, ...patch, page: "page" in patch ? patch.page ?? 1 : 1 };
    const search = serializeUsersQuery(next);
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  }, [query, router, pathname]);
  return { query, update };
}
