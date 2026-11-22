import { openDB, DBSchema, IDBPDatabase } from 'idb';
import { CapturedPage, ChatMessage, type SourceExcerpt, TTL_24_HOURS_MS } from '../types';

interface ChronoVaultDB extends DBSchema {
  pages: {
    key: string;
    value: CapturedPage;
    indexes: {
      'by-url': string;
      'by-expires': number;
    };
  };
  messages: {
    key: string;
    value: ChatMessage;
    indexes: {
      'by-expires': number;
      'by-created': number;
    };
  };
  media: {
    key: [string, string];
    value: { pageId: string; url: string; blob: Blob };
    indexes: { 'by-page': string };
  };
}

const DB_NAME = 'chronovault-24h-db';
const DB_VERSION = 2;
const MEDIA_PAGE_LIMIT = 96 * 1024 * 1024;
const MEDIA_VAULT_LIMIT = 512 * 1024 * 1024;

let dbPromise: Promise<IDBPDatabase<ChronoVaultDB>> | null = null;

export function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<ChronoVaultDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('pages')) {
          const pageStore = db.createObjectStore('pages', { keyPath: 'id' });
          pageStore.createIndex('by-url', 'url', { unique: true });
          pageStore.createIndex('by-expires', 'expiresAt');
        }
        if (!db.objectStoreNames.contains('messages')) {
          const msgStore = db.createObjectStore('messages', { keyPath: 'id' });
          msgStore.createIndex('by-expires', 'expiresAt');
          msgStore.createIndex('by-created', 'createdAt');
        }
        if (!db.objectStoreNames.contains('media')) {
          const mediaStore = db.createObjectStore('media', { keyPath: ['pageId', 'url'] });
          mediaStore.createIndex('by-page', 'pageId');
        }
      },
      blocking() {
        void dbPromise?.then((db) => db.close());
        dbPromise = null;
      },
    });
  }
  return dbPromise;
}

export async function getCachedMedia(pageId: string) {
  const db = await getDB();
  return db.getAllFromIndex('media', 'by-page', pageId);
}

export async function saveCachedMedia(pageId: string, capturedAt: number, url: string, blob: Blob) {
  const db = await getDB();
  const tx = db.transaction(['pages', 'media'], 'readwrite');
  const page = await tx.objectStore('pages').get(pageId);
  if (page?.capturedAt === capturedAt && (page.pinned || page.expiresAt > Date.now())) {
    const store = tx.objectStore('media');
    const items = await store.getAll();
    let pageBytes = 0;
    let totalBytes = 0;
    for (const item of items) {
      if (item.pageId === pageId && item.url === url) continue;
      totalBytes += item.blob.size;
      if (item.pageId === pageId) pageBytes += item.blob.size;
    }
    if (pageBytes + blob.size <= MEDIA_PAGE_LIMIT && totalBytes + blob.size <= MEDIA_VAULT_LIMIT) {
      await store.put({ pageId, url, blob });
    }
  }
  await tx.done;
}

export function normalizeUrl(rawUrl: string): string {
  try {
    const u = new URL(rawUrl);
    u.hash = '';
    return u.toString();
  } catch {
    return rawUrl;
  }
}

export function chunkText(text: string, maxChars = 800): string[] {
  const clean = text.replace(/\s+/g, ' ').trim();
  const chunks: string[] = [];
  for (let i = 0; i < clean.length; i += maxChars) {
    chunks.push(clean.slice(i, i + maxChars));
  }
  return chunks.slice(0, 25); // cap per page for lean storage
}

export async function saveCapturedPage(input: {
  url: string;
  title: string;
  cleanText: string;
  snapshotHtml: string;
  language?: string;
  video?: CapturedPage['video'];
  media?: CapturedPage['media'];
}): Promise<CapturedPage> {
  const db = await getDB();
  const url = normalizeUrl(input.url);
  const now = Date.now();
  const page: CapturedPage = {
    id: url,
    url,
    title: input.title || url,
    cleanText: input.cleanText,
    snapshotHtml: input.snapshotHtml,
    language: input.language,
    video: input.video,
    media: input.media,
    chunks: chunkText(input.cleanText),
    capturedAt: now,
    expiresAt: now + TTL_24_HOURS_MS,
  };
  const tx = db.transaction('pages', 'readwrite');
  const previous = await tx.store.get(url);
  page.pinned = previous?.pinned;
  if (previous?.cleanText === page.cleanText) page.summary = previous.summary;
  if (page.video && previous?.video?.captions && previous.cleanText === page.cleanText) {
    page.video.captions = previous.video.captions;
  }
  if (page.video && previous?.video && previous.cleanText === page.cleanText &&
      previous.video.description === page.video.description) {
    page.video.summary = previous.video.summary;
  }
  await tx.store.put(page);
  await tx.done;
  return page;
}

export async function getPageByUrl(rawUrl: string): Promise<CapturedPage | undefined> {
  const db = await getDB();
  const url = normalizeUrl(rawUrl);
  const page = await db.get('pages', url);
  if (!page || (!page.pinned && page.expiresAt <= Date.now())) return undefined;
  return page;
}

export async function setPagePinned(id: string, pinned: boolean): Promise<CapturedPage | undefined> {
  const db = await getDB();
  const tx = db.transaction('pages', 'readwrite');
  const page = await tx.store.get(id);
  if (page && (page.pinned || page.expiresAt > Date.now())) {
    page.pinned = pinned;
    await tx.store.put(page);
  }
  await tx.done;
  return page && (page.pinned || page.expiresAt > Date.now()) ? page : undefined;
}

export async function saveCapturedSummary(id: string, capturedAt: number, summary: string, videoSource?: CapturedPage['video']) {
  if (!summary.trim()) return;
  const db = await getDB();
  const tx = db.transaction('pages', 'readwrite');
  const page = await tx.store.get(id);
  if (page?.capturedAt === capturedAt && (page.pinned || page.expiresAt > Date.now())) {
    const text = summary.slice(0, 2000);
    if (!videoSource) {
      await tx.store.put({ ...page, summary: text });
    } else if (page.video && page.video.description === videoSource.description && page.video.captions === videoSource.captions) {
      await tx.store.put({ ...page, video: { ...page.video, summary: text } });
    }
  }
  await tx.done;
}

export async function saveVideoCaptions(id: string, capturedAt: number, captions: string) {
  const db = await getDB();
  const tx = db.transaction('pages', 'readwrite');
  const page = await tx.store.get(id);
  if (page?.video && page.capturedAt === capturedAt && (page.pinned || page.expiresAt > Date.now())) {
    const text = captions.slice(0, 12000);
    await tx.store.put({ ...page, video: {
      ...page.video, captions: text, summary: page.video.captions === text ? page.video.summary : undefined,
    } });
  }
  await tx.done;
}

export async function getAllValidPages(): Promise<CapturedPage[]> {
  const db = await getDB();
  const now = Date.now();
  const all = await db.getAll('pages');
  return all
    .filter((p) => p.pinned || p.expiresAt > now)
    .sort((a, b) => b.capturedAt - a.capturedAt);
}

export async function saveChatMessage(
  msg: Omit<ChatMessage, 'id' | 'createdAt' | 'expiresAt'>
): Promise<ChatMessage> {
  const db = await getDB();
  const now = Date.now();
  const full: ChatMessage = {
    ...msg,
    id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: now,
    expiresAt: now + TTL_24_HOURS_MS,
  };
  await db.put('messages', full);
  return full;
}

export async function getValidChatMessages(): Promise<ChatMessage[]> {
  const db = await getDB();
  const now = Date.now();
  const all = await db.getAllFromIndex('messages', 'by-created');
  return all.filter((m) => m.expiresAt > now);
}

export async function getValidChatMessage(id: string): Promise<ChatMessage | undefined> {
  const db = await getDB();
  const message = await db.get('messages', id);
  return message && message.expiresAt > Date.now() ? message : undefined;
}

export async function purgeExpiredRecords(): Promise<{ pagesDeleted: number; messagesDeleted: number }> {
  const db = await getDB();
  const now = Date.now();
  let pagesDeleted = 0;
  let messagesDeleted = 0;

  const txPages = db.transaction(['pages', 'media'], 'readwrite');
  const media = txPages.objectStore('media');
  let cursor = await txPages.objectStore('pages').index('by-expires').openCursor(IDBKeyRange.upperBound(now));
  while (cursor) {
    if (!cursor.value.pinned) {
      const keys = await media.index('by-page').getAllKeys(cursor.value.id);
      await Promise.all(keys.map((key) => media.delete(key)));
      await cursor.delete();
      pagesDeleted++;
    }
    cursor = await cursor.continue();
  }
  await txPages.done;

  const txMsgs = db.transaction('messages', 'readwrite');
  let msgCursor = await txMsgs.store.index('by-expires').openCursor(IDBKeyRange.upperBound(now));
  while (msgCursor) {
    await msgCursor.delete();
    messagesDeleted++;
    msgCursor = await msgCursor.continue();
  }
  await txMsgs.done;

  return { pagesDeleted, messagesDeleted };
}

export async function purgeAllVaultData(): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(['pages', 'messages', 'media'], 'readwrite');
  await Promise.all([tx.objectStore('pages').clear(), tx.objectStore('messages').clear(), tx.objectStore('media').clear()]);
  await tx.done;
}

/**
 * Lightweight local keyword/overlap retriever for on-device Gemini Nano context windows
 */
export interface ResearchContext {
  contextText: string;
  referencedUrls: string[];
  sourceExcerpts: SourceExcerpt[];
  latestPageSummary?: {
    id: string;
    capturedAt: number;
    title: string;
    excerpt: string;
    summary?: string;
    videoSource?: NonNullable<CapturedPage['video']>;
  };
}

export function buildPageContext(items: { page: CapturedPage; text: string }[]): ResearchContext {
  return {
    contextText: items.map(({ page, text }) => `[Source: ${page.title} (${page.url})]\n${text}`).join('\n\n'),
    referencedUrls: [...new Set(items.map(({ page }) => page.url))],
    sourceExcerpts: items.map(({ page, text }) => ({ url: page.url, text })),
  };
}

export async function retrieveRelevantContext(query: string, maxChunks = 4, selection?: string | string[]): Promise<ResearchContext> {
  const savedPages = await getAllValidPages();
  const selected = typeof selection === 'string' ? [selection] : selection ?? [];
  const pages = selected.length ? savedPages.filter((page) => selected.includes(page.url)) : savedPages;
  if (pages.length < new Set(selected).size) throw new Error('A selected page has expired or was removed.');

  const wantsSummary = /\b(?:summary|summari[sz]e|recap)\b/i.test(query);
  const asksForLatest = /\b(?:last|latest|most recent|last visited|most recently (?:visited|captured))\s+(?:(?:visited|saved|captured|web)\s+)*(?:page|site|article)\b/i.test(query);
  const keywords = [...new Set(query.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 2))];
  const relevance = (text: string) => {
    const lower = text.toLowerCase();
    return keywords.filter((word) => lower.includes(word)).length;
  };
  if (selected.length > 1) {
    return buildPageContext(pages.map((page) => {
      const chunks = page.chunks.map((chunk) => ({ chunk, score: relevance(chunk) }))
        .sort((a, b) => b.score - a.score).slice(0, 2);
      return {
        page,
        text: [page.summary?.slice(0, 300), ...chunks.map(({ chunk }) => chunk)].filter(Boolean).join('\n').slice(0, 1500),
      };
    }));
  }
  if (selected.length ? wantsSummary : asksForLatest) {
    const latest = pages[0];
    if (!latest) {
      throw new Error('No pages are saved in the 24-hour vault. Enable Web Capture and visit the page while online.');
    }
    const excerpt = latest.chunks.slice(0, maxChunks).join(' ').trim()
      || latest.cleanText.slice(0, 800 * maxChunks).trim();
    if (!excerpt) {
      throw new Error('The last saved page has no readable text to summarize.');
    }
    return {
      ...buildPageContext([{ page: latest, text: excerpt }]),
      latestPageSummary: wantsSummary
        ? { id: latest.id, capturedAt: latest.capturedAt, title: latest.title, excerpt, summary: latest.summary }
        : undefined,
    };
  }
  const scored: { score: number; url: string; title: string; chunk: string }[] = [];

  for (const page of pages) {
    for (const chunk of page.chunks) {
      const score = relevance(page.title + ' ' + chunk);
      if (score > 0 || keywords.length === 0) {
        scored.push({ score, url: page.url, title: page.title, chunk });
      }
    }
  }

  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, maxChunks);

  // Fallback to most recently visited pages if no keyword matched
  if (top.length === 0 && pages.length > 0) {
    const recent = pages.slice(0, 2);
    return buildPageContext(recent.map((page) => ({ page, text: page.chunks[0] || '' })));
  }

  const referencedUrls = Array.from(new Set(top.map((t) => t.url)));
  const contextText = top
    .map((t) => `[Source: ${t.title} (${t.url})]\n${t.chunk}`)
    .join('\n\n');

  return { contextText, referencedUrls, sourceExcerpts: top.map(({ url, chunk }) => ({ url, text: chunk })) };
}
