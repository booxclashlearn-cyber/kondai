import React, { useEffect, useRef, useState } from 'react';
import {
  getAllValidPages,
  getPageByUrl,
  getValidChatMessages,
  saveChatMessage,
  retrieveRelevantContext,
  buildPageContext,
  setPagePinned,
  type ResearchContext,
} from '../services/db';
import { askHybridAI } from '../services/firebase';
import NanoSetup from '../components/NanoSetup';
import MessageSources from '../components/MessageSources';
import ReportLink from '../components/ReportLink';
import { isPdfReportRequest, saveVaultReport } from '../services/vaultReport';
import PageTranslation from './PageTranslation';
import PageMedia from './PageMedia';
import { findVideoSummaryPage, isVideoSummaryRequest } from './videoSummary';
import { CapturedPage, ChatMessage } from '../types';

export default function OfflineReader() {
  const [pages, setPages] = useState<CapturedPage[]>([]);
  const [activePage, setActivePage] = useState<CapturedPage | null>(null);
  const [requestedUrl, setRequestedUrl] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [reportProgress, setReportProgress] = useState('');
  const [chatError, setChatError] = useState('');
  const [questionPages, setQuestionPages] = useState<string[]>([]);
  const [selecting, setSelecting] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);
  const [excerpts, setExcerpts] = useState<string[]>([]);
  const [pinStatus, setPinStatus] = useState('');
  const [pinBusy, setPinBusy] = useState(false);
  const preview = useRef<HTMLElement>(null);
  const chatInput = useRef<HTMLInputElement>(null);
  const transcript = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const list = transcript.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlParam = params.get('url') || '';
    const messageId = params.get('message');
    setRequestedUrl(urlParam);

    Promise.all([getAllValidPages(), getValidChatMessages()]).then(async ([allPages, msgs]) => {
      setPages(allPages);
      setMessages(msgs);
      if (urlParam) {
        const match = await getPageByUrl(urlParam);
        if (match) {
          setActivePage(match);
          setExcerpts(msgs.find(({ id }) => id === messageId)?.sourceExcerpts
            ?.filter(({ url }) => url === match.url).map(({ text }) => text) ?? []);
        }
        else if (allPages.length > 0) setActivePage(allPages[0]);
      } else if (allPages.length > 0) {
        setActivePage(allPages[0]);
      }
    });
  }, []);

  const openPage = (page: CapturedPage, sourceText: string[] = []) => {
    setActivePage(page);
    setExcerpts(sourceText);
    setShowTranslation(false);
    setPinStatus('');
    preview.current?.scrollTo(0, 0);
  };

  const togglePin = async () => {
    if (!activePage) return;
    setPinBusy(true);
    setPinStatus('');
    try {
      const page = await setPagePinned(activePage.id, !activePage.pinned);
      setPages(await getAllValidPages());
      setActivePage((current) => current?.id === activePage.id ? page ?? null : current);
      if (!page) setQuestionPages((current) => current.filter((url) => url !== activePage.url));
      setPinStatus(page?.pinned ? 'Pinned for offline use.' : page ? 'Pin removed.' : 'The unpinned page has expired.');
    } catch (err) {
      setPinStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setPinBusy(false);
    }
  };

  const runChat = async (question: string, task?: 'digest' | 'video') => {
    if (loading) return;
    if (!task) setInput('');
    setChatError('');
    setLoading(true);

    try {
      if (!task && isPdfReportRequest(question)) {
        const userMessage = await saveChatMessage({ role: 'user', content: question, referencedUrls: [], inferenceSource: 'system' });
        setMessages((previous) => [...previous, userMessage]);
        const report = await saveVaultReport(setReportProgress);
        setMessages((previous) => [...previous, report]);
        return;
      }
      const videoPage = task === 'video'
        ? findVideoSummaryPage(question, await getAllValidPages(), activePage)
        : undefined;
      const urls = videoPage ? [videoPage.url] : task ? [] : questionPages;
      const requests: { question: string; context: ResearchContext; note?: string }[] = [];
      const historyText = task ? '' : (urls.length
        ? messages.filter((message) => message.referencedUrls.length > 0 &&
          message.referencedUrls.every((url) => urls.includes(url)))
        : messages).slice(-6).map((m) => `${m.role.toUpperCase()}: ${m.content}`).join('\n');

      if (task === 'digest') {
        const start = new Date();
        start.setHours(0, 0, 0, 0);
        const today = (await getAllValidPages()).filter(({ capturedAt }) => capturedAt >= start.getTime());
        if (!today.length) throw new Error('No saved pages from today yet.');
        for (let index = 0; index < today.length; index += 8) {
          const batch = today.slice(index, index + 8);
          requests.push({
            question: 'Write a catch-up digest of up to 100 words from these saved pages. Group related pages under topic headings and mention the titles within each group.',
            context: buildPageContext(batch.map((page) => ({
              page, text: (page.summary || page.chunks[0] || page.cleanText).slice(0, 450),
            }))),
          });
        }
      } else if (task === 'video') {
        const page = videoPage && await getPageByUrl(videoPage.url);
        if (!page) throw new Error('No matching video page is saved. Select a saved page or visit the video page while online.');
        const { video } = page;
        const description = video?.description || page.cleanText;
        const descriptionLabel = video?.description ? 'Video description' : 'Saved page or video listing';
        if (!description.trim() && !video?.captions) throw new Error('This saved video page has no readable description or captions.');
        const content = [
          video?.title && `Video title: ${video.title.slice(0, 120)}`,
          description.trim() && `${descriptionLabel}: ${description.slice(0, video?.captions ? 440 : 1400)}`,
          video?.captions && `Captions: ${video.captions.slice(0, 920)}`,
        ].filter(Boolean).join('\n\n');
        requests.push({
          question: 'Summarize the video or video listing using only the material supplied. Distinguish what the listing says from what the captions say when both are present.',
          context: {
            ...buildPageContext([{ page, text: content }]),
            latestPageSummary: {
              id: page.id, capturedAt: page.capturedAt, title: page.title,
              excerpt: content, summary: video?.summary, videoSource: video ?? {},
            },
          },
          note: `Material used: ${[description.trim() && descriptionLabel, video?.captions && 'captions'].filter(Boolean).join(' and ')}.\n\n`,
        });
      } else {
        requests.push({ question, context: await retrieveRelevantContext(question, undefined, urls) });
      }

      const userMsg = await saveChatMessage({
        role: 'user',
        content: question,
        referencedUrls: urls,
        inferenceSource: 'system',
      });
      setMessages((prev) => [...prev, userMsg]);

      if (task === 'digest' && requests.length > 1) {
        let digests: string[] = [];
        for (const { question: digestQuestion, context } of requests) {
          const reply = await askHybridAI({ question: digestQuestion, contextText: context.contextText, historyText: '' });
          digests.push(reply.text);
        }
        const mergeQuestion = 'Combine these partial browsing digests into one concise catch-up. Merge overlapping topics, give each topic a heading, and mention the relevant page titles.';
        while (digests.length > 8) {
          const merged: string[] = [];
          for (let index = 0; index < digests.length; index += 8) {
            const reply = await askHybridAI({
              question: mergeQuestion + ' Use up to 150 words.',
              contextText: digests.slice(index, index + 8).map((digest) => digest.slice(0, 850)).join('\n\n'),
              historyText: '',
            });
            merged.push(reply.text);
          }
          digests = merged;
        }
        const context = {
          contextText: digests.map((digest) => digest.slice(0, 850)).join('\n\n'),
          referencedUrls: requests.flatMap(({ context: batch }) => batch.referencedUrls),
          sourceExcerpts: requests.flatMap(({ context: batch }) => batch.sourceExcerpts),
        };
        requests.splice(0, requests.length, { question: mergeQuestion, context });
      }

      for (const request of requests) {
        const { contextText, referencedUrls, sourceExcerpts, latestPageSummary } = request.context;
        const reply = await askHybridAI({ question: request.question, contextText, historyText, latestPageSummary });
        const aiMsg = await saveChatMessage({
          role: 'assistant',
          content: (request.note ?? '') + reply.text,
          referencedUrls,
          sourceExcerpts,
          inferenceSource: reply.inferenceSource,
        });
        setMessages((prev) => [...prev, aiMsg]);
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : String(err));
    } finally {
      setReportProgress('');
      setLoading(false);
    }
  };

  const handleAsk = (event: React.FormEvent) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;
    if (!isPdfReportRequest(question) && !selecting && isVideoSummaryRequest(question)) {
      setInput('');
      void runChat(question, 'video');
    } else {
      void runChat(question);
    }
  };

  return (
    <div className="reader-layout">
      <aside className="reader-sidebar">
        <div className="brand">kondai Vault</div>
        <div className="reader-actions">
          <button className="btn" disabled={loading} onClick={() => runChat('Catch me up on today’s pages', 'digest')}>Catch me up</button>
          <button className="btn btn-ghost" aria-pressed={selecting} disabled={loading} onClick={() => {
            setSelecting(!selecting);
            setQuestionPages([]);
          }}>{selecting ? 'Done comparing' : 'Compare pages'}</button>
          {selecting && <p className="reader-status">Select two or three pages, then ask in chat.</p>}
        </div>
        <div className="reader-actions">
          <button className="btn btn-ghost" disabled={!activePage || loading} onClick={() => {
            if (!activePage) return;
            setSelecting(false);
            setQuestionPages([activePage.url]);
            chatInput.current?.focus();
          }}>Ask about this page</button>
          <button className="btn btn-ghost" disabled={!activePage || pinBusy} onClick={togglePin}>{activePage?.pinned ? 'Unpin page' : 'Pin for offline'}</button>
          <button className="btn btn-ghost" disabled={!activePage} aria-pressed={showTranslation} onClick={() => {
            setShowTranslation(!showTranslation);
            preview.current?.scrollTo(0, 0);
          }}>{showTranslation ? 'Show saved page' : 'Translate page'}</button>
          <button className="btn btn-ghost" disabled={!activePage || loading} onClick={() => runChat('Summarize this video page', 'video')}>Summarize video page</button>
          {pinStatus && <p className="reader-status" role="status">{pinStatus}</p>}
        </div>
        <h2 className="reader-section-heading">Saved pages ({pages.length})</h2>
        {pages.map((p) => (
          <div key={p.id} className="reader-page-row">
            {selecting && (
              <input type="checkbox" aria-label={`Select ${p.title}`}
                checked={questionPages.includes(p.url)}
                disabled={loading || (questionPages.length === 3 && !questionPages.includes(p.url))}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setQuestionPages((previous) => checked ? [...previous, p.url] : previous.filter((url) => url !== p.url));
                }} />
            )}
            <button type="button" className="page-item" aria-current={activePage?.id === p.id ? 'page' : undefined}
              onClick={() => openPage(p)}>
              <span className="page-title">{p.title}</span>
              {p.pinned && <span className="page-url">Pinned</span>}
            </button>
          </div>
        ))}
        <details className="reader-setup"><summary>Offline AI setup</summary><NanoSetup /></details>
      </aside>

      <main className="reader-main" ref={preview} aria-label="Page preview" tabIndex={0}>
        {activePage ? (
          <article className="reader-article">
            <div style={{ fontSize: 12, color: '#38bdf8', marginBottom: 8 }}>
              Saved {new Date(activePage.capturedAt).toLocaleString()} · {activePage.pinned ? 'Pinned' : '24-hour vault'}
            </div>
            <h1>{activePage.title}</h1>
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 20 }}>
              {activePage.url}
            </div>
            {excerpts.length > 0 && (
              <section className="card reader-excerpts">
                <h2>Excerpts used in the answer</h2>
                {excerpts.map((excerpt, index) => <blockquote key={index}>{excerpt}</blockquote>)}
              </section>
            )}
            {!showTranslation && activePage.summary && (
              <div className="card" style={{ marginBottom: 20 }}>
                <strong>Saved summary</strong>
                <p>{activePage.summary}</p>
              </div>
            )}
            {showTranslation
              ? <PageTranslation key={activePage.id} page={activePage} />
              : <PageMedia key={activePage.id} page={activePage} />}
          </article>
        ) : (
          <div className="reader-article">
            <h1>No saved page selected</h1>
            <p style={{ color: '#94a3b8' }}>
              {requestedUrl
                ? `We intercepted ${requestedUrl}, but no cached snapshot was found in your 24-hour vault.`
                : 'Enable 24-Hour Web Capture in the kondai Side Panel while online to browse pages here offline.'}
            </p>
          </div>
        )}
      </main>

      <section className="reader-chat">
        <h2 className="reader-section-heading">Research chat</h2>
        <div className="scroll-area" ref={transcript} aria-label="Chat messages" tabIndex={0}>
          {messages.map((m) => (
            <div
              key={m.id}
              className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-assistant'}`}
            >
              <div>{m.content}</div>
              <ReportLink message={m} />
              {m.role === 'assistant' && (
                <MessageSources message={m} pages={pages} onOpen={openPage} />
              )}
              {m.role === 'assistant' && (
                <div className="msg-meta">
                  <span>
                    {m.inferenceSource === 'on-device'
                      ? '⚡ On-Device (Gemini Nano 4)'
                      : m.inferenceSource === 'cloud' ? '☁️ Cloud' : 'System'}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
        {loading && <div role="status">{reportProgress || 'Waiting for a reply…'}</div>}
        {chatError && <div role="alert">{chatError}</div>}
        {questionPages.length > 0 && (
          <div className="row">
            <span>{questionPages.length === 1
              ? pages.find(({ url }) => url === questionPages[0])?.title
              : `${questionPages.length} selected pages`}</span>
            <button className="btn btn-ghost" type="button" disabled={loading} onClick={() => {
              setQuestionPages([]);
              setSelecting(false);
            }}>
              All pages
            </button>
          </div>
        )}
        <form className="input-bar" onSubmit={handleAsk}>
          <input
            ref={chatInput}
            className="input"
            placeholder="Ask offline AI about your 24h vault..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading || (selecting && questionPages.length < 2)}
          />
          <button className="btn" type="submit" disabled={loading || (selecting && questionPages.length < 2)}>
            {loading ? '...' : 'Ask'}
          </button>
        </form>
      </section>
    </div>
  );
}
