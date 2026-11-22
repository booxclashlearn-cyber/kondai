import { useEffect, useState } from 'react';
import { checkLocalNanoAvailability, downloadLocalNano } from '../services/firebase';
import type { LocalModelStatus } from '../types';

export default function NanoSetup() {
  const [status, setStatus] = useState<LocalModelStatus | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      setOnline(navigator.onLine);
      if (!busy) {
        void checkLocalNanoAvailability().then((next) => {
          if (active) setStatus(next);
        });
      }
    };
    refresh();
    window.addEventListener('online', refresh);
    window.addEventListener('offline', refresh);
    window.addEventListener('focus', refresh);
    return () => {
      active = false;
      window.removeEventListener('online', refresh);
      window.removeEventListener('offline', refresh);
      window.removeEventListener('focus', refresh);
    };
  }, [busy]);

  const startDownload = async () => {
    setBusy(true);
    setProgress(null);
    setFailed(false);
    try {
      await downloadLocalNano(setProgress);
      setStatus('readily');
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const canDownload = status === 'downloadable' || status === 'downloading';
  let message = 'Checking Chrome’s Gemini Nano availability…';
  if (busy) {
    message = progress === null
      ? 'Preparing the Gemini Nano download…'
      : progress === 100
        ? 'Finishing Gemini Nano setup…'
        : `Downloading Gemini Nano… ${progress}%`;
  } else if (status === 'readily') {
    message = 'Gemini Nano is ready for offline AI.';
  } else if (canDownload) {
    message = online
      ? 'Download Gemini Nano in Chrome to use AI offline.'
      : 'Reconnect to the internet to download Gemini Nano for offline AI.';
  } else if (status === 'unsupported') {
    message = 'Chrome’s Prompt API is missing. Update to the latest desktop Chrome and relaunch.';
  } else if (status === 'unavailable') {
    message = 'Chrome reports Gemini Nano is unavailable. Check device requirements, free storage and your connection.';
  } else if (status === 'unknown') {
    message = 'Could not check Gemini Nano availability. Try checking again.';
  }

  return (
    <div className="card" aria-label="Gemini Nano setup" style={{ fontSize: 12 }}>
      <div role="status">{message}</div>
      {failed && !busy && status !== 'readily' && (
        <div role="alert">
          Chrome could not complete the download. Check your connection and free storage, then try again.
        </div>
      )}
      {busy && progress !== null && (
        <progress aria-label="Gemini Nano download progress" max={100} value={progress} />
      )}
      {!busy && canDownload && online && (
        <button className="btn" type="button" onClick={startDownload}>
          {status === 'downloading' ? 'Track download' : 'Download Gemini Nano'}
        </button>
      )}
      {!busy && (status === 'unsupported' || status === 'unavailable' || status === 'unknown' || failed) && status !== 'readily' && (
        <>
          <button className="btn btn-ghost" type="button" onClick={async () => {
            setFailed(false);
            setStatus(await checkLocalNanoAvailability());
          }}>
            Check again
          </button>
          <a href="https://developer.chrome.com/docs/ai/get-started" target="_blank" rel="noreferrer">
            Chrome setup and requirements
          </a>
        </>
      )}
    </div>
  );
}
