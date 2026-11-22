import { useEffect, useMemo, useState } from 'react';
import type { CapturedPage, SavedMedia } from '../types';
import { getCachedMedia } from '../services/db';

function webUrl(value: string | null | undefined, base: string) {
  if (!value) return;
  try {
    const url = new URL(value, base);
    if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
  } catch {
    // Malformed URLs cannot be loaded.
  }
}

function preparePreview(page: CapturedPage, localUrls: ReadonlyMap<string, string>) {
  const fragment = document.createElement('template');
  fragment.innerHTML = page.snapshotHtml;
  const images = new Set<string>();
  const capturedMedia = [...(page.media || [])];
  for (const image of fragment.content.querySelectorAll('img')) {
    const source = webUrl(image.getAttribute('data-src') || image.getAttribute('data-original'), page.url)
      || webUrl(image.getAttribute('src'), page.url);
    if (source) {
      const local = localUrls.get(source);
      image.setAttribute('src', local || source);
      image.setAttribute('loading', 'lazy');
      images.add(source);
      if (local) {
        image.removeAttribute('srcset');
        for (const candidate of image.closest('picture')?.querySelectorAll('source') ?? []) {
          candidate.remove();
        }
      }
    }
  }
  for (const source of fragment.content.querySelectorAll('picture > source[srcset], img[srcset]')) {
    const srcset = source.getAttribute('srcset');
    if (!srcset || srcset.startsWith('data:')) continue;
    const candidates = srcset.split(',').flatMap((entry) => {
      const [url, descriptor] = entry.trim().split(/\s+/);
      const resolved = webUrl(url, page.url);
      const urlForDisplay = resolved && (localUrls.get(resolved) || resolved);
      return urlForDisplay ? [descriptor ? `${urlForDisplay} ${descriptor}` : urlForDisplay] : [];
    });
    if (candidates.length) source.setAttribute('srcset', candidates.join(', '));
    else source.removeAttribute('srcset');
  }
  for (const element of fragment.content.querySelectorAll<HTMLElement>('[style]')) {
    const background = element.style.backgroundImage;
    if (!background.includes('url(')) continue;
    element.style.backgroundImage = background.replace(/url\(["']?([^"')]+)["']?\)/g, (original, path) => {
      const source = webUrl(path, page.url);
      if (!source) return original;
      images.add(source);
      return `url("${(localUrls.get(source) || source).replace(/"/g, '%22')}")`;
    });
  }
  for (const player of fragment.content.querySelectorAll('video, audio')) {
    const url = webUrl(player.getAttribute('src'), page.url)
      || Array.from(player.querySelectorAll('source[src]'), (source) => webUrl(source.getAttribute('src'), page.url)).find(Boolean);
    if (!url) {
      player.remove();
      continue;
    }
    player.setAttribute('src', localUrls.get(url) || url);
    player.setAttribute('controls', '');
    player.setAttribute('preload', 'none');
    player.removeAttribute('autoplay');
    const poster = webUrl(player.getAttribute('poster'), page.url);
    if (poster) player.setAttribute('poster', localUrls.get(poster) || poster);
    for (const source of player.querySelectorAll('source')) source.remove();
    images.add(url);
  }
  const media = capturedMedia.flatMap((item) => {
    const url = webUrl(item.url, page.url);
    if (!url || images.has(url)) return [];
    const poster = webUrl(item.poster, page.url);
    return [{ ...item, url: localUrls.get(url) || url, poster: poster && (localUrls.get(poster) || poster) }];
  });
  return { html: fragment.innerHTML, media };
}

function MediaItem({ item, originalUrl }: { item: SavedMedia; originalUrl?: string }) {
  const [failed, setFailed] = useState(false);
  const label = item.label || (item.kind === 'image' ? 'Page image' : item.kind === 'video' ? 'Video' : 'Audio');
  const onError = () => setFailed(true);
  if (failed) {
    return (
      <p className="reader-status">
        {label} could not load.{' '}
        {originalUrl && <a href={originalUrl} target="_blank" rel="noreferrer">Open original page</a>}
      </p>
    );
  }
  if (item.kind === 'image') return <img src={item.url} alt={label} loading="lazy" onError={onError} />;
  if (item.kind === 'audio') return <audio src={item.url} controls preload="none" aria-label={label} onError={onError} />;
  return <video src={item.url} poster={item.poster} controls playsInline preload="none" aria-label={label} onError={onError} />;
}

export default function PageMedia({ page }: { page: CapturedPage }) {
  const [localUrls, setLocalUrls] = useState<ReadonlyMap<string, string>>(() => new Map());
  useEffect(() => {
    const urls = new Map<string, string>();
    let active = true;
    const refresh = async () => {
      const entries = await getCachedMedia(page.id);
      if (!active) return;
      let changed = false;
      for (const { url, blob } of entries) {
        if (urls.has(url)) continue;
        urls.set(url, URL.createObjectURL(blob));
        changed = true;
      }
      if (changed) setLocalUrls(new Map(urls));
    };
    const refreshMedia = () => { void refresh().catch(console.debug); };
    refreshMedia();
    window.addEventListener('offline', refreshMedia);
    window.addEventListener('focus', refreshMedia);
    const interval = setInterval(refreshMedia, 4000);
    return () => {
      active = false;
      clearInterval(interval);
      window.removeEventListener('offline', refreshMedia);
      window.removeEventListener('focus', refreshMedia);
      for (const url of urls.values()) URL.revokeObjectURL(url);
    };
  }, [page.id]);
  const { html, media } = useMemo(() => preparePreview(page, localUrls), [page, localUrls]);
  const originalUrl = webUrl(page.url, page.url);
  return (
    <>
      <div dangerouslySetInnerHTML={{ __html: html }} />
      {media.length > 0 && (
        <section className="reader-media">
          <h2>Page media</h2>
          {media.map((item) => <MediaItem key={item.url} item={item} originalUrl={originalUrl} />)}
        </section>
      )}
      {originalUrl && <a className="reader-original" href={originalUrl} target="_blank" rel="noreferrer">Open original page</a>}
    </>
  );
}
