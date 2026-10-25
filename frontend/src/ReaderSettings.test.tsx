import { act, cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { StoryWorld } from "./StoryWorld";
import { defaultReaderPreferences, readerPreferencesKey, favoriteKey, historyKey, sleepTimerKey, validateReaderPreferences, parseReaderBackup } from "./readerPreferences";
import type { PublicStory } from "./api";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });
const story: PublicStory = { story_id: "one", title: "A real story", category: "CHILDREN", story: "A story to read.", episodes: [], audio_url: "/media/audio/story.wav" };
function renderReader() { return render(<MemoryRouter initialEntries={["/stories/one"]}><StoryWorld mode="story" storyId="one" stories={[story]} error="" reload={async () => {}} /></MemoryRouter>); }
function settings() { fireEvent.click(screen.getByRole("button", { name: "Settings" })); return within(screen.getByRole("dialog")); }

it("previews and persists theme, font size, and focus mode across a remount", () => {
  const view = renderReader();
  const panel = settings();
  fireEvent.click(panel.getByRole("radio", { name: "စက္ကူရောင်" }));
  expect(document.querySelector(".story-world")).toHaveClass("world-sepia");
  fireEvent.click(panel.getByRole("button", { name: /စာဖတ်ခြင်း/ }));
  fireEvent.change(panel.getByLabelText("စာလုံးအရွယ်အစား"), { target: { value: "23" } });
  fireEvent.click(panel.getByRole("switch", { name: /အာရုံစိုက် ဖတ်ရှုရန်/ }));
  expect(document.querySelector(".story-world")).toHaveStyle({ "--reader-font-size": "23px" });
  expect(document.querySelector(".story-world")).toHaveClass("reader-focus-mode");
  view.unmount(); renderReader();
  expect(document.querySelector(".story-world")).toHaveClass("world-sepia", "reader-focus-mode");
  expect(document.querySelector(".story-world")).toHaveStyle({ "--reader-font-size": "23px" });
});

it("applies playback speed and volume to actual story audio elements", () => {
  renderReader(); const panel = settings();
  fireEvent.click(panel.getByRole("button", { name: /အသံနားထောင်ခြင်း/ }));
  fireEvent.click(panel.getByRole("radio", { name: "1.5×" }));
  fireEvent.change(panel.getByLabelText("အသံအတိုးအကျယ်"), { target: { value: "0.35" } });
  const audio = screen.getByLabelText("ပုံပြင်အသံဖိုင်") as HTMLAudioElement;
  expect(audio.playbackRate).toBe(1.5); expect(audio.volume).toBe(0.35);
  expect(JSON.parse(localStorage.getItem(readerPreferencesKey) || "{}").playbackRate).toBe(1.5);
});

it("pauses reader audio when the sleep timer expires", () => {
  vi.useFakeTimers(); const pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  renderReader(); const panel = settings();
  fireEvent.click(panel.getByRole("button", { name: /အသံနားထောင်ခြင်း/ }));
  fireEvent.click(panel.getByRole("button", { name: "5 မိနစ်" }));
  expect(Number(localStorage.getItem(sleepTimerKey))).toBeGreaterThan(Date.now());
  document.querySelectorAll("audio").forEach((audio) => Object.defineProperty(audio, "paused", { configurable: true, value: false }));
  act(() => vi.advanceTimersByTime(5 * 60_000));
  expect(pause).toHaveBeenCalled();
  expect(localStorage.getItem(sleepTimerKey)).toBe("0");
});

it("honors disabled reading history and resets preferences without deleting favorites", () => {
  localStorage.setItem(readerPreferencesKey, JSON.stringify({ ...defaultReaderPreferences, rememberHistory: false, fontSize: 24 }));
  localStorage.setItem(favoriteKey, '["one"]');
  renderReader(); expect(localStorage.getItem(historyKey)).toBeNull();
  const panel = settings();
  fireEvent.click(panel.getByRole("button", { name: "မူလ setting ပြန်ထားရန်" }));
  fireEvent.click(panel.getByRole("button", { name: "အတည်ပြုသည်" }));
  expect(JSON.parse(localStorage.getItem(readerPreferencesKey) || "{}")).toEqual(defaultReaderPreferences);
  expect(localStorage.getItem(favoriteKey)).toBe('["one"]');
});

it("validates imported backup values and rejects unrelated JSON", () => {
  expect(() => parseReaderBackup('{"hello":"world"}')).toThrow();
  const backup = parseReaderBackup(JSON.stringify({ app: "pyonpyin-reader", version: 1, preferences: { fontSize: 999, playbackRate: 99, theme: "invalid" }, favorites: ["one", "one", 3], history: ["one"] }));
  expect(backup.preferences.fontSize).toBe(26); expect(backup.preferences.playbackRate).toBe(2);
  expect(backup.preferences.theme).toBe("light"); expect(backup.favorites).toEqual(["one"]);
  expect(validateReaderPreferences({ volume: Infinity }).volume).toBe(0.8);
});

it("requires confirmation before clearing a saved list", () => {
  localStorage.setItem(favoriteKey, '["one"]');
  renderReader(); const panel = settings();
  fireEvent.click(panel.getByRole("button", { name: /ကိုယ်ပိုင်မှတ်တမ်း/ }));
  fireEvent.click(panel.getAllByRole("button", { name: "ရှင်းရန်" })[0]);
  expect(localStorage.getItem(favoriteKey)).toBe('["one"]');
  fireEvent.click(panel.getByRole("button", { name: "အတည်ပြုသည်" }));
  expect(localStorage.getItem(favoriteKey)).toBe("[]");
});

it("imports a validated local backup and updates the current UI", async () => {
  renderReader(); const panel = settings();
  fireEvent.click(panel.getByRole("button", { name: /ကိုယ်ပိုင်မှတ်တမ်း/ }));
  const backup = new File([JSON.stringify({ app: "pyonpyin-reader", version: 1, preferences: { ...defaultReaderPreferences, theme: "dark", fontSize: 22 }, favorites: ["one"], history: [] })], "backup.json", { type: "application/json" });
  fireEvent.change(panel.getByLabelText(/Backup ပြန်ထည့်ရန်/), { target: { files: [backup] } });
  await waitFor(() => expect(document.querySelector(".story-world")).toHaveClass("world-night"));
  expect(JSON.parse(localStorage.getItem(readerPreferencesKey) || "{}").fontSize).toBe(22);
  expect(localStorage.getItem(favoriteKey)).toBe('["one"]');
});

it("warns when browser storage cannot persist settings", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Quota"); });
  renderReader(); const panel = settings();
  expect(panel.getByRole("alert")).toHaveTextContent("Browser storage");
  fireEvent.click(panel.getByRole("radio", { name: "ညအမှောင်" }));
  expect(document.querySelector(".story-world")).toHaveClass("world-night");
});
