// frontend/src/components/chat/chat-shell.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

"use client";

import * as React from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";
import { useTranslation } from "@/lib/i18n/provider";

export function ChatShell({
  onNewChat,
  children,
}: {
  onNewChat: () => void;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();

  return (
    // will-change-transform on this wrapper establishes a new containing
    // block for position:fixed descendants (per the CSS Transforms/Will
    // Change specs, without applying any actual transform or visual
    // change). This matters because the shared sidebar.tsx primitive
    // renders <Sidebar>'s visible desktop panel as `fixed inset-y-0
    // left-0` -- always relative to the nearest such containing block, or
    // the browser viewport if there is none. Without this wrapper,
    // ChatHistorySidebar's fixed panel (side="left", same default as
    // AppShell's own outer Chat/Suche sidebar) would escape all the way
    // out to the true viewport edge and paint directly on top of
    // AppShell's sidebar instead of appearing beside it -- confirmed with
    // an actual browser render (Playwright), not something jsdom-based
    // unit tests can catch since they never evaluate CSS position:fixed
    // layout. With this wrapper, the fixed panel instead resolves
    // relative to this div's own box, which sits right after AppShell's
    // sidebar in the page's normal layout flow -- exactly where the two
    // sidebars are meant to meet.
    <div className="relative w-full flex-1 will-change-transform">
      {/* min-h-0 overrides the primitive's own min-h-svh (see
          sidebar.tsx's SidebarProvider): cn()'s twMerge keeps the LAST
          class touching a given CSS property, and this className prop is
          merged in after the primitive's own classes, so min-h-0 wins.
          Without this, this nested provider's min-h-svh stacks on top of
          AppShell's outer SidebarProvider (page.tsx) doing the same,
          making every chat page render taller than the actual viewport
          (a permanent whole-page scrollbar) -- confirmed via a real
          browser render, not something jsdom-based unit tests catch. */}
      <SidebarProvider className="min-h-0">
        <ChatHistorySidebar onNewChat={onNewChat} />
        {/* A plain div, not SidebarInset: HomePageContent is already
            rendered inside AppShell's own SidebarInset (page.tsx), which
            renders a <main> around PageHeader + HomePageContent.
            SidebarInset always renders <main> unconditionally (no
            polymorphic "as"), so using it again here would nest a second
            <main> landmark inside the first -- exactly what
            smoke.test.tsx's "Finding 2" guard checks for. The
            peer-data-[variant=inset] margin/rounding classes SidebarInset
            adds are no-ops here anyway: ChatHistorySidebar's <Sidebar>
            doesn't set variant="inset" (default is "sidebar"), so this div
            only needs the same plain flex layout. */}
        <div className="relative flex w-full flex-1 flex-col bg-background">
          {/* This sidebar starts open by default on desktop (matching the
              ai-chat-v2 reference's always-visible history panel) and
              closed by default on mobile (the primitive's own
              openMobile state always starts false, regardless of
              defaultOpen) -- md:hidden here means desktop users get no
              toggle chrome (matching the reference, which shows none),
              while mobile users get the one reachable way to open it.
              This trigger lives in the SidebarInset-equivalent wrapper
              above, never inside ChatHistorySidebar's own <Sidebar> --
              see Global Constraints on why that placement matters. */}
          <div className="flex items-center border-b p-2 md:hidden">
            <SidebarTrigger aria-label={t("nav.toggleChatHistory")} />
          </div>
          {children}
        </div>
      </SidebarProvider>
    </div>
  );
}
