// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { UsageSection } from "@/components/account/usage-section";

const originalFetch = global.fetch;

function usage(overrides: Record<string, unknown> = {}) {
  return new Response(
    JSON.stringify({
      used: 7, limit: 30, resets_at: "2099-01-01T00:00:00Z",
      pool_exhausted: false, pool_resets_at: null, ...overrides,
    }),
    { status: 200 },
  );
}

function renderSection() {
  render(
    <LocaleProvider initialLocale="de">
      <UsageSection />
    </LocaleProvider>,
  );
}

describe("UsageSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows used and limit with a progress bar and the reset", async () => {
    global.fetch = vi.fn().mockResolvedValue(usage());
    renderSection();

    await waitFor(() => expect(screen.getByText("KI-Antworten heute: 7 von 30")).toBeInTheDocument());
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText(/Wird zurückgesetzt um/)).toBeInTheDocument();
    expect(screen.queryByText(/ausgelastet/)).not.toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith("/api/account/usage");
  });

  it("shows the capacity notice when the pool is exhausted", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      usage({ pool_exhausted: true, pool_resets_at: "2099-01-01T00:00:00Z" }),
    );
    renderSection();

    await waitFor(() => expect(screen.getByText(/KI-Antworten sind derzeit ausgelastet/)).toBeInTheDocument());
    // Signed-in users get the notice without the sign-in hint.
    expect(screen.queryByText(/Anmeldung/)).not.toBeInTheDocument();
  });

  it("shows an error when loading fails", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 503 }));
    renderSection();

    await waitFor(() =>
      expect(screen.getByText("Die Nutzung konnte nicht geladen werden.")).toBeInTheDocument(),
    );
  });
});
