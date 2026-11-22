import type { SavedVideo } from '../types';

function findVideoObject() {
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    const raw = script.textContent;
    if (!raw || raw.length > 200_000) continue;
    try {
      const schema = JSON.parse(raw);
      const candidates = Array.isArray(schema) ? schema : [schema, ...(Array.isArray(schema?.['@graph']) ? schema['@graph'] : [])];
      const video = candidates.find((node) => [node?.['@type']].flat().includes('VideoObject'));
      if (video) {
        return {
          title: typeof video.name === 'string' ? video.name : undefined,
          description: typeof video.description === 'string' ? video.description : undefined,
        };
      }
    } catch {
      // Continue with other structured data on the page.
    }
  }
}

export function readVideoMetadata(): SavedVideo | undefined {
  const meta = (name: string) => document.querySelector<HTMLMetaElement>(
    `meta[property="${name}"], meta[name="${name}"]`
  )?.content.trim();
  const type = meta('og:type') || '';
  const video = findVideoObject();
  if (!video && !document.querySelector('video, [itemtype$="/VideoObject"]') && !type.startsWith('video') &&
      !meta('og:video') && !meta('twitter:player')) return;

  return {
    title: (video?.title || meta('og:title') || document.title).slice(0, 250),
    description: (video?.description || meta('og:description') || meta('description'))?.slice(0, 3000),
  };
}

export async function readVideoCaptions(): Promise<string | undefined> {
  const track = document.querySelector<HTMLTrackElement>('video track[kind="captions"][src], video track[kind="subtitles"][src]');
  const cues = track?.track.cues;
  if (cues?.length) {
    return Array.from(cues).filter((cue): cue is VTTCue => 'text' in cue).map((cue) => cue.text).join('\n').slice(0, 12000);
  }
  if (!track || !/^https?:\/\//.test(track.src)) return;
  const response = await fetch(track.src, { credentials: 'omit', signal: AbortSignal.timeout(3500) });
  if (!response.ok || !response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let raw = '';
  try {
    while (raw.length < 48_000) {
      const { value, done } = await reader.read();
      if (done) break;
      raw += decoder.decode(value.subarray(0, 48_000 - raw.length), { stream: true });
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  return raw.split(/\r?\n\r?\n/).flatMap((block) => {
    const lines = block.split(/\r?\n/);
    const timing = lines.findIndex((line) => /\d:\d{2}.*-->.*\d:\d{2}/.test(line));
    return timing < 0 ? [] : lines.slice(timing + 1);
  }).join('\n').replace(/<[^>]*>/g, '').trim().slice(0, 12000) || undefined;
}
