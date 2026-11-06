// frontend/tests/unit/admin-api.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminApiError, adminApi, errorKey } from "@/lib/admin-api";

const originalFetch = global.fetch;

describe("adminApi", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("maps the user page to camelCase and builds the query", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      rows: [{
        kind: "account", id: "1", email: "a@b.de", first_name: "A", last_name: null,
        sign_in_methods: ["email", "google"], role: "publisher", publisher_id: "p",
        publisher_name: "DIN Media", last_login_at: null, created_at: "2026-10-01T10:00:00Z",
        status: "active", block_reason: null, expires_at: null,
      }],
      total: 1, page: 1, page_size: 10,
    })));

    const page = await adminApi.listUsers({
      q: "a", role: "publisher", status: "all", sort: "email", order: "asc", page: 1, pageSize: 10,
    });

    expect(page.rows[0]).toMatchObject({
      firstName: "A", signInMethods: ["email", "google"], publisherName: "DIN Media",
    });
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/admin/users?q=a&role=publisher&sort=email&order=asc&page=1&page_size=10",
    );
  });

  it("turns an error body into AdminApiError with the backend code", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "last_administrator" }), { status: 409 }),
    );
    const failure = adminApi.unblock("1");
    await expect(failure).rejects.toBeInstanceOf(AdminApiError);
    await expect(failure).rejects.toMatchObject({ status: 409, code: "last_administrator" });
  });

  it("maps known codes to translation keys and everything else to generic", () => {
    expect(errorKey(new AdminApiError(409, "self_action"))).toBe("admin.errors.self_action");
    expect(errorKey(new AdminApiError(400, "invalid or missing parameter: body.email")))
      .toBe("admin.errors.generic");
    expect(errorKey(new Error("network"))).toBe("admin.errors.generic");
  });
});
