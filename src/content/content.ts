import { Readability } from '@mozilla/readability';
import DOMPurify from 'dompurify';
import { summarizeSavedText } from '../services/localPageAI?content-script';
import { readVideoCaptions, readVideoMetadata } from './video';
import { collectPageMedia } from './media';

let summaryController: AbortController | undefined;

async function prepareSummary(id: string, capturedAt: number, text: string) {
  summaryController?.abort();
  const controller = new AbortController();
  summaryController = controller;
  const timeout = setTimeout(() => controller.abort(), 12_000);
  try {
    const summary = await summarizeSavedText(text.slice(0, 3200), controller.signal);
    if (summary && !controller.signal.aborted) {
      await chrome.runtime.sendMessage({ type: 'CAPTURE_PAGE_SUMMARY', id, capturedAt, summary });
    }
  } catch {
    // The snapshot and text chunks were already saved.
  } finally {
    clearTimeout(timeout);
    if (summaryController === controller) summaryController = undefined;
  }
}

async function captureCurrentPage() {
  try {
    const result = await chrome.storage.local.get(['captureEnabled']);
    if (!result.captureEnabled) return { ok: false, error: 'Web Capture is off.' };

    // Skip non-HTTP pages or empty documents
    if (!['http:', 'https:'].includes(window.location.protocol)) {
      return { ok: false, error: 'Open a regular website to capture it.' };
    }

    const docClone = document.cloneNode(true) as Document;
    const reader = new Readability(docClone);
    const article = reader.parse();

    const video = readVideoMetadata();
    const cleanText = (article?.textContent || document.body?.innerText || video?.description || video?.title || '').trim();

    const plainSnapshot = document.createElement('pre');
    plainSnapshot.textContent = cleanText.slice(0, 15000);
    const rawHtml = article?.content || plainSnapshot.outerHTML;
    const snapshotHtml = DOMPurify.sanitize(rawHtml);
    const media = collectPageMedia(snapshotHtml);
    if (!cleanText && !media.length) return { ok: false, empty: true, error: 'This page has no readable text or media yet.' };

    const response = await chrome.runtime.sendMessage({
      type: 'CAPTURE_PAGE',
      payload: {
        url: window.location.href,
        title: article?.title || document.title || window.location.href,
        cleanText: cleanText.slice(0, 25000),
        snapshotHtml,
        video,
        media,
        language: document.documentElement.lang || undefined,
      },
    });
    if (response?.ok && !response.hasSummary && cleanText) {
      void prepareSummary(response.id, response.capturedAt, cleanText);
    }
    if (response?.ok && video && !response.hasCaptions) {
      void readVideoCaptions().then((captions) => {
        if (captions) return chrome.runtime.sendMessage({
          type: 'CAPTURE_VIDEO_CAPTIONS', id: response.id, capturedAt: response.capturedAt, captions,
        });
      }).catch(() => {});
    }
    return response ?? { ok: false, error: 'Kondai did not confirm the save.' };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

let captureTimer: ReturnType<typeof setTimeout>;
function scheduleCapture(retry = true) {
  clearTimeout(captureTimer);
  captureTimer = setTimeout(async () => {
    const url = location.href;
    const result = await captureCurrentPage();
    if (retry && result.empty && location.href === url) scheduleCapture(false);
  }, retry ? 1500 : 3000);
}

async function showReloadShortcut() {
  const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  if (navigation?.type !== 'reload' || !navigator.onLine || document.getElementById('kondai-reload-shortcut')) return;
  const { captureEnabled } = await chrome.storage.local.get('captureEnabled');
  if (!captureEnabled) return;

  const host = document.createElement('div');
  host.id = 'kondai-reload-shortcut';
  host.style.cssText = 'all:initial;position:fixed;bottom:16px;right:16px;z-index:2147483647';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Open Kondai';
  button.style.cssText = 'font:600 13px system-ui;color:white;background:#075985;border:1px solid #7dd3fc;border-radius:8px;padding:8px 12px;cursor:pointer';
  const shadow = host.attachShadow({ mode: 'closed' });
  shadow.append(button);
  document.documentElement.append(host);

  const dismiss = () => host.remove();
  const timeout = setTimeout(dismiss, 8_000);
  button.addEventListener('click', () => {
    void chrome.runtime.sendMessage({ type: 'OPEN_CAPTURE_PANEL' }).then((response) => {
      if (response?.ok) {
        clearTimeout(timeout);
        dismiss();
      }
    }).catch(() => {});
  });
}

scheduleCapture();
void showReloadShortcut().catch(() => {});
window.addEventListener('offline', () => {
  if (document.visibilityState === 'visible') {
    void chrome.runtime.sendMessage({ type: 'BROWSING_WENT_OFFLINE' }).catch(() => {});
  }
});
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'SCHEDULE_PAGE_CAPTURE') {
    scheduleCapture();
    return;
  }
  if (message?.type !== 'CAPTURE_CURRENT_PAGE') return;
  clearTimeout(captureTimer);
  void captureCurrentPage().then(sendResponse);
  return true;
});
