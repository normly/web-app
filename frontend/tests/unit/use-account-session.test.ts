// frontend/tests/unit/use-account-session.test.ts
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAccountSession } from "@/lib/use-account-session";

const originalFetch = global.fetch;

describe("useAccountSession", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("fetches the session on mount and exposes the account", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    const { result } = renderHook(() => useAccountSession());
    await waitFor(() => expect(result.current.account?.email).toBe("a@example.de"));
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/session");
  });

  it("clears the account and posts to the logout endpoint", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    const { result } = renderHook(() => useAccountSession());
    await waitFor(() => expect(result.current.account).not.toBeNull());

    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    await act(async () => {
      await result.current.logout();
    });
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
    expect(result.current.account).toBeNull();
  });

  it("exposes a setter that updates the account without a network call", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          account: {
            accountId: "1", email: "a@example.de", firstName: null, lastName: null,
            avatarDataUrl: null,
          },
        }),
      ),
    );
    const { result } = renderHook(() => useAccountSession());
    await waitFor(() => expect(result.current.account?.email).toBe("a@example.de"));

    const fetchCallsBefore = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    act(() => {
      result.current.setAccount((current) => (current ? { ...current, firstName: "Alex" } : current));
    });
    expect(result.current.account?.firstName).toBe("Alex");
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(fetchCallsBefore);
  });
});
