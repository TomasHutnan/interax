"use client";
import { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { useLocalePreference } from "@/lib/hooks/use-preferences";
import { MESSAGES, setGlobalLocale, TIME_ZONE } from "@/lib/i18n";

/**
 * Client-side i18n: the language is a per-device preference (localStorage), not part of the URL,
 * so pages stay static. The server renders English; the stored language applies right after hydration.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale] = useLocalePreference();
  setGlobalLocale(locale);

  return (
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale]}
      timeZone={TIME_ZONE}
    >
      {children}
    </NextIntlClientProvider>
  );
}
