// frontend/src/lib/jurisdiction/provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";

// Mirrors lib/i18n/provider.tsx's LocaleProvider exactly: a small React
// Context so any client component (JurisdictionSwitcher, the chat send
// handler, the search/detail pages) can read and change the current
// jurisdiction without prop-drilling, persisted via a plain (non-httpOnly --
// this is UI state, not a security-relevant token) cookie the root layout
// reads server-side on the next request.
export const JURISDICTIONS = ["DE", "EU"] as const;
export type Jurisdiction = (typeof JURISDICTIONS)[number];

interface JurisdictionContextValue {
  jurisdiction: Jurisdiction;
  setJurisdiction: (jurisdiction: Jurisdiction) => void;
}

const JurisdictionContext = React.createContext<JurisdictionContextValue | null>(null);

export function JurisdictionProvider({
  children,
  initialJurisdiction,
}: {
  children: React.ReactNode;
  initialJurisdiction: Jurisdiction;
}) {
  const [jurisdiction, setJurisdictionState] = React.useState<Jurisdiction>(
    initialJurisdiction,
  );

  const setJurisdiction = React.useCallback((next: Jurisdiction) => {
    setJurisdictionState(next);
    document.cookie = `normly_jurisdiction=${next}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
  }, []);

  const value = React.useMemo(
    () => ({ jurisdiction, setJurisdiction }),
    [jurisdiction, setJurisdiction],
  );

  return (
    <JurisdictionContext.Provider value={value}>{children}</JurisdictionContext.Provider>
  );
}

export function useJurisdiction(): JurisdictionContextValue {
  const context = React.useContext(JurisdictionContext);
  if (context === null) {
    throw new Error("useJurisdiction must be used within a JurisdictionProvider");
  }
  return context;
}
