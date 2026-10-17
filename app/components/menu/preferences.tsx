"use client";
import { Check, Languages, Moon, Palette, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "cn";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import {
  Background,
  BACKGROUNDS,
  LOCALE_NAMES,
  LOCALES,
} from "@/lib/preferences";
import {
  useBackground,
  useLocalePreference,
  useTheme,
} from "@/lib/hooks/use-preferences";

/**
 * Background, language and light/dark switchers, shown in the headers.
 */
export default function Preferences({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center", className)}>
      <BackgroundSwitcher />
      <LanguageSwitcher />
      <ThemeSwitcher />
    </div>
  );
}

function BackgroundSwitcher() {
  const t = useTranslations("preferences");
  const [background, setBackground] = useBackground();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant={"ghost"}
            size={"icon-sm"}
            aria-label={t("background")}
            title={t("background")}
          />
        }
      >
        <Palette />
      </DropdownMenuTrigger>
      <DropdownMenuContent align={"end"} className={"w-auto min-w-40"}>
        {BACKGROUNDS.map((b) => (
          <DropdownMenuItem key={b} onClick={() => setBackground(b)}>
            <BackgroundSwatch background={b} />
            {t(`backgrounds.${b}`)}
            {b === background && <Check className={"ml-auto"} />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** A tiny preview of the design, using the same CSS as the real background. */
function BackgroundSwatch({ background }: { background: Background }) {
  return (
    <span
      data-bg={background}
      className={
        "bg-swatch relative size-5 shrink-0 overflow-hidden border border-border bg-background"
      }
      aria-hidden
    >
      <span className={"app-bg"} />
    </span>
  );
}

function LanguageSwitcher() {
  const t = useTranslations("preferences");
  const [locale, setLocale] = useLocalePreference();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant={"ghost"}
            size={"sm"}
            aria-label={t("language")}
            title={t("language")}
          />
        }
      >
        <Languages />
        <span className={"uppercase"}>{locale}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={"end"} className={"w-auto min-w-36"}>
        {LOCALES.map((l) => (
          <DropdownMenuItem key={l} onClick={() => setLocale(l)} lang={l}>
            <span className={"w-5 text-muted-foreground uppercase"}>{l}</span>
            {LOCALE_NAMES[l]}
            {l === locale && <Check className={"ml-auto"} />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ThemeSwitcher() {
  const t = useTranslations("preferences");
  const [theme, setTheme] = useTheme();
  const label = theme === "dark" ? t("toLight") : t("toDark");

  return (
    <Button
      variant={"ghost"}
      size={"icon-sm"}
      aria-label={label}
      title={label}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
