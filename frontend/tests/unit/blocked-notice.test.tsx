// frontend/tests/unit/blocked-notice.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "@/lib/i18n/provider";
import { BlockedNotice } from "@/components/auth/blocked-notice";

function renderNotice(contact: string | null) {
  return render(<LocaleProvider initialLocale="de"><BlockedNotice contact={contact} /></LocaleProvider>);
}

describe("BlockedNotice", () => {
  it("links an e-mail contact with mailto", () => {
    renderNotice("support@normly.example");
    const link = screen.getByRole("link", { name: "support@normly.example" });
    expect(link).toHaveAttribute("href", "mailto:support@normly.example");
    expect(screen.getByRole("alert")).toHaveTextContent("Bei Fragen wende dich an support@normly.example.");
  });

  it("links a URL contact directly", () => {
    renderNotice("https://normly.example/imprint");
    expect(screen.getByRole("link", { name: "https://normly.example/imprint" }))
      .toHaveAttribute("href", "https://normly.example/imprint");
  });

  it("treats a URL containing @ as a URL", () => {
    renderNotice("https://normly.example/@team");
    expect(screen.getByRole("link", { name: "https://normly.example/@team" }))
      .toHaveAttribute("href", "https://normly.example/@team");
  });

  it("shows other text without a link", () => {
    renderNotice("the operator");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Bei Fragen wende dich an the operator.");
  });

  it("shows no contact line without a contact", () => {
    renderNotice(null);
    expect(screen.getByRole("alert")).not.toHaveTextContent("Bei Fragen");
  });
});
