import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/toast";
import { I18nProvider } from "@/components/contexts/i18n";
import { DEFAULT_BACKGROUND, PREFERENCES_SCRIPT } from "@/lib/preferences";

const inter = Inter({
  subsets: ["latin", "latin-ext", "cyrillic"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "InteraX - MVP",
  description: "InteraX drug interaction checker",
};

export default function Layout({ children }: LayoutProps<"/">) {
  // The inline script changes class / lang / data-bg / style before paint, hence suppressHydrationWarning.
  return (
    <html
      lang={"en"}
      data-bg={DEFAULT_BACKGROUND}
      suppressHydrationWarning
      className={cn("h-full", "antialiased", "font-sans", inter.variable)}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: PREFERENCES_SCRIPT }} />
      </head>
      <body>
        <div className={"app-bg"} aria-hidden />
        <I18nProvider>
          {children}
          <Toaster />
        </I18nProvider>
      </body>
    </html>
  );
}
