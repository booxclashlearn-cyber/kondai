import type { VaultReportEntry } from '../types';

export interface PrintableEntry extends VaultReportEntry {
  thumbnail?: string;
}

export default function ReportDocument({ entries, date }: { entries: PrintableEntry[]; date: string }) {
  return (
    <main className="report">
      <header className="report-header">
        <div className="report-brand">kondai</div>
        <h1>Saved Page Summaries</h1>
        <p>{date} · {entries.length} {entries.length === 1 ? 'page' : 'pages'}</p>
      </header>
      {entries.map((entry) => {
        const { title, url, summary, thumbnail } = entry;
        const source = /^https?:\/\//i.test(url) ? url : undefined;
        const text = summary?.replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, '$1$2');
        return (
          <article className="report-entry" key={entry.pageId}>
            {thumbnail && <img src={thumbnail} alt="" width={104} height={68} />}
            <div className="report-entry-text">
              <h2>{title}</h2>
              <p>{text || 'Model summary unavailable for this page.'}</p>
              {source && <a href={source}>{source}</a>}
            </div>
          </article>
        );
      })}
    </main>
  );
}
