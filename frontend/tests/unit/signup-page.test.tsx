// frontend/tests/unit/signup-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { SignupPageContent } from "@/app/signup/signup-page-content";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const originalFetch = global.fetch;

describe("SignupPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    push.mockClear();
  });

  it("renders the heading, the register form, and a link back to login", () => {
    render(
      <LocaleProvider initialLocale="de">
        <SignupPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Konto erstellen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Konto erstellen" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/login");
  });

  it("navigates home after a successful registration", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <SignupPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "new@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
