import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { getCachedMedia, getValidChatMessage } from '../services/db';
import ReportDocument, { type PrintableEntry } from './ReportDocument';
import type { VaultReportEntry } from '../types';
import './report.css';

async function createThumbnail(entry: VaultReportEntry): Promise<Blob | undefined> {
  const images = (await getCachedMedia(entry.pageId)).filter(({ blob }) => blob.type.startsWith('image/'));
  const chosen = entry.thumbnailCandidates.map((url) => images.find((image) => image.url === url)).filter(Boolean);
  for (const image of [...new Set([...chosen, ...images])]) {
    if (!image) continue;
    try {
      const bitmap = await createImageBitmap(image.blob);
      try {
        const scale = Math.min(1, 220 / bitmap.width, 144 / bitmap.height);
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(bitmap.width * scale));
        canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        const context = canvas.getContext('2d');
        if (!context) return;
        context.fillStyle = '#fff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        const thumbnail = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82));
        if (thumbnail) return thumbnail;
      } finally {
        bitmap.close();
      }
    } catch {
      // Try the next saved image if the browser cannot decode this one.
    }
  }
}

function ReportPage() {
  const [report, setReport] = useState<{ entries: PrintableEntry[]; date: string }>();
  const [status, setStatus] = useState('Preparing report preview…');
  useEffect(() => {
    let active = true;
    const objectUrls: string[] = [];
    void (async () => {
      const id = new URLSearchParams(location.search).get('id');
      const message = id && await getValidChatMessage(id);
      if (!message || !message.report?.length) {
        if (active) setStatus('This report expired or was removed. Create a new one from chat.');
        return;
      }
      const entries: PrintableEntry[] = [];
      for (const entry of message.report) {
        const image = await createThumbnail(entry).catch(() => undefined);
        if (!active) return;
        const thumbnail = image && URL.createObjectURL(image);
        if (thumbnail) objectUrls.push(thumbnail);
        entries.push({ ...entry, thumbnail });
      }
      if (active) setReport({ entries, date: new Date(message.createdAt).toLocaleDateString(undefined, { dateStyle: 'long' }) });
    })().catch(() => { if (active) setStatus('The saved report could not be opened.'); });
    return () => {
      active = false;
      for (const url of objectUrls) URL.revokeObjectURL(url);
    };
  }, []);

  if (!report) return <p className="report-status" role="status">{status}</p>;
  return (
    <>
      <nav className="report-toolbar" aria-label="Report actions">
        <button type="button" onClick={async () => {
          await Promise.all(Array.from(document.images, (image) => image.decode().catch(() => {})));
          window.print();
        }}>Save as PDF</button>
      </nav>
      <ReportDocument entries={report.entries} date={report.date} />
    </>
  );
}

createRoot(document.getElementById('root')!).render(<ReportPage />);
