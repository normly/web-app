// frontend/tests/unit/i18n.test.tsx
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 normly contributors

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider, useTranslation } from "@/lib/i18n/provider";
import de from "@/lib/i18n/de.json";
import en from "@/lib/i18n/en.json";

function Probe() {
  const { t } = useTranslation();
  return <span>{t("chat.sendButton")}</span>;
}

describe("i18n", () => {
  it("renders the German string by default", () => {
    render(
      <LocaleProvider initialLocale="de">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(de.chat.sendButton)).toBeInTheDocument();
  });

  it("renders the English string when initialised with locale=en", () => {
    render(
      <LocaleProvider initialLocale="en">
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText(en.chat.sendButton)).toBeInTheDocument();
  });

  it("has an identical key structure in both dictionaries", () => {
    const flatten = (obj: object, prefix = ""): string[] =>
      Object.entries(obj).flatMap(([key, value]) =>
        typeof value === "object" && value !== null
          ? flatten(value, `${prefix}${key}.`)
          : [`${prefix}${key}`],
      );
    expect(flatten(de).sort()).toEqual(flatten(en).sort());
  });
});
