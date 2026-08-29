// frontend/src/lib/jurisdiction/provider.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { JURISDICTIONS, type Jurisdiction } from "./constants";

// Mirrors lib/i18n/provider.tsx's LocaleProvider exactly: a small React
// Context so any client component (JurisdictionSwitcher, the chat send
// handler, the search/detail pages) can read and change the current
// jurisdiction without prop-drilling, persisted via a plain (non-httpOnly --
// this is UI state, not a security-relevant token) cookie the root layout
// reads server-side on the next request.
//
// JURISDICTIONS/Jurisdiction live in ./constants, not here, and are
// re-exported below only for this module's existing client consumers --
// layout.tsx (a Server Component) must import them directly from
// ./constants instead. See constants.ts for why.
export { JURISDICTIONS, type Jurisdiction };

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
