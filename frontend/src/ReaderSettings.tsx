import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Palette, BookOpen, Headphones, Database, X, Check, Sparkles, Sun, Moon, Monitor, Coffee, RotateCcw, Download, Upload, Heart, History, ShieldCheck, Timer, Volume2, SlidersHorizontal, CheckCircle2 } from "lucide-react";
import { defaultReaderPreferences, type ReaderPreferences } from "./readerPreferences";
import { defaultStoryArt } from "./uiAssets";

export function ReaderAudio({ preferences, update, ...props }: { preferences: ReaderPreferences; update: (patch: Partial<ReaderPreferences>) => void; src: string; "aria-label": string; className?: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => { if (ref.current) ref.current.playbackRate = preferences.playbackRate; }, [preferences.playbackRate]);
  useEffect(() => { if (ref.current) ref.current.volume = preferences.volume; }, [preferences.volume]);
  return <audio ref={ref} controls preload="metadata" {...props} onLoadedMetadata={() => { if (ref.current) { ref.current.playbackRate = preferences.playbackRate; ref.current.volume = preferences.volume; } }} onRateChange={(event) => update({ playbackRate: event.currentTarget.playbackRate })} onVolumeChange={(event) => update({ volume: event.currentTarget.volume })} onPlay={(event) => {
    document.querySelectorAll<HTMLAudioElement>(".story-world audio").forEach((audio) => { if (audio !== event.currentTarget && !audio.paused) audio.pause(); });
  }} />;
}

function Toggle({ label, description, checked, change }: { label: string; description: string; checked: boolean; change: (value: boolean) => void }) {
  return <label className="reader-setting-toggle"><span><strong>{label}</strong><small>{description}</small></span><input role="switch" type="checkbox" checked={checked} onChange={(event) => change(event.target.checked)} /><span className="reader-switch-track" aria-hidden="true" /></label>;
}

export function ReaderSettings({ preferences, update, close, storageError, favoriteCount, historyCount, clearData, exportData, importData, sleepSeconds, setSleepTimer, audioUrl, storyTitle }: {
  preferences: ReaderPreferences; update: (patch: Partial<ReaderPreferences>) => void; close: () => void; storageError: string;
  favoriteCount: number; historyCount: number; clearData: (kind: "favorites" | "history") => void;
  exportData: () => void; importData: (file: File) => Promise<void>;
  sleepSeconds: number; setSleepTimer: (minutes: number) => void; audioUrl?: string; storyTitle?: string;
}) {
  const [tab, setTab] = useState("appearance");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState<"favorites" | "history" | "reset" | null>(null);
  const [importing, setImporting] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; closeRef.current?.focus();
    return () => { document.body.style.overflow = overflow; if (previous?.isConnected) previous.focus(); };
  }, []);
  useEffect(() => { if (confirm) dialogRef.current?.querySelector<HTMLElement>(".reader-confirm")?.scrollIntoView?.({ block: "nearest" }); }, [confirm]);
  const tabs = [{ id: "appearance", label: "အပြင်အဆင်", en: "Appearance", icon: Palette }, { id: "reading", label: "စာဖတ်ခြင်း", en: "Reading", icon: BookOpen }, { id: "audio", label: "အသံနားထောင်ခြင်း", en: "Audio", icon: Headphones }, { id: "data", label: "ကိုယ်ပိုင်မှတ်တမ်း", en: "Your data", icon: Database }];
  const fileImport = async (file?: File) => {
    if (!file) return;
    setImporting(true); setMessage("");
    try { await importData(file); setMessage("Backup ပြန်ထည့်ပြီးပါပြီ။ Setting နှင့် မှတ်တမ်းများ ပြန်ရပါပြီ။"); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Backup ဖိုင်ဖတ်မရပါ။"); }
    finally { setImporting(false); }
  };
  const applyConfirm = () => {
    if (!confirm) return;
    if (confirm === "reset") { update(defaultReaderPreferences); setSleepTimer(0); setMessage("Setting များကို မူလအတိုင်း ပြန်ထားပြီးပါပြီ။ Favorites နှင့် History ကို မဖျက်ပါ။"); }
    else { clearData(confirm); setMessage("မှတ်တမ်းကို ရှင်းပြီးပါပြီ။"); }
    setConfirm(null);
  };
  return <div className="reader-settings-backdrop" onClick={close}><section className="reader-settings" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="reader-settings-title" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
    if (event.key === "Escape") close();
    if (event.key === "Tab") {
      const elements = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href]') || []).filter((element) => !element.closest("[hidden]"));
      const first = elements[0]; const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }}>
    <header className="reader-settings-header"><div className="reader-settings-avatar"><Sparkles size={27} /></div><div><span>MAKE YOURSELF AT HOME</span><h2 id="reader-settings-title">သင့်စိတ်ကြိုက် ပုံပြင်ကမ္ဘာ</h2><p>ဖတ်ရှုခြင်းနဲ့ နားထောင်ခြင်းကို သင့်စိတ်တိုင်းကျ ပြင်ဆင်ပါ။</p></div><button ref={closeRef} className="reader-settings-close" onClick={close} aria-label="Settings ပိတ်ရန်"><X size={21} /></button></header>
    <div className="reader-settings-layout"><aside className="reader-settings-nav"><div className="reader-settings-identity"><span>စာ</span><div><strong>စာဖတ်သူ</strong><small>Your personal space</small></div></div><nav aria-label="Settings အပိုင်းများ">{tabs.map(({ id, label, en, icon: Icon }) => <button className={tab === id ? "active" : ""} aria-pressed={tab === id} key={id} onClick={() => { setTab(id); setMessage(""); setConfirm(null); }}><Icon size={20} /><span>{label}<small>{en}</small></span></button>)}</nav><div className="reader-settings-local"><ShieldCheck size={18} /><span>ဤ browser ထဲမှာပဲ<br />သိမ်းပေးပါတယ်</span></div></aside>
    <main className="reader-settings-main">
      <div className="reader-settings-section-title"><span className="reader-settings-section-icon"><SlidersHorizontal size={19} /></span><div><h3>{tabs.find((item) => item.id === tab)?.label}</h3><p>ပြောင်းလဲမှုကို ချက်ချင်း အသုံးပြုပြီး သိမ်းပေးမည်။</p></div></div>
      {tab === "appearance" && <><section className="reader-setting-card"><h4>အရောင်ပုံစံ</h4><p>သင်နှစ်သက်တဲ့ စာဖတ်ခန်းကို ရွေးပါ။</p><div className="reader-theme-grid" role="radiogroup" aria-label="အရောင်ပုံစံ">{([{ id: "light", label: "နေ့အလင်း", icon: Sun }, { id: "dark", label: "ညအမှောင်", icon: Moon }, { id: "sepia", label: "စက္ကူရောင်", icon: Coffee }, { id: "system", label: "စက်အတိုင်း", icon: Monitor }] as const).map(({ id, label, icon: Icon }) => <button className={`reader-theme-choice theme-${id} ${preferences.theme === id ? "selected" : ""}`} key={id} role="radio" aria-checked={preferences.theme === id} onClick={() => update({ theme: id })}><div className="reader-theme-mini"><span /><span /><span /></div><span><Icon size={15} />{label}{preferences.theme === id && <Check size={14} />}</span></button>)}</div></section>
      <section className="reader-setting-card"><h4>စိတ်ကြိုက် အဓိကအရောင်</h4><div className="reader-accent-options" role="radiogroup" aria-label="အဓိကအရောင်">{([{ id: "blue", label: "ပင်လယ်ပြာ" }, { id: "violet", label: "ခရမ်းရောင်" }, { id: "green", label: "သစ်ရွက်စိမ်း" }] as const).map(({ id, label }) => <button role="radio" aria-checked={preferences.accent === id} className={preferences.accent === id ? "selected" : ""} key={id} onClick={() => update({ accent: id })}><span className={`reader-accent-swatch accent-${id}`}>{preferences.accent === id && <Check size={15} />}</span>{label}</button>)}</div></section>
      <section className="reader-setting-card"><Toggle label="လှုပ်ရှားမှု လျှော့ရန်" description="ကတ်၊ မီနူးတို့၏ animation ကို ရပ်ပေးမည်။" checked={preferences.reduceMotion} change={(value) => update({ reduceMotion: value })} /></section></>}
      {tab === "reading" && <><section className="reader-setting-card"><div className="reader-range-label"><label htmlFor="reader-font-size">စာလုံးအရွယ်အစား</label><output>{preferences.fontSize}px</output></div><input id="reader-font-size" type="range" min="14" max="26" step="1" value={preferences.fontSize} onChange={(event) => update({ fontSize: Number(event.target.value) })} /><div className="reader-range-hints"><span>သေး</span><span>ကြီး</span></div></section>
      <section className="reader-setting-card"><div className="reader-range-label"><label htmlFor="reader-line-height">စာကြောင်းကြား အကွာအဝေး</label><output>{preferences.lineHeight.toFixed(1)}×</output></div><input id="reader-line-height" type="range" min="1.8" max="3" step="0.1" value={preferences.lineHeight} onChange={(event) => update({ lineHeight: Number(event.target.value) })} /></section>
      <section className="reader-setting-card reader-settings-two-columns"><label>စာလုံးပုံစံ<select value={preferences.font} onChange={(event) => update({ font: event.target.value as ReaderPreferences["font"] })}><option value="myanmar">Myanmar Text · ရိုးရှင်း</option><option value="serif">Serif · စာအုပ်ပုံစံ</option></select></label><label>ဖတ်ရှုသည့် စာမျက်နှာအကျယ်<select value={preferences.readingWidth} onChange={(event) => update({ readingWidth: event.target.value as ReaderPreferences["readingWidth"] })}><option value="comfortable">ကျစ်လစ် · ဖတ်ရလွယ်</option><option value="wide">ကျယ်ကျယ် · အပြည့်</option></select></label></section>
      <section className="reader-setting-card"><Toggle label="အာရုံစိုက် ဖတ်ရှုရန်" description="ပုံပြင်ဖတ်ချိန်မှာ ညာဘက် preview နှင့် အလှပုံများကို ဝှက်ပေးမည်။" checked={preferences.focusMode} change={(value) => update({ focusMode: value })} /></section></>}
      {tab === "audio" && <><section className="reader-setting-card"><h4>အသံဖတ်နှုန်း</h4><p>ပုံပြင်အသံအားလုံးတွင် အသုံးပြုမည်။</p><div className="reader-speed-options" role="radiogroup" aria-label="အသံဖတ်နှုန်း">{[0.75, 1, 1.25, 1.5, 2].map((rate) => <button role="radio" aria-checked={preferences.playbackRate === rate} className={preferences.playbackRate === rate ? "selected" : ""} onClick={() => update({ playbackRate: rate })} key={rate}>{rate}×</button>)}</div></section>
      <section className="reader-setting-card"><div className="reader-range-label"><label htmlFor="reader-volume"><Volume2 size={17} />အသံအတိုးအကျယ်</label><output>{Math.round(preferences.volume * 100)}%</output></div><input id="reader-volume" type="range" min="0" max="1" step="0.05" value={preferences.volume} onChange={(event) => update({ volume: Number(event.target.value) })} /></section>
      <section className="reader-setting-card"><h4><Timer size={18} />အိပ်ချိန် အသံအလိုအလျောက်ရပ်ရန်</h4><p>ရွေးထားသည့်အချိန် ပြည့်လျှင် ဖွင့်ထားသော ပုံပြင်အသံကို ရပ်ပေးမည်။</p><div className="reader-speed-options">{[5, 15, 30, 60].map((minutes) => <button onClick={() => setSleepTimer(minutes)} key={minutes}>{minutes} မိနစ်</button>)}</div>{sleepSeconds > 0 && <div className="reader-timer-active" role="status"><Timer size={17} /><strong>{Math.floor(sleepSeconds / 60)}:{String(sleepSeconds % 60).padStart(2, "0")} ကျန်သည်</strong><button onClick={() => setSleepTimer(0)}>ပယ်ဖျက်ရန်</button></div>}</section>
      <section className="reader-setting-card"><h4>အသံ setting စမ်းနားထောင်ရန်</h4>{audioUrl ? <><p>{storyTitle}</p><ReaderAudio preferences={preferences} update={update} src={audioUrl} aria-label="Settings အသံစမ်းနားထောင်ရန်" /></> : <p>အသံပါတဲ့ ပုံပြင်တစ်ပုဒ် ရွေးပြီး စမ်းနားထောင်နိုင်ပါသည်။</p>}</section></>}
      {tab === "data" && <><div className="reader-data-stats"><div><Heart size={23} /><strong>{favoriteCount}</strong><span>သိမ်းထားသော ပုံပြင်</span></div><div><History size={23} /><strong>{historyCount}</strong><span>ဖတ်ရှုမှုမှတ်တမ်း</span></div></div>
      <section className="reader-setting-card"><Toggle label="ဖတ်ရှုမှုမှတ်တမ်း သိမ်းရန်" description="ပိတ်ထားလျှင် နောက်ဖတ်သောပုံပြင်များကို History ထဲ မထည့်ပါ။" checked={preferences.rememberHistory} change={(value) => update({ rememberHistory: value })} /></section>
      <section className="reader-setting-card"><h4>သင့်မှတ်တမ်းကို သင်စီမံပါ</h4><p>Settings၊ Favorites နှင့် History ပါဝင်သည့် JSON ဖိုင်အဖြစ် သိမ်းနိုင်သည်။ ပြန်ထည့်လျှင် လက်ရှိ browser မှတ်တမ်းကို အစားထိုးမည်။</p><div className="reader-data-actions"><button onClick={() => { try { exportData(); setMessage("Backup downloaded."); } catch { setMessage("Backup download failed. Please try again."); } }}><Download size={17} />Backup သိမ်းရန်</button><label><Upload size={17} />{importing ? "ဖတ်နေသည်…" : "Backup ပြန်ထည့်ရန်"}<input type="file" accept=".json,application/json" disabled={importing} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void fileImport(file); }} /></label></div></section>
      <section className="reader-setting-card reader-danger-zone"><h4>မှတ်တမ်း ရှင်းလင်းရန်</h4><div><span>Favorites စာရင်း</span><button disabled={!favoriteCount} onClick={() => setConfirm("favorites")}>ရှင်းရန်</button></div><div><span>History စာရင်း</span><button disabled={!historyCount} onClick={() => setConfirm("history")}>ရှင်းရန်</button></div></section></>}
      {confirm && <div className="reader-confirm" role="alert"><strong>{confirm === "reset" ? "Setting များကို မူလအတိုင်း ပြန်ထားမလား။" : "ဤ browser မှာ သိမ်းထားသော စာရင်းကို ရှင်းမလား။"}</strong><p>{confirm === "reset" ? "Favorites နှင့် History ကို ဆက်သိမ်းထားပါမည်။" : "လိုအပ်လျှင် Backup အရင်သိမ်းပါ။ ပုံပြင်မူရင်းများကို မဖျက်ပါ။"}</p><div><button onClick={applyConfirm}>အတည်ပြုသည်</button><button onClick={() => setConfirm(null)}>မလုပ်တော့ပါ</button></div></div>}
      {message && <p className="reader-settings-message" role="status">{message}</p>}{storageError && <p className="reader-settings-error" role="alert">{storageError}</p>}
    </main><aside className="reader-settings-preview"><span className="reader-preview-label"><Sparkles size={15} />LIVE PREVIEW</span><img src={defaultStoryArt} alt="" /><div><small>သင့်ရဲ့ စာဖတ်ခန်း</small><h3>ပုံပြင်တစ်ပုဒ်၊ ကမ္ဘာတစ်ခု</h3><p style={{ fontSize: preferences.fontSize, lineHeight: preferences.lineHeight, fontFamily: preferences.font === "serif" ? 'Georgia,"Myanmar Text",serif' : '"Myanmar Text","Noto Sans Myanmar",sans-serif' } as CSSProperties}>တစ်ခါတုန်းက တောင်တန်းတွေကြားမှာ ရွာလေးတစ်ရွာ ရှိခဲ့တယ်။ မနက်ခင်းအလင်းရောင်နဲ့အတူ ပုံပြင်အသစ်တစ်ပုဒ် စတင်ခဲ့တယ်။</p><span className="reader-preview-badge"><CheckCircle2 size={14} />သင့်အပြောင်းအလဲကို ချက်ချင်းမြင်ရသည်</span></div></aside></div>
    <footer className="reader-settings-footer"><button className="reader-reset-button" onClick={() => setConfirm("reset")}><RotateCcw size={16} />မူလ setting ပြန်ထားရန်</button><span><CheckCircle2 size={15} />{storageError ? "လက်ရှိစာမျက်နှာတွင်သာ အသုံးပြုနေသည်" : "ဤ browser တွင် အလိုအလျောက် သိမ်းထားသည်"}</span><button className="reader-settings-done" onClick={close}>ပြီးပါပြီ <Check size={16} /></button></footer>
  </section></div>;
}
