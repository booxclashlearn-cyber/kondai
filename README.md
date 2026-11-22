# kondai — Ephemeral 24-Hour Offline Web Memory & Hybrid AI Assistant

Built for **#BuildHybridAI 2026** (Web / Chrome Extension Track).

kondai replaces Chrome's `ERR_INTERNET_DISCONNECTED` screen with a self-cleaning **24-hour offline research vault** and research chat.

## Key Features
- **Opt-In 24-Hour Passive Web Capture:** Once enabled, kondai automatically snapshots visited pages (clean readable HTML + chunked text) into local IndexedDB with a strict 24-hour TTL.
- **`ERR_INTERNET_DISCONNECTED` Takeover:** When Wi-Fi drops, Chrome's network error is intercepted via `chrome.webNavigation.onErrorOccurred` and redirected to `offline-reader.html`, letting you keep reading any page visited in the last 24 hours.
- **Hybrid AI Research Memory (`firebase/ai`):**
  - **Online** uses Cloud Gemini through Firebase AI Logic with relevant excerpts and recent chat history.
  - **Offline** uses Chrome’s on-device Gemini Nano over your 24-hour vault and chat history.
- **24-Hour Auto-Purge:** A background `chrome.alarms` job automatically wipes expired pages and LLM conversations every 15 minutes so your vault stays private and lightweight.

## Quick Start (For Judges & Developers)

### 1. Prerequisites
- **Google Chrome 139+** (Desktop)
- Enable Chrome's Built-in AI flag:
  1. Open `chrome://flags/#prompt-api-for-gemini-nano-multimodal-input`
  2. Set it to **Enabled** and relaunch Chrome.
- **Node.js 18+**

### 2. Configure Firebase
1. Create a Firebase project and enable **Firebase AI Logic** and **App Check**.
2. Set your Firebase web config in `.env`.
3. For private testing, register an App Check debug token in the Firebase Console and set `VITE_FIREBASE_APPCHECK_DEBUG_TOKEN` in `.env`. You can also leave it unset and register the token logged in the extension’s DevTools on first run.

### 3. Build & Load Unpacked Extension
```bash
npm install
npm run build:debug
```
1. Open `chrome://extensions/` in Chrome.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select the generated `dist-debug/` folder.
4. Click the **kondai** icon in the toolbar to open the Side Panel.

Keep `dist-debug/` private. The regular `npm run build` output in `dist/` excludes App Check debug credentials. Cloud chat in a distributed build requires a production App Check integration.

### 4. Testing Offline Mode
1. Toggle **24-Hour Auto-Capture** ON in the Side Panel.
2. Browse 2–3 articles normally and ask a question in the Side Panel chat.
3. Turn off Wi-Fi (or open DevTools -> Network -> **Offline**).
4. Refresh a visited tab or click a link — kondai intercepts `ERR_INTERNET_DISCONNECTED`, loads your cached page, and lets you continue chatting offline using **Gemini Nano 4**.
