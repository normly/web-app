// frontend/tests/unit/admin-users-query.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { describe, expect, it } from "vitest";
import { DEFAULT_USERS_QUERY, parseUsersQuery, serializeUsersQuery } from "@/lib/admin-users-query";

describe("users query in the URL", () => {
  it("falls back to defaults for missing or invalid values", () => {
    expect(parseUsersQuery(new URLSearchParams(""))).toEqual(DEFAULT_USERS_QUERY);
    expect(parseUsersQuery(new URLSearchParams("page=-3&page_size=7&sort=password&role=owner")))
      .toEqual(DEFAULT_USERS_QUERY);
  });

  it("round-trips non-default values and omits defaults", () => {
    const query = { ...DEFAULT_USERS_QUERY, q: "keller", role: "administrator" as const,
                    status: "blocked" as const, sort: "last_login_at" as const,
                    order: "desc" as const, page: 3, pageSize: 50 };
    const serialized = serializeUsersQuery(query);
    expect(parseUsersQuery(new URLSearchParams(serialized))).toEqual(query);
    expect(serializeUsersQuery(DEFAULT_USERS_QUERY)).toBe("");
  });
});
