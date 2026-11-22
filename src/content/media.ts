import type { SavedMedia } from '../types';

function mediaUrl(value?: string | null) {
  if (!value) return;
  try {
    const url = new URL(value, document.baseURI);
    if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
  } catch {
    // Ignore malformed or temporary media URLs.
  }
}

export function collectPageMedia(snapshotHtml = ''): SavedMedia[] {
  const media: SavedMedia[] = [];
  const urls = new Set<string>();
  const add = (kind: SavedMedia['kind'], url: string | undefined, label?: string, poster?: string) => {
    if (!url || urls.has(url)) return;
    urls.add(url);
    media.push({ kind, url, label: label?.trim().slice(0, 250) || undefined, poster });
  };
  const meta = (key: string) => document.querySelector<HTMLMetaElement>(`meta[property="${key}"],meta[name="${key}"]`)?.content;

  for (const element of Array.from(document.querySelectorAll<HTMLMediaElement>('video, audio')).slice(0, 12)) {
    const kind = element.tagName === 'VIDEO' ? 'video' : 'audio';
    const source = [element.currentSrc, element.getAttribute('src'),
      ...Array.from(element.querySelectorAll('source[src]'), (item) => item.getAttribute('src'))]
      .map(mediaUrl).find(Boolean);
    const label = element.getAttribute('aria-label') || element.title;
    add(kind, source, label, kind === 'video' ? mediaUrl(element.getAttribute('poster')) : undefined);
    if (!source && kind === 'video') add('image', mediaUrl(element.getAttribute('poster')), label);
  }
  if (meta('og:video:type') !== 'text/html') {
    add('video', mediaUrl(meta('og:video:secure_url') || meta('og:video')),
      document.title, mediaUrl(meta('og:image')));
  }
  add('audio', mediaUrl(meta('og:audio:secure_url') || meta('og:audio')), document.title);
  add('image', mediaUrl(meta('og:image') || meta('twitter:image')), document.title);

  for (const kind of ['video', 'audio'] as const) {
    if (media.some((item) => item.kind === kind && !/\.(?:m3u8|mpd)$/i.test(new URL(item.url).pathname))) continue;
    const extension = kind === 'video' ? /\.(?:mp4|webm|m4v)$/i : /\.(?:mp3|m4a|wav|ogg|aac)$/i;
    const link = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]')).find((anchor) => {
      const url = mediaUrl(anchor.getAttribute('href'));
      return url && extension.test(new URL(url).pathname);
    });
    if (link) add(kind, mediaUrl(link.getAttribute('href')), link.textContent || document.title);
  }

  const snapshot = document.createElement('template');
  snapshot.innerHTML = snapshotHtml;
  const inlineImages = snapshot.content.querySelectorAll<HTMLImageElement>('img');
  for (const image of [...inlineImages, ...document.images]) {
    if (media.length >= 100) break;
    const url = mediaUrl(image.getAttribute('data-src') || image.getAttribute('data-original'))
      || mediaUrl(image.currentSrc || image.getAttribute('src'));
    add('image', url, image.alt || image.title);
  }
  for (const element of snapshot.content.querySelectorAll<HTMLElement>('[style]')) {
    if (media.length >= 100) break;
    for (const [, url] of element.style.backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)) {
      add('image', mediaUrl(url));
    }
  }
  return media;
}
