// Keep this module inside the classic content-script bundle.
declare module '*?content-script' {
  export function summarizeSavedText(text: string, signal: AbortSignal): Promise<string | undefined>;
}
