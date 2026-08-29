// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import { LocaleProvider, type Locale } from "@/lib/i18n/provider";
import { JurisdictionProvider, JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/provider";
import "./globals.css";

export const dynamic = "force-dynamic";

export function generateMetadata(): Metadata {
  const config = getInstanceConfig();
  return {
    title: config.instanceName,
    description: "Normen- und Regelwerkswissen im Dialog",
    manifest: "/manifest.webmanifest",
  };
}

function resolveInitialLocale(): Locale {
  const cookieLocale = cookies().get("normly_locale")?.value;
  if (cookieLocale === "de" || cookieLocale === "en") {
    return cookieLocale;
  }
  const acceptLanguage = headers().get("accept-language") ?? "";
  return acceptLanguage.toLowerCase().startsWith("en") ? "en" : "de";
}

function resolveInitialJurisdiction(): Jurisdiction {
  const cookieJurisdiction = cookies().get("normly_jurisdiction")?.value;
  if ((JURISDICTIONS as readonly string[]).includes(cookieJurisdiction ?? "")) {
    return cookieJurisdiction as Jurisdiction;
  }
  return "DE";
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  const initialLocale = resolveInitialLocale();
  const initialJurisdiction = resolveInitialJurisdiction();
  return (
    <html
      lang={initialLocale}
      style={{ "--brand": config.brandColorHsl } as React.CSSProperties}
    >
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <JurisdictionProvider initialJurisdiction={initialJurisdiction}>
            <ServiceWorkerRegistration />
            {children}
          </JurisdictionProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
