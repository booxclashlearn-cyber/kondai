import { getAllValidPages, saveChatMessage } from './db';
import { askHybridAI } from './firebase';
import type { VaultReportEntry } from '../types';

export function isPdfReportRequest(question: string) {
  return /\bpdf\b/i.test(question) && /\b(?:summar(?:y|ies|i[sz]e)|digest|report|export)\b/i.test(question);
}

export async function createVaultReport(onProgress: (status: string) => void): Promise<VaultReportEntry[]> {
  const pages = await getAllValidPages();
  if (!pages.length) throw new Error('Save a page to the vault before creating a PDF report.');
  const entries: VaultReportEntry[] = [];

  for (const [index, page] of pages.entries()) {
    onProgress(`Preparing PDF report · ${index + 1}/${pages.length}`);
    let summary = page.summary?.trim();
    const excerpt = page.chunks.slice(0, 4).join(' ').trim() || page.cleanText.slice(0, 3200);
    if (!summary && excerpt) {
      try {
        const reply = await askHybridAI({
          question: 'Write a professional two- or three-sentence summary of this saved page. Use only the supplied content. Return the summary text without a heading.',
          contextText: `Page: ${page.title}\n\n${excerpt}`,
          historyText: '',
          latestPageSummary: { id: page.id, capturedAt: page.capturedAt, title: page.title, excerpt },
        });
        summary = reply.text.trim();
      } catch {
        // Keep the page and flag the missing model summary in the report.
      }
    }
    const media = page.media ?? [];
    entries.push({
      title: page.title,
      url: page.url,
      pageId: page.id,
      summary,
      thumbnailCandidates: [...new Set(media.flatMap((asset) => asset.poster ? [asset.poster] : [])
        .concat(media.filter((asset) => asset.kind === 'image').map((asset) => asset.url)))],
    });
  }
  return entries;
}

export async function saveVaultReport(onProgress: (status: string) => void) {
  const report = await createVaultReport(onProgress);
  const missing = report.filter(({ summary }) => !summary).length;
  return saveChatMessage({
    role: 'assistant',
    inferenceSource: 'system',
    content: `Your report includes all ${report.length} saved ${report.length === 1 ? 'page' : 'pages'}.${missing
      ? ` A model summary was unavailable for ${missing}.` : ''}`,
    referencedUrls: [],
    report,
  });
}
