// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import { LocaleProvider, type Locale } from "@/lib/i18n/provider";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  const initialLocale = resolveInitialLocale();
  return (
    <html
      lang={initialLocale}
      style={{ "--brand": config.brandColorHsl } as React.CSSProperties}
    >
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <ServiceWorkerRegistration />
          {children}
        </LocaleProvider>
      </body>
    </html>
  );
}
