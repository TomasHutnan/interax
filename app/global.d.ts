import type { Locale } from "@/lib/preferences";
import type { Messages } from "@/lib/i18n";

// Type-checks `useTranslations` keys against the English messages.
declare module "next-intl" {
    interface AppConfig {
        Locale: Locale;
        Messages: Messages;
    }
}
