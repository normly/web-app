// frontend/src/app/layout.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import type { Metadata } from "next";
import { getInstanceConfig } from "@/lib/config";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import "./globals.css";

export function generateMetadata(): Metadata {
  const config = getInstanceConfig();
  return {
    title: config.instanceName,
    description: "Normen- und Regelwerkswissen im Dialog",
    manifest: "/manifest.webmanifest",
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const config = getInstanceConfig();
  return (
    <html lang="de" style={{ "--brand": config.brandColorHsl } as React.CSSProperties}>
      <body>
        <ServiceWorkerRegistration />
        {children}
      </body>
    </html>
  );
}
