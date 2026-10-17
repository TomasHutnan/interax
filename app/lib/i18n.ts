import { createTranslator, type TranslationValues } from "next-intl";
import { DEFAULT_LOCALE, Locale, LOCALES } from "./preferences";
import auth from "@/messages/auth.json";
import doctor from "@/messages/doctor.json";
import errors from "@/messages/errors.json";
import home from "@/messages/home.json";
import interactions from "@/messages/interactions.json";
import menu from "@/messages/menu.json";
import patient from "@/messages/patient.json";
import preferences from "@/messages/preferences.json";
import toasts from "@/messages/toasts.json";

/**
 * One file per namespace in messages/, each holding all locales: `{ en: {...}, cs: {...}, ... }`.
 * English is the reference; other locales fall back to it key by key.
 */
const NAMESPACES = {
  auth,
  doctor,
  errors,
  home,
  interactions,
  menu,
  patient,
  preferences,
  toasts,
};

type Namespaces = typeof NAMESPACES;
export type Messages = { [N in keyof Namespaces]: Namespaces[N]["en"] };

type Tree = { [key: string]: string | Tree };

function withFallback(base: Tree, over: Tree | undefined): Tree {
  const out: Tree = { ...base };
  for (const [key, value] of Object.entries(over ?? {})) {
    const fallback = base[key];
    out[key] =
      typeof value === "object" && typeof fallback === "object"
        ? withFallback(fallback, value)
        : value;
  }
  return out;
}

function build(locale: Locale): Messages {
  const out: Record<string, Tree> = {};
  for (const [name, all] of Object.entries(NAMESPACES) as [
    string,
    Record<Locale, Tree>,
  ][])
    out[name] = locale === "en" ? all.en : withFallback(all.en, all[locale]);
  return out as Messages;
}

export const MESSAGES = Object.fromEntries(
  LOCALES.map((l) => [l, build(l)]),
) as Record<Locale, Messages>;

export const TIME_ZONE = "Europe/Prague";

let current: Locale = DEFAULT_LOCALE;
let translator = createTranslator({
  locale: current,
  messages: MESSAGES[current],
  timeZone: TIME_ZONE,
});

/** Called by the provider whenever the language changes. */
export function setGlobalLocale(locale: Locale) {
  if (locale === current) return;
  current = locale;
  translator = createTranslator({
    locale,
    messages: MESSAGES[locale],
    timeZone: TIME_ZONE,
  });
}

/**
 * Translation outside React components (toasts from plain functions, error messages):
 * `tr("errors.notFound")`. Inside components prefer `useTranslations`, which checks keys at compile time.
 */
export function tr(key: string, values?: TranslationValues): string {
  return (
    translator as unknown as (k: string, v?: TranslationValues) => string
  )(key, values);
}
