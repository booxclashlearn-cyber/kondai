import type { CapturedPage } from '../types';

export function isVideoSummaryRequest(question: string) {
  return /\b(?:summari[sz]e|summary|recap)\b/i.test(question) &&
    /\b(?:video|clip|captions|transcript)\b/i.test(question);
}

export function findVideoSummaryPage(question: string, pages: CapturedPage[], activePage: CapturedPage | null) {
  const host = question.match(/\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b/i)?.[0].toLowerCase().replace(/^www\./, '');
  if (!host) return activePage ?? pages.find(({ video }) => Boolean(video));
  const matchesHost = (page: CapturedPage) => {
    const savedHost = new URL(page.url).hostname.replace(/^www\./, '');
    return savedHost === host || savedHost.endsWith(`.${host}`);
  };
  if (activePage && matchesHost(activePage)) return activePage;
  return pages.find((page) => page.video && matchesHost(page)) ?? pages.find(matchesHost);
}
