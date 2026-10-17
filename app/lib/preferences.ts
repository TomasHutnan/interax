/**
 * User preferences (theme, background, language). The source of truth is an attribute on <html>,
 * set before first paint by PREFERENCES_SCRIPT (no flash) and updated by the hooks in
 * lib/hooks/use-preferences.ts, which also persist to localStorage.
 *
 * No "use client" here: the root layout (a server component) needs the script string.
 */

export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

export const BACKGROUNDS = ["ecg", "lines", "waves", "plain"] as const;
export type Background = (typeof BACKGROUNDS)[number];
export const DEFAULT_BACKGROUND: Background = "plain";

export const LOCALES = ["en", "cs", "sk", "uk"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
/** Shown in their own language, so anyone can find theirs. */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  cs: "Čeština",
  sk: "Slovenčina",
  uk: "Українська",
};

export const PREFERENCE_KEYS = {
  theme: "interax-theme",
  background: "interax-bg",
  locale: "interax-locale",
} as const;
export const PREFERENCES_EVENT = "interax-preferences";

/**
 * Inlined into <head>: applies the stored preferences before the page is painted.
 * Theme falls back to the OS setting.
 */
export const PREFERENCES_SCRIPT = `(function(){try{
var d=document.documentElement,s=localStorage;
var t=s.getItem(${JSON.stringify(PREFERENCE_KEYS.theme)});
if(${JSON.stringify(THEMES)}.indexOf(t)<0)t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
d.classList.toggle("dark",t==="dark");d.style.colorScheme=t;
var b=s.getItem(${JSON.stringify(PREFERENCE_KEYS.background)});
d.dataset.bg=${JSON.stringify(BACKGROUNDS)}.indexOf(b)<0?${JSON.stringify(DEFAULT_BACKGROUND)}:b;
var l=s.getItem(${JSON.stringify(PREFERENCE_KEYS.locale)});
if(${JSON.stringify(LOCALES)}.indexOf(l)>=0)d.lang=l;
}catch(e){}})();`;
