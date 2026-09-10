// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import { LocaleProvider, type Locale } from "@/lib/i18n/provider";
import { JurisdictionProvider } from "@/lib/jurisdiction/provider";
import { JURISDICTIONS, type Jurisdiction } from "@/lib/jurisdiction/constants";
import { ThemeProvider } from "@/components/theme-provider";
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

async function resolveInitialLocale(): Promise<Locale> {
  const cookieLocale = (await cookies()).get("normly_locale")?.value;
  if (cookieLocale === "de" || cookieLocale === "en") {
    return cookieLocale;
  }
  const acceptLanguage = (await headers()).get("accept-language") ?? "";
  return acceptLanguage.toLowerCase().startsWith("en") ? "en" : "de";
}

async function resolveInitialJurisdiction(): Promise<Jurisdiction> {
  const cookieJurisdiction = (await cookies()).get("normly_jurisdiction")?.value;
  if ((JURISDICTIONS as readonly string[]).includes(cookieJurisdiction ?? "")) {
    return cookieJurisdiction as Jurisdiction;
  }
  return "DE";
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  const initialLocale = await resolveInitialLocale();
  const initialJurisdiction = await resolveInitialJurisdiction();
  return (
    <html
      lang={initialLocale}
      suppressHydrationWarning
      style={{ "--brand": config.brandColorHsl } as React.CSSProperties}
    >
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <LocaleProvider initialLocale={initialLocale}>
            <JurisdictionProvider initialJurisdiction={initialJurisdiction}>
              <ServiceWorkerRegistration />
              {children}
            </JurisdictionProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
