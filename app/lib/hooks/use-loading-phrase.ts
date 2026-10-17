import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import {
  PHRASE_INTERVAL_MS,
  PhraseGroup,
  shuffledPhrases,
} from "../loading-phrases";

/** A playful phrase that changes every few seconds while `active`; null otherwise. */
export function useLoadingPhrase(
  group: PhraseGroup,
  active: boolean,
): string | null {
  const locale = useLocale();
  const [phrase, setPhrase] = useState<string | null>(null);

  useEffect(() => {
    if (!active) {
      setPhrase(null);
      return;
    }
    const phrases = shuffledPhrases(group);
    let i = 0;
    setPhrase(phrases[0] ?? null);
    const timer = setInterval(() => {
      i = (i + 1) % Math.max(phrases.length, 1);
      setPhrase(phrases[i] ?? null);
    }, PHRASE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [group, active, locale]);

  return phrase;
}
