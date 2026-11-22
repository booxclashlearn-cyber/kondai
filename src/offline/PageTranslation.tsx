import { useEffect, useRef, useState } from 'react';
import type { CapturedPage } from '../types';

type LanguagePair = { sourceLanguage: string; targetLanguage: string };
type ChromeTranslator = {
  availability(pair: LanguagePair): Promise<string>;
  create(options: LanguagePair & { signal: AbortSignal; monitor: (monitor: EventTarget) => void }): Promise<{
    translate(text: string, options: { signal: AbortSignal }): Promise<string>;
    destroy(): void;
  }>;
};

export default function PageTranslation({ page }: { page: CapturedPage }) {
  const [source, setSource] = useState(page.language?.split('-')[0] || 'en');
  const [target, setTarget] = useState(source === 'en' ? 'es' : 'en');
  const [translation, setTranslation] = useState('');
  const [translatedLanguage, setTranslatedLanguage] = useState('');
  const [status, setStatus] = useState('');
  const [pending, setPending] = useState(false);
  const current = useRef<AbortController | null>(null);
  useEffect(() => () => current.current?.abort(), []);

  const translate = async (event: React.FormEvent) => {
    event.preventDefault();
    const Translator = (globalThis as typeof globalThis & { Translator?: ChromeTranslator }).Translator;
    if (!Translator) {
      setStatus('Chrome’s on-device Translator is unavailable here.');
      return;
    }
    const pair = { sourceLanguage: source.trim().toLowerCase(), targetLanguage: target.trim().toLowerCase() };
    if (pair.sourceLanguage === pair.targetLanguage) {
      setStatus('Choose a different target language.');
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    current.current = controller;
    setPending(true);
    setTranslation('');
    setStatus('Checking language pack…');
    const timeout = setTimeout(() => controller.abort(new Error('Translation timed out. Try again.')), 180_000);
    try {
      const available = await Translator.availability(pair);
      if (available === 'unavailable') throw new Error('Chrome does not support this language pair.');
      signal.throwIfAborted();
      const translator = await Translator.create({
        ...pair,
        signal,
        monitor(monitor) {
          monitor.addEventListener('downloadprogress', (event) => {
            if (!signal.aborted) setStatus(`Preparing language pack… ${Math.round((event as ProgressEvent).loaded * 100)}%`);
          });
        },
      });
      try {
        setStatus('Translating saved page…');
        setTranslatedLanguage(pair.targetLanguage);
        const parts = page.cleanText.match(/[\s\S]{1,1000}(?:\s|$)|[\s\S]{1,1000}/g) || [];
        const translated: string[] = [];
        for (const [index, part] of parts.entries()) {
          translated.push(await translator.translate(part, { signal }));
          signal.throwIfAborted();
          setStatus(`Translating saved page… ${index + 1}/${parts.length}`);
        }
        setTranslation(translated.join('\n\n'));
        setStatus('');
      } finally {
        if (!signal.aborted) translator.destroy();
      }
    } catch (error) {
      if (current.current !== controller) return;
      const reason = signal.aborted ? signal.reason : error;
      setStatus(!navigator.onLine && !signal.aborted
        ? 'Chrome could not translate offline. Open this language pair while connected to prepare its pack.'
        : reason instanceof Error ? reason.message : String(reason));
    } finally {
      clearTimeout(timeout);
      if (current.current === controller) {
        current.current = null;
        setPending(false);
      }
    }
  };

  return (
    <>
      <form className="translation-form" onSubmit={translate}>
        <label>From <input className="input" value={source} onChange={(event) => setSource(event.target.value)} required disabled={pending} /></label>
        <label>To <input className="input" value={target} onChange={(event) => setTarget(event.target.value)} required disabled={pending} /></label>
        <button className="btn" type="submit" disabled={pending}>Translate</button>
      </form>
      {status && <p className="reader-status" role="status">{status}</p>}
      <div className="translation-columns">
        <section><h2>Original text</h2><p>{page.cleanText}</p></section>
        {translation && <section lang={translatedLanguage}><h2>Translation</h2><p>{translation}</p></section>}
      </div>
    </>
  );
}
