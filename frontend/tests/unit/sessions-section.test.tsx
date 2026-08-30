// frontend/tests/unit/sessions-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { SessionsSection } from "@/components/account/sessions-section";

const originalFetch = global.fetch;

describe("SessionsSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("lists sessions and marks the current one", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "sess-1", created_at: "2026-08-01T00:00:00Z",
            expires_at: "2026-09-01T00:00:00Z", is_current: true,
          },
          {
            id: "sess-2", created_at: "2026-08-15T00:00:00Z",
            expires_at: "2026-09-15T00:00:00Z", is_current: false,
          },
        ]),
        { status: 200 },
      ),
    );

    render(
      <LocaleProvider initialLocale="de">
        <SessionsSection />
      </LocaleProvider>,
    );

    await waitFor(() => expect(screen.getByText("Dieses Gerät")).toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: "Sitzung beenden" })).toHaveLength(1);
  });

  it("removes a session from the list after revoking it", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "sess-1", created_at: "2026-08-01T00:00:00Z",
              expires_at: "2026-09-01T00:00:00Z", is_current: true,
            },
            {
              id: "sess-2", created_at: "2026-08-15T00:00:00Z",
              expires_at: "2026-09-15T00:00:00Z", is_current: false,
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "session_revoked" }), { status: 200 }),
      );

    render(
      <LocaleProvider initialLocale="de">
        <SessionsSection />
      </LocaleProvider>,
    );

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Sitzung beenden" })).toHaveLength(1),
    );
    fireEvent.click(screen.getByRole("button", { name: "Sitzung beenden" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    const [calledUrl] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[1];
    expect(calledUrl).toBe("/api/account/sessions/sess-2");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Sitzung beenden" })).not.toBeInTheDocument(),
    );
  });
});
