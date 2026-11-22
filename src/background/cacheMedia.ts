import { getCachedMedia, saveCachedMedia } from '../services/db';
import type { CapturedPage, SavedMedia } from '../types';

const ASSET_LIMIT = 48 * 1024 * 1024;
const inFlight = new Set<string>();

function publicMediaUrl(raw: string) {
  try {
    const url = new URL(raw);
    const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        !hostname.includes('.') || /^(?:\d+\.){3}\d+$/.test(hostname) ||
        /\.(?:localhost|local|internal|test|lan)$/.test(hostname)) return;
    return url;
  } catch {
    // Invalid media URL.
  }
}

function mediaType(asset: SavedMedia, header: string, pathname: string) {
  const type = header.split(';')[0].trim().toLowerCase();
  if (type.startsWith(`${asset.kind}/`)) return type;
  if (type && type !== 'application/octet-stream' && type !== 'binary/octet-stream') return;
  const extension = pathname.split('.').pop()?.toLowerCase();
  const known: Record<string, string> = {
    jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
    svg: 'image/svg+xml', webp: 'image/webp', avif: 'image/avif',
    mp4: 'video/mp4', webm: 'video/webm', m4v: 'video/mp4',
    mp3: 'audio/mpeg', m4a: 'audio/mp4', wav: 'audio/wav', ogg: 'audio/ogg',
  };
  const guessed = extension && known[extension];
  if (guessed && guessed.startsWith(`${asset.kind}/`)) return guessed;
}

async function downloadAsset(asset: SavedMedia, signal: AbortSignal): Promise<Blob | undefined> {
  const url = publicMediaUrl(asset.url);
  if (!url || /\.(?:m3u8|mpd)$/i.test(url.pathname)) return;
  const response = await fetch(url, {
    credentials: 'omit',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    cache: 'force-cache',
    signal,
  });
  const type = mediaType(asset, response.headers.get('content-type') || '', url.pathname);
  if (!response.ok || response.status === 206 || !response.body || !type ||
      Number(response.headers.get('content-length')) > ASSET_LIMIT) {
    await response.body?.cancel();
    return;
  }

  const reader = response.body.getReader();
  const chunks: ArrayBuffer[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > ASSET_LIMIT) return;
      chunks.push(new Uint8Array(value).buffer);
    }
    if (size) return new Blob(chunks, { type });
  } finally {
    await reader.cancel().catch(() => {});
  }
}

export async function cachePageMedia(page: CapturedPage) {
  if (!page.media?.length) return;
  const cached = new Set((await getCachedMedia(page.id)).map(({ url }) => url));
  const assets = new Map<string, SavedMedia>();
  for (const asset of page.media) {
    assets.set(asset.url, asset);
    if (asset.poster && !assets.has(asset.poster)) {
      assets.set(asset.poster, { kind: 'image', url: asset.poster });
    }
  }

  const deadline = AbortSignal.timeout(28_000);
  const pending = [...assets.values()].filter(({ url }) => !cached.has(url));
  // Start images and players in parallel so large downloads don't block inline visuals.
  await Promise.all(Array.from({ length: 5 }, async () => {
    while (pending.length && !deadline.aborted) {
      const asset = pending.shift()!;
      const key = JSON.stringify([page.id, page.capturedAt, asset.url]);
      if (inFlight.has(key)) continue;
      inFlight.add(key);
      try {
        const blob = await downloadAsset(asset, deadline);
        if (blob) await saveCachedMedia(page.id, page.capturedAt, asset.url, blob);
      } catch {
        // Media availability must not affect the saved page.
      } finally {
        inFlight.delete(key);
      }
    }
  }));
}
