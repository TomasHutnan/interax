import { toast } from "@/components/ui/toast";
import { trRaw } from "./i18n";

export type PhraseGroup = "photo" | "voice" | "interactions";

/** How long each light-hearted phrase stays on screen. */
export const PHRASE_INTERVAL_MS = 5000;

/** The phrases of a `loading.<group>` message group, in a random order. */
export function shuffledPhrases(group: PhraseGroup): string[] {
  const raw = trRaw(`loading.${group}`);
  const phrases = Object.values(
    raw && typeof raw === "object" ? (raw as Record<string, string>) : {},
  );
  for (let i = phrases.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [phrases[i], phrases[j]] = [phrases[j], phrases[i]];
  }
  return phrases;
}

/**
 * Like `toast.promise`, but while loading the description cycles through playful phrases.
 * The title stays factual so it's always clear what is happening.
 */
export function phraseToast<T>(
  promise: Promise<T>,
  opts: {
    group: PhraseGroup;
    loading: string;
    success: string;
    error: (err: unknown) => string;
  },
): Promise<T> {
  const phrases = shuffledPhrases(opts.group);
  let i = 0;
  const id = toast.add({
    type: "loading",
    title: opts.loading,
    description: phrases[0],
    timeout: 0,
  });
  const timer = setInterval(() => {
    i = (i + 1) % Math.max(phrases.length, 1);
    toast.update(id, { description: phrases[i] });
  }, PHRASE_INTERVAL_MS);

  return promise.then(
    (value) => {
      clearInterval(timer);
      toast.update(id, {
        type: "success",
        title: opts.success,
        description: undefined,
        timeout: 5000,
      });
      return value;
    },
    (err) => {
      clearInterval(timer);
      toast.update(id, {
        type: "error",
        title: opts.error(err),
        description: undefined,
        timeout: 5000,
      });
      throw err;
    },
  );
}
