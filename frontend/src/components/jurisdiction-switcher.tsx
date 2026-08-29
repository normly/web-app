// frontend/src/components/jurisdiction-switcher.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import { useJurisdiction, JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/provider";

export function JurisdictionSwitcher() {
  const { jurisdiction, setJurisdiction } = useJurisdiction();
  return (
    <select
      value={jurisdiction}
      onChange={(event) => setJurisdiction(event.target.value as Jurisdiction)}
      className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      aria-label="Jurisdiktion"
    >
      {JURISDICTIONS.map((value) => (
        <option key={value} value={value}>
          {value}
        </option>
      ))}
    </select>
  );
}
