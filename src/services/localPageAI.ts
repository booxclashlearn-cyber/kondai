const summaryOptions = { type: 'tldr', format: 'plain-text', length: 'short' } as const;

interface PageAI {
  LanguageDetector?: {
    availability(): Promise<string>;
    create(options: { signal: AbortSignal }): Promise<{
      detect(text: string, options: { signal: AbortSignal }): Promise<{ detectedLanguage: string; confidence: number }[]>;
      destroy(): void;
    }>;
  };
  Summarizer?: {
    availability(options: typeof summaryOptions & { expectedInputLanguages: string[] }): Promise<string>;
    create(options: typeof summaryOptions & { expectedInputLanguages: string[]; signal: AbortSignal }): Promise<{
      summarize(text: string, options: { signal: AbortSignal }): Promise<string>;
      destroy(): void;
    }>;
  };
}

export async function summarizeSavedText(text: string, signal: AbortSignal): Promise<string | undefined> {
  const { LanguageDetector, Summarizer } = globalThis as typeof globalThis & PageAI;
  let language = 'en';
  try {
    if (LanguageDetector && await LanguageDetector.availability() === 'available') {
      signal.throwIfAborted();
      const detector = await LanguageDetector.create({ signal });
      try {
        const [result] = await detector.detect(text.slice(0, 1200), { signal });
        if (result && result.confidence >= 0.7 && result.detectedLanguage !== 'und') {
          language = result.detectedLanguage;
        }
      } finally {
        if (!signal.aborted) detector.destroy();
      }
    }
  } catch {
    signal.throwIfAborted();
  }

  signal.throwIfAborted();
  const options = { ...summaryOptions, expectedInputLanguages: [language] };
  if (!Summarizer || await Summarizer.availability(options) !== 'available') return;
  signal.throwIfAborted();
  const summarizer = await Summarizer.create({ ...options, signal });
  try {
    return (await summarizer.summarize(text, { signal })).trim() || undefined;
  } finally {
    if (!signal.aborted) summarizer.destroy();
  }
}
