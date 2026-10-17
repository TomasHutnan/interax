"use client";
import { useCallback, useSyncExternalStore } from "react";
import {
    Background, BACKGROUNDS, DEFAULT_BACKGROUND, DEFAULT_LOCALE, Locale, LOCALES,
    PREFERENCE_KEYS, PREFERENCES_EVENT, Theme,
} from "../preferences";

/*
 * Server snapshots are fixed (light / default background / English) so hydration always matches;
 * the real values from <html> take over right after.
 */

function subscribe(onChange: () => void) {
    window.addEventListener(PREFERENCES_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
        window.removeEventListener(PREFERENCES_EVENT, onChange);
        window.removeEventListener("storage", onChange);
    };
}

function store(key: string, value: string) {
    try {
        localStorage.setItem(key, value);
    } catch {
        // private mode / storage full: the choice just isn't remembered
    }
    window.dispatchEvent(new Event(PREFERENCES_EVENT));
}

function oneOf<T extends string>(values: readonly T[], value: string | null | undefined, fallback: T): T {
    return (values as readonly string[]).includes(value ?? "") ? value as T : fallback;
}

const html = () => document.documentElement;

export function useTheme() {
    const theme = useSyncExternalStore<Theme>(
        subscribe,
        () => html().classList.contains("dark") ? "dark" : "light",
        () => "light",
    );
    const setTheme = useCallback((value: Theme) => {
        html().classList.toggle("dark", value === "dark");
        html().style.colorScheme = value;
        store(PREFERENCE_KEYS.theme, value);
    }, []);
    return [theme, setTheme] as const;
}

export function useBackground() {
    const background = useSyncExternalStore<Background>(
        subscribe,
        () => oneOf(BACKGROUNDS, html().dataset.bg, DEFAULT_BACKGROUND),
        () => DEFAULT_BACKGROUND,
    );
    const setBackground = useCallback((value: Background) => {
        html().dataset.bg = value;
        store(PREFERENCE_KEYS.background, value);
    }, []);
    return [background, setBackground] as const;
}

export function useLocalePreference() {
    const locale = useSyncExternalStore<Locale>(
        subscribe,
        () => oneOf(LOCALES, html().lang, DEFAULT_LOCALE),
        () => DEFAULT_LOCALE,
    );
    const setLocale = useCallback((value: Locale) => {
        html().lang = value;
        store(PREFERENCE_KEYS.locale, value);
    }, []);
    return [locale, setLocale] as const;
}
