export const TTL_24_HOURS_MS = 24 * 60 * 60 * 1000;

export interface CapturedPage {
  id: string;
  url: string;
  title: string;
  cleanText: string;
  snapshotHtml: string;
  chunks: string[];
  summary?: string;
  pinned?: boolean;
  language?: string;
  video?: SavedVideo;
  media?: SavedMedia[];
  capturedAt: number;
  expiresAt: number;
}

export interface SavedMedia {
  kind: 'image' | 'video' | 'audio';
  url: string;
  label?: string;
  poster?: string;
}

export interface SavedVideo {
  title?: string;
  description?: string;
  captions?: string;
  summary?: string;
}

export interface SourceExcerpt {
  url: string;
  text: string;
}

export interface VaultReportEntry {
  title: string;
  url: string;
  pageId: string;
  summary?: string;
  thumbnailCandidates: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  referencedUrls: string[];
  sourceExcerpts?: SourceExcerpt[];
  report?: VaultReportEntry[];
  inferenceSource: 'on-device' | 'cloud' | 'system';
  createdAt: number;
  expiresAt: number;
}

export interface VaultSettings {
  captureEnabled: boolean;
  preferOfflineMode: boolean;
}

export type LocalModelStatus = 'readily' | 'downloadable' | 'downloading' | 'unavailable' | 'unsupported' | 'unknown';
