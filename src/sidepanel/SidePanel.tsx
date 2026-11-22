import React, { useEffect, useRef, useState } from 'react';
import {
  getAllValidPages,
  getValidChatMessages,
  saveChatMessage,
  retrieveRelevantContext,
  purgeAllVaultData,
} from '../services/db';
import { askHybridAI } from '../services/firebase';
import NanoSetup from '../components/NanoSetup';
import MessageSources from '../components/MessageSources';
import ReportLink from '../components/ReportLink';
import { isPdfReportRequest, saveVaultReport } from '../services/vaultReport';
import { CapturedPage, ChatMessage } from '../types';

export default function SidePanel() {
  const [captureEnabled, setCaptureEnabled] = useState(false);
  const [captureBusy, setCaptureBusy] = useState(false);
  const [captureStatus, setCaptureStatus] = useState('');
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [tab, setTab] = useState<'chat' | 'vault'>('chat');
  const [pages, setPages] = useState<CapturedPage[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [reportProgress, setReportProgress] = useState('');
  const [chatError, setChatError] = useState('');
  const transcript = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const list = transcript.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length]);

  const refreshData = async () => {
    const [p, m] = await Promise.all([getAllValidPages(), getValidChatMessages()]);
    setPages(p);
    setMessages(m);
  };

  useEffect(() => {
    chrome.storage.local.get(['captureEnabled'], (res) => {
      setCaptureEnabled(Boolean(res.captureEnabled));
    });
    refreshData();

    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    const interval = setInterval(refreshData, 5000);
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      clearInterval(interval);
    };
  }, []);

  const captureActivePage = async () => {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const tabId = activeTab?.id;
    if (tabId === undefined || !/^https?:\/\//i.test(activeTab.url ?? '')) {
      throw new Error('Open a regular website and click Save this page.');
    }

    const request = () => chrome.tabs.sendMessage(tabId, { type: 'CAPTURE_CURRENT_PAGE' }, { frameId: 0 });
    let result;
    try {
      result = await request();
    } catch {
      // Tabs open before installation or reload may not have a content script.
      await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
      result = await request();
    }
    if (!result?.ok) throw new Error(result?.error || 'Kondai did not confirm the save.');
    setPages(await getAllValidPages());
    setCaptureStatus('Page saved to the 24h Vault.');
  };

  const updateCapture = async (toggle: boolean) => {
    setCaptureBusy(true);
    setCaptureStatus('');
    let enabledNow = false;
    try {
      if (toggle) {
        const next = !captureEnabled;
        await chrome.storage.local.set({ captureEnabled: next });
        setCaptureEnabled(next);
        if (!next) return;
        enabledNow = true;
      }
      await captureActivePage();
    } catch (err) {
      setCaptureStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setCaptureBusy(false);
      if (enabledNow && navigator.onLine) {
        // The installed Chrome typings predate sidePanel.close().
        const panel = chrome.sidePanel as typeof chrome.sidePanel & {
          close?(options: { windowId: number }): Promise<void>;
        };
        if (panel.close) {
          try {
            const { id } = await chrome.windows.getCurrent();
            if (id !== undefined) await panel.close({ windowId: id });
          } catch (error) {
            console.debug('[kondai] Could not close the side panel:', error);
          }
        }
      }
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput('');
    setChatError('');
    setLoading(true);

    try {
      const userMsg = await saveChatMessage({
        role: 'user',
        content: question,
        referencedUrls: [],
        inferenceSource: 'system',
      });
      setMessages((prev) => [...prev, userMsg]);

      if (isPdfReportRequest(question)) {
        const report = await saveVaultReport(setReportProgress);
        setMessages((prev) => [...prev, report]);
        return;
      }

      const { contextText, referencedUrls, sourceExcerpts, latestPageSummary } = await retrieveRelevantContext(question);
      const historyText = messages
        .slice(-6)
        .map((m) => `${m.role.toUpperCase()}: ${m.content}`)
        .join('\n');

      const reply = await askHybridAI({ question, contextText, historyText, latestPageSummary });

      const aiMsg = await saveChatMessage({
        role: 'assistant',
        content: reply.text,
        referencedUrls,
        sourceExcerpts,
        inferenceSource: reply.inferenceSource,
      });
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : String(err));
    } finally {
      setReportProgress('');
      setLoading(false);
    }
  };

  const handlePurge = async () => {
    await purgeAllVaultData();
    await refreshData();
  };

  const openOfflineReader = async (url?: string) => {
    const hub = chrome.runtime.getURL('offline-reader.html');
    const target = url ? `${hub}?url=${encodeURIComponent(url)}` : hub;
    try {
      const tabs = await chrome.tabs.query({ currentWindow: true });
      const existing = tabs.find((tab) => url ? tab.url === target : tab.url?.split('?')[0] === hub);
      if (existing?.id !== undefined) await chrome.tabs.update(existing.id, { active: true });
      else await chrome.tabs.create({ url: target });
    } catch (error) {
      setChatError(error instanceof Error ? error.message : String(error));
    }
  };

  if (!isOnline) {
    return (
      <div className="container offline-launcher">
        <div className="header">
          <div className="brand">kondai Vault</div>
          <span className="badge badge-offline">OFFLINE</span>
        </div>
        <button className="btn" type="button" onClick={() => openOfflineReader()}>Open Offline Hub</button>
        <p className="reader-status">{pages.length} saved {pages.length === 1 ? 'page' : 'pages'}</p>
        {chatError && <div role="alert">{chatError}</div>}
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header">
        <div className="brand">kondai</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <span className="badge badge-online">ONLINE</span>
        </div>
      </div>

      <NanoSetup />

      <div className="card">
        <div className="row">
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>24-Hour Web Capture</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              Auto-saves visited pages & chats (auto-wipes in 24h)
            </div>
          </div>
          <button
            className={`btn ${captureEnabled ? '' : 'btn-ghost'}`}
            onClick={() => updateCapture(true)}
            disabled={captureBusy}
            aria-pressed={captureEnabled}
          >
            {captureEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
        {captureEnabled && (
          <button className="btn btn-ghost" onClick={() => updateCapture(false)} disabled={captureBusy}>
            {captureBusy ? 'Saving…' : 'Save this page'}
          </button>
        )}
        {captureStatus && <div role="status">{captureStatus}</div>}
      </div>

      <div className="tabs">
        <button
          className={`tab ${tab === 'chat' ? 'active' : ''}`}
          onClick={() => setTab('chat')}
        >
          Hybrid AI Chat ({messages.length})
        </button>
        <button
          className={`tab ${tab === 'vault' ? 'active' : ''}`}
          onClick={() => setTab('vault')}
        >
          24h Vault ({pages.length})
        </button>
      </div>

      {tab === 'chat' ? (
        <>
          <div className="scroll-area" ref={transcript}>
            {messages.length === 0 && (
              <div className="card" style={{ fontSize: 12, color: '#94a3b8' }}>
                Ask anything about pages you visited in the last 24 hours. Works online via Cloud Gemini and offline via on-device Gemini Nano 4.
              </div>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-assistant'}`}
              >
                <div>{m.content}</div>
                <ReportLink message={m} />
                {m.role === 'assistant' && <MessageSources message={m} pages={pages} />}
                {m.role === 'assistant' && (
                  <div className="msg-meta">
                    <span>
                      {m.inferenceSource === 'on-device'
                        ? '⚡ On-Device (Gemini Nano 4)'
                        : m.inferenceSource === 'cloud'
                        ? '☁️ Cloud Gemini'
                        : 'System'}
                    </span>
                    <span>24h TTL</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {loading && <div role="status">{reportProgress || 'Waiting for a reply…'}</div>}
          {chatError && <div role="alert">{chatError}</div>}
          <form className="input-bar" onSubmit={handleSend}>
            <input
              className="input"
              placeholder="Ask your 24h research vault..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button className="btn" type="submit" disabled={loading}>
              {loading ? '...' : 'Ask'}
            </button>
          </form>
        </>
      ) : (
        <div className="scroll-area">
          <div className="row">
            <button className="btn btn-ghost" onClick={() => openOfflineReader()}>
              Open Offline Hub
            </button>
            <button className="btn btn-danger" onClick={handlePurge}>
              Purge 24h Vault
            </button>
          </div>
          {pages.length === 0 && (
            <div className="card" style={{ fontSize: 12, color: '#94a3b8' }}>
              No pages captured yet. Turn ON 24-Hour Web Capture and browse normally.
            </div>
          )}
          {pages.map((p) => {
            const hrsLeft = Math.max(1, Math.round((p.expiresAt - Date.now()) / 3600000));
            return (
              <div
                key={p.id}
                className="page-item"
                onClick={() => openOfflineReader(p.url)}
              >
                <div className="page-title">{p.title}</div>
                <div className="page-url">{p.url}</div>
                <div style={{ fontSize: 10, color: '#38bdf8', marginTop: 4 }}>
                  {p.pinned ? 'Pinned' : `Expires in ~${hrsLeft}h`} • Click to read offline
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
