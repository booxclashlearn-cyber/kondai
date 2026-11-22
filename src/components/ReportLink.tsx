import type { ChatMessage } from '../types';

export default function ReportLink({ message }: { message: ChatMessage }) {
  if (!message.report?.length) return null;
  const url = chrome.runtime.getURL(`vault-report.html?id=${encodeURIComponent(message.id)}`);
  return <a className="report-link" href={url} target="_blank" rel="noreferrer">Open PDF report</a>;
}
