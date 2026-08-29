// frontend/tests/unit/jurisdiction.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JurisdictionProvider, useJurisdiction } from "@/lib/jurisdiction/provider";

function Probe() {
  const { jurisdiction, setJurisdiction } = useJurisdiction();
  return <button onClick={() => setJurisdiction("EU")}>{jurisdiction}</button>;
}

describe("JurisdictionProvider", () => {
  it("exposes the initial jurisdiction", () => {
    render(
      <JurisdictionProvider initialJurisdiction="DE">
        <Probe />
      </JurisdictionProvider>,
    );
    expect(screen.getByRole("button", { name: "DE" })).toBeInTheDocument();
  });

  it("updates the jurisdiction and sets the cookie when changed", () => {
    render(
      <JurisdictionProvider initialJurisdiction="DE">
        <Probe />
      </JurisdictionProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "DE" }));
    expect(screen.getByRole("button", { name: "EU" })).toBeInTheDocument();
    expect(document.cookie).toContain("normly_jurisdiction=EU");
  });
});
