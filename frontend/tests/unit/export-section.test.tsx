// frontend/tests/unit/export-section.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { ExportSection } from "@/components/account/export-section";

const originalFetch = global.fetch;

describe("ExportSection", () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("fetches the export payload and triggers a download when clicked", async () => {
    const exportBody = { account: { email: "a@example.de" }, chat_sessions: [] };
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(exportBody), { status: 200 }));
    const createObjectUrlSpy = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectUrlSpy = vi.fn();
    global.URL.createObjectURL = createObjectUrlSpy;
    global.URL.revokeObjectURL = revokeObjectUrlSpy;

    render(
      <LocaleProvider initialLocale="de">
        <ExportSection />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Export herunterladen" }));

    await waitFor(() => expect(createObjectUrlSpy).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith("/api/account/export");
  });
});
