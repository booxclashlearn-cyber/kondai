import type { CapturedPage, ChatMessage } from '../types';

export default function MessageSources({ message, pages, onOpen }: {
  message: ChatMessage;
  pages: CapturedPage[];
  onOpen?: (page: CapturedPage, excerpts: string[]) => void;
}) {
  const sources = [...new Set(message.referencedUrls)]
    .map((url) => pages.find((page) => page.url === url && (page.pinned || page.expiresAt > Date.now())))
    .filter((page): page is CapturedPage => Boolean(page));
  if (!sources.length) return null;

  return (
    <details className="msg-sources">
      <summary>Sources ({sources.length})</summary>
      <ul>
        {sources.map((page) => (
          <li key={page.id}>
            <a href={chrome.runtime.getURL(`offline-reader.html?${new URLSearchParams({ url: page.url, message: message.id })}`)}
              target={onOpen ? undefined : '_blank'}
              rel="noreferrer"
              onClick={(event) => {
                if (!onOpen || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                onOpen(page, message.sourceExcerpts?.filter(({ url }) => url === page.url).map(({ text }) => text) ?? []);
              }}>
              {page.title}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}
