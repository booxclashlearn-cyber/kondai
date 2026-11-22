import { saveCapturedPage, saveCapturedSummary, saveVideoCaptions, purgeExpiredRecords } from '../services/db';
import { cachePageMedia } from './cacheMedia';

const PURGE_ALARM_NAME = 'chronovault-24h-purge';
const OFFLINE_HUB = chrome.runtime.getURL('offline-reader.html');
const openingHubs = new Set<number>();

async function showOfflineHub(tab: chrome.tabs.Tab) {
  if (!tab.active || openingHubs.has(tab.windowId)) return;
  openingHubs.add(tab.windowId);
  try {
    const { captureEnabled } = await chrome.storage.local.get('captureEnabled');
    if (!captureEnabled) return;
    const tabs = await chrome.tabs.query({ windowId: tab.windowId });
    if (!tabs.some((current) => current.id === tab.id && current.active)) return;
    const existing = tabs.find(({ url, pendingUrl }) => (pendingUrl || url)?.split('?')[0] === OFFLINE_HUB);
    if (existing?.id !== undefined) {
      await chrome.tabs.update(existing.id, { active: true });
    } else {
      await chrome.tabs.create({
        windowId: tab.windowId,
        url: `${OFFLINE_HUB}?url=${encodeURIComponent(tab.url || '')}`,
      });
    }
  } finally {
    openingHubs.delete(tab.windowId);
  }
}

// Open Side Panel when user clicks the extension icon
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((err) => console.error('[kondai] SidePanel error:', err));

// Set up 15-minute alarm to purge records older than 24 hours
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(PURGE_ALARM_NAME, { periodInMinutes: 15 });
  purgeExpiredRecords().catch(console.error);
});

chrome.runtime.onStartup.addListener(() => {
  purgeExpiredRecords().catch(console.error);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === PURGE_ALARM_NAME) {
    purgeExpiredRecords()
      .then((res) => console.log('[kondai] 24h auto-purge completed:', res))
      .catch(console.error);
  }
});

// Intercept ERR_INTERNET_DISCONNECTED and redirect to our Offline Reader instead of Chrome's dinosaur
chrome.webNavigation.onErrorOccurred.addListener((details) => {
  if (details.frameId !== 0) return;

  const offlineErrors = [
    'net::ERR_INTERNET_DISCONNECTED',
    'net::ERR_NAME_NOT_RESOLVED',
    'net::ERR_NETWORK_CHANGED',
  ];

  if (offlineErrors.includes(details.error) && details.url.startsWith('http')) {
    const readerUrl = chrome.runtime.getURL(
      `offline-reader.html?url=${encodeURIComponent(details.url)}`
    );
    chrome.tabs.update(details.tabId, { url: readerUrl }).catch(console.error);
  }
});

// Single-page sites change history without loading a new content script.
chrome.webNavigation.onHistoryStateUpdated.addListener(({ tabId, frameId }) => {
  if (frameId === 0) {
    chrome.tabs.sendMessage(tabId, { type: 'SCHEDULE_PAGE_CAPTURE' }, { frameId }).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'BROWSING_WENT_OFFLINE' && sender.tab && sender.frameId === 0) {
    void showOfflineHub(sender.tab).catch(console.error);
    return;
  }
  if (message?.type === 'OPEN_CAPTURE_PANEL' && sender.tab && sender.frameId === 0) {
    // Call directly in the click message handler so Chrome can use the user gesture.
    chrome.sidePanel.open({ windowId: sender.tab.windowId })
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message?.type === 'CAPTURE_PAGE') {
    saveCapturedPage(message.payload)
      .then((saved) => {
        sendResponse({
          ok: true, id: saved.id, capturedAt: saved.capturedAt, hasSummary: Boolean(saved.summary),
          hasCaptions: Boolean(saved.video?.captions),
        });
        if (sender.tab && sender.frameId === 0) void cachePageMedia(saved).catch(console.debug);
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  if (message?.type === 'CAPTURE_PAGE_SUMMARY') {
    saveCapturedSummary(message.id, message.capturedAt, message.summary)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  if (message?.type === 'CAPTURE_VIDEO_CAPTIONS') {
    saveVideoCaptions(message.id, message.capturedAt, message.captions)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
});
