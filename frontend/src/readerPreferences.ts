export type ReaderTheme = "light" | "dark" | "sepia" | "system";
export interface ReaderPreferences {
  theme: ReaderTheme;
  accent: "blue" | "violet" | "green";
  fontSize: number;
  lineHeight: number;
  font: "myanmar" | "serif";
  readingWidth: "comfortable" | "wide";
  focusMode: boolean;
  playbackRate: number;
  volume: number;
  reduceMotion: boolean;
  rememberHistory: boolean;
}
export const readerPreferencesKey = "pyonpyin-reader-preferences-v1";
export const favoriteKey = "pyonpyin-reader-favorites";
export const historyKey = "pyonpyin-reader-history";
export const sleepTimerKey = "pyonpyin-reader-sleep-until";
export const defaultReaderPreferences: ReaderPreferences = {
  theme: "light", accent: "blue", fontSize: 16, lineHeight: 2.4, font: "myanmar",
  readingWidth: "comfortable", focusMode: false, playbackRate: 1, volume: 0.8,
  reduceMotion: false, rememberHistory: true,
};
function choice<T extends string>(value: unknown, options: readonly T[], fallback: T): T {
  return typeof value === "string" && options.includes(value as T) ? value as T : fallback;
}
function number(value: unknown, min: number, max: number, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback;
}
export function validateReaderPreferences(value: unknown): ReaderPreferences {
  const p = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
  return {
    theme: choice(p.theme, ["light", "dark", "sepia", "system"], "light"),
    accent: choice(p.accent, ["blue", "violet", "green"], "blue"),
    fontSize: number(p.fontSize, 14, 26, 16), lineHeight: number(p.lineHeight, 1.8, 3, 2.4),
    font: choice(p.font, ["myanmar", "serif"], "myanmar"),
    readingWidth: choice(p.readingWidth, ["comfortable", "wide"], "comfortable"),
    focusMode: typeof p.focusMode === "boolean" ? p.focusMode : false,
    playbackRate: number(p.playbackRate, 0.5, 2, 1), volume: number(p.volume, 0, 1, 0.8),
    reduceMotion: typeof p.reduceMotion === "boolean" ? p.reduceMotion : false,
    rememberHistory: typeof p.rememberHistory === "boolean" ? p.rememberHistory : true,
  };
}
export function loadReaderPreferences(): ReaderPreferences {
  try {
    const saved = localStorage.getItem(readerPreferencesKey);
    if (saved) return validateReaderPreferences(JSON.parse(saved));
    return { ...defaultReaderPreferences, theme: localStorage.getItem("pyonpyin-reader-night") === "true" ? "dark" : "light" };
  } catch { return { ...defaultReaderPreferences }; }
}
export function readReaderIds(key: string): string[] {
  try { return validateReaderIds(JSON.parse(localStorage.getItem(key) || "[]")); } catch { return []; }
}
export function validateReaderIds(value: unknown): string[] {
  return Array.isArray(value) ? [...new Set(value.filter((id): id is string => typeof id === "string" && id.length > 0 && id.length <= 200))].slice(0, 1000) : [];
}
export function parseReaderBackup(text: string) {
  const value = JSON.parse(text);
  if (!value || value.app !== "pyonpyin-reader" || value.version !== 1 || !value.preferences || !Array.isArray(value.favorites) || !Array.isArray(value.history)) throw new Error("PyonPyin Settings မှ ထုတ်ထားသော backup ဖိုင်ကိုသာ ရွေးပါ။");
  return { preferences: validateReaderPreferences(value.preferences), favorites: validateReaderIds(value.favorites), history: validateReaderIds(value.history).slice(0, 50) };
}

// အသံထုတ်ကုန်အားလုံးကို တစ်ပြိုင်တည်းမဖွင့်စေဘဲ sleep timer ကလည်း ဤ player များကို ရပ်နိုင်သည်။
export function pauseReaderAudio(except?: HTMLAudioElement) {
  document.querySelectorAll<HTMLAudioElement>(".story-world audio").forEach((audio) => { if (audio !== except && !audio.paused) audio.pause(); });
}
