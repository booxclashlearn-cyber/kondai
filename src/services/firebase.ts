import { initializeApp } from 'firebase/app';
import { CustomProvider, initializeAppCheck } from 'firebase/app-check';
import { getAI, getGenerativeModel, GoogleAIBackend, InferenceMode, type OnDeviceParams } from 'firebase/ai';
import { LocalModelStatus } from '../types';
import { saveCapturedSummary, type ResearchContext } from './db';
import { summarizeSavedText } from './localPageAI';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'DEMO_API_KEY',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'demo.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'demo-project',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'demo.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '000000000000',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:000:web:000',
};

export const app = initializeApp(firebaseConfig);

if (import.meta.env.MODE === 'extension-debug') {
  const debugToken = import.meta.env.VITE_FIREBASE_APPCHECK_DEBUG_TOKEN;
  (globalThis as typeof globalThis & { FIREBASE_APPCHECK_DEBUG_TOKEN?: string | boolean })
    .FIREBASE_APPCHECK_DEBUG_TOKEN = !debugToken || debugToken === 'true' ? true : debugToken;

  initializeAppCheck(app, {
    // The SDK exchanges the debug token directly. This provider loads no remote scripts.
    provider: new CustomProvider({
      getToken: async () => { throw new Error('Firebase App Check debug mode is required.'); },
    }),
  });
}

export const ai = getAI(app, { backend: new GoogleAIBackend() });

const textPromptOptions = {
  expectedInputs: [{ type: 'text', languages: ['en'] }],
  expectedOutputs: [{ type: 'text', languages: ['en'] }],
} satisfies NonNullable<OnDeviceParams['createOptions']>;

interface BrowserLanguageModel {
  availability(options: typeof textPromptOptions): Promise<string>;
  create(options: typeof textPromptOptions & {
    monitor?: (monitor: EventTarget) => void;
    signal?: AbortSignal;
  }): Promise<{ destroy(): void }>;
}

function getLanguageModel() {
  return (globalThis as typeof globalThis & { LanguageModel?: BrowserLanguageModel }).LanguageModel;
}

/**
 * Check Chrome's built-in Gemini Nano availability
 */
export async function checkLocalNanoAvailability(): Promise<LocalModelStatus> {
  try {
    const lm = getLanguageModel();
    if (typeof lm?.availability !== 'function' || typeof lm.create !== 'function') return 'unsupported';
    const status = await lm.availability(textPromptOptions);
    if (status === 'available' || status === 'readily') return 'readily';
    if (status === 'downloading') return 'downloading';
    if (status === 'downloadable' || status === 'after-download') return 'downloadable';
    return status === 'unavailable' || status === 'no' ? 'unavailable' : 'unknown';
  } catch {
    return 'unknown';
  }
}

export async function downloadLocalNano(onProgress: (percent: number) => void) {
  const lm = getLanguageModel();
  if (!lm) throw new Error('Chrome’s Prompt API is unavailable.');

  // Start in the click handler's activation window. Chrome manages the download.
  const session = await lm.create({
    ...textPromptOptions,
    monitor(monitor) {
      monitor.addEventListener('downloadprogress', (event) => {
        const { loaded } = event as ProgressEvent;
        onProgress(Math.round(Math.min(1, Math.max(0, loaded)) * 100));
      });
    },
  });
  session.destroy();
}

export interface HybridResponse {
  text: string;
  inferenceSource: 'on-device' | 'cloud';
}

async function tryQuickSummary(excerpt: string, requestSignal: AbortSignal) {
  const controller = new AbortController();
  const signal = AbortSignal.any([requestSignal, controller.signal]);
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const aborted = new Promise<undefined>((resolve) => {
      if (signal.aborted) resolve(undefined);
      else signal.addEventListener('abort', () => resolve(undefined), { once: true });
    });
    return await Promise.race([summarizeSavedText(excerpt.slice(0, 2400), signal).catch(() => undefined), aborted]);
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Executes a research prompt using Firebase AI Logic, with Chrome's Prompt API on-device.
 * - Online requests use Cloud Gemini
 * - Offline requests use Gemini Nano
 */
export async function askHybridAI(params: {
  question: string;
  contextText: string;
  historyText: string;
  latestPageSummary?: ResearchContext['latestPageSummary'];
}): Promise<HybridResponse> {

  const prompt = `You are kondai, an offline-capable personal web research assistant.
Answer the user's question concisely using the 24-hour browsed page excerpts and recent conversation history below.
For page summaries, use the page excerpts supplied below and identify the page by title.
If the answer isn't in the saved pages, say so clearly.

=== RECENT 24H BROWSED PAGES ===
${params.contextText || '(No pages captured yet in the last 24 hours.)'}

=== RECENT CONVERSATION ===
${params.historyText || '(Start of conversation)'}

=== USER QUESTION ===
${params.question}`;

  const { latestPageSummary } = params;
  if (!navigator.onLine && latestPageSummary?.summary) {
    return {
      text: `${latestPageSummary.title}\n\n${latestPageSummary.summary}`,
      inferenceSource: 'on-device',
    };
  }

  const controller = new AbortController();
  const { signal } = controller;
  let inferenceSource: HybridResponse['inferenceSource'] = navigator.onLine ? 'cloud' : 'on-device';
  const localSummaryTimeout = 60_000;
  let timeout = setTimeout(() => controller.abort(),
    inferenceSource === 'on-device' && latestPageSummary ? localSummaryTimeout : 60_000);
  let text: string;
  try {
    const response = (async () => {
      if (inferenceSource === 'cloud') {
        try {
          const model = getGenerativeModel(ai, {
            mode: InferenceMode.ONLY_IN_CLOUD,
            inCloudParams: { model: 'gemini-3.5-flash-lite' },
          });
          return (await model.generateContent(prompt, { signal })).response.text();
        } catch (error) {
          if (navigator.onLine || signal.aborted) throw error;
          inferenceSource = 'on-device';
          if (latestPageSummary) {
            clearTimeout(timeout);
            timeout = setTimeout(() => controller.abort(), localSummaryTimeout);
          }
        }
      }
      if (latestPageSummary?.summary) return `${latestPageSummary.title}\n\n${latestPageSummary.summary}`;
      if (latestPageSummary) {
        const summary = await tryQuickSummary(latestPageSummary.excerpt, signal);
        if (summary) return summary;
      }
      signal.throwIfAborted();
      if (await checkLocalNanoAvailability() !== 'readily') {
        throw new Error('Offline AI needs Gemini Nano. See Gemini Nano setup above the chat.');
      }
      signal.throwIfAborted();
      const model = getGenerativeModel(ai, {
        mode: InferenceMode.ONLY_ON_DEVICE,
        onDeviceParams: { createOptions: { ...textPromptOptions, signal } },
      });
      const localPrompt = latestPageSummary
        ? `Summarize the following saved text in 2–3 short sentences. Use only the supplied text.\n\nTitle: ${latestPageSummary.title}\n\n${latestPageSummary.excerpt.slice(0, 1600)}`
        : prompt;
      return (await model.generateContent(localPrompt)).response.text();
    })();
    const deadline = new Promise<never>((_, reject) => {
      signal.addEventListener('abort', () => {
        const model = inferenceSource === 'on-device' ? 'Gemini Nano' : 'Cloud Gemini';
        reject(new Error(`${model} took too long to respond. ${latestPageSummary && inferenceSource === 'on-device'
          ? 'No model-generated summary is saved for this page yet.'
          : 'Try again.'}`));
      }, { once: true });
    });
    text = (await Promise.race([response, deadline])).trim();
    if (!text) {
      throw new Error('AI returned an empty reply. Try asking again.');
    }
  } finally {
    clearTimeout(timeout);
    controller.abort();
  }

  if (inferenceSource === 'on-device' && latestPageSummary && !latestPageSummary.summary) {
    void saveCapturedSummary(latestPageSummary.id, latestPageSummary.capturedAt, text, latestPageSummary.videoSource).catch(() => {});
  }
  return { text, inferenceSource };
}
