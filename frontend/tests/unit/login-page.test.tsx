// frontend/tests/unit/login-page.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { LoginPageContent } from "@/app/login/login-page-content";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const originalFetch = global.fetch;

describe("LoginPageContent", () => {
  afterEach(() => {
    global.fetch = originalFetch;
    push.mockClear();
  });

  it("renders the heading, description, and login form", () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Willkommen zurück" })).toBeInTheDocument();
    expect(screen.getByText("Melde dich an, um fortzufahren.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("shows links to signup and the magic-link page", () => {
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    expect(screen.getByRole("link", { name: "Registrieren" })).toHaveAttribute("href", "/signup");
    expect(screen.getByRole("link", { name: "Magic-Link" })).toHaveAttribute(
      "href", "/magic-link",
    );
  });

  it("navigates home after a successful login", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    render(
      <LocaleProvider initialLocale="de">
        <LoginPageContent />
      </LocaleProvider>,
    );
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "a@example.de" },
    });
    fireEvent.change(screen.getByLabelText("Passwort"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
