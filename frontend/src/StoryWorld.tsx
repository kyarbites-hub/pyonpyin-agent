import { useEffect, useState, type ReactNode, type CSSProperties } from "react";
import { Link, NavLink, useNavigate, useSearchParams } from "react-router-dom";
import { BookOpen, House, Heart, History, Headphones, Search, Settings2, Moon, Sun, Globe2, ChevronRight, ArrowRight, Clock3, ShieldCheck, Menu, X, Mountain, Sparkles, Leaf, Smile, Users, Share2 } from "lucide-react";
import type { PublicStory } from "./api";
import { defaultStoryArt } from "./uiAssets";
import { ReaderAudio, ReaderSettings } from "./ReaderSettings";
import { loadReaderPreferences, validateReaderPreferences, readerPreferencesKey, favoriteKey, historyKey, sleepTimerKey, parseReaderBackup, pauseReaderAudio, type ReaderPreferences } from "./readerPreferences";

function storedIds(key: string): string[] {
  try { const value: unknown = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : []; } catch { return []; }
}
function remember(key: string, ids: string[]) { try { localStorage.setItem(key, JSON.stringify(ids)); } catch { /* browser storage ပိတ်ထားလျှင် လက်ရှိစာမျက်နှာတွင် ဆက်သုံးနိုင်သည်။ */ } }
const topics = [{ label: "Adventure", mm: "စွန့်စားခန်း", icon: Mountain, query: "စွန့်စား" }, { label: "Fantasy", mm: "စိတ်ကူးယဉ်", icon: Sparkles, query: "စိတ်ကူး" }, { label: "Friendship", mm: "မိတ်ဆွေများ", icon: Users, query: "မိတ်ဆွေ" }, { label: "Life lessons", mm: "ဘဝသင်ခန်းစာ", icon: Leaf, query: "သင်ခန်းစာ" }, { label: "Comedy", mm: "ပျော်ရွှင်စရာ", icon: Smile, query: "ပျော်" }];

export function StoryWorld({ stories, error, reload, mode = "home", storyId, heroImage = "" }: { stories: PublicStory[] | null; error: string; reload: () => Promise<void>; mode?: "home" | "library" | "story"; storyId?: string; heroImage?: string }) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState("");
  const [favorites, setFavorites] = useState(() => storedIds(favoriteKey));
  const [history, setHistory] = useState(() => storedIds(historyKey));
  const [readerPrefs, setReaderPrefs] = useState(loadReaderPreferences);
  const [storageError, setStorageError] = useState("");
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches || false);
  const [sleepDeadline, setSleepDeadline] = useState(() => {
    try { const value = Number(localStorage.getItem(sleepTimerKey)); return Number.isFinite(value) && value > 0 && value < Date.now() + 3_600_001 ? value : 0; } catch { return 0; }
  });
  const [sleepSeconds, setSleepSeconds] = useState(0);
  const night = readerPrefs.theme === "dark" || readerPrefs.theme === "system" && systemDark;
  const [preferences, setPreferences] = useState(false);
  const [menu, setMenu] = useState(false);
  const [shareNotice, setShareNotice] = useState("");
  const query = params.get("q") || "";
  const category = params.get("category") || "ALL";
  const collection = params.get("collection") || "";
  const rows = stories || [];
  const updatePrefs = (patch: Partial<ReaderPreferences>) => setReaderPrefs((current) => {
    const next = validateReaderPreferences({ ...current, ...patch });
    return JSON.stringify(next) === JSON.stringify(current) ? current : next;
  });
  useEffect(() => {
    try { localStorage.setItem(readerPreferencesKey, JSON.stringify(readerPrefs)); setStorageError(""); }
    catch { setStorageError("Browser storage ပိတ်ထားသည် သို့မဟုတ် နေရာမလောက်ပါ။ လက်ရှိစာမျက်နှာတွင်သာ အသုံးပြုနိုင်ပါမည်။"); }
  }, [readerPrefs]);
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const change = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media?.addEventListener?.("change", change);
    return () => media?.removeEventListener?.("change", change);
  }, []);
  const setSleepTimer = (minutes: number) => {
    const deadline = minutes > 0 ? Date.now() + minutes * 60_000 : 0;
    setSleepDeadline(deadline);
    try { localStorage.setItem(sleepTimerKey, String(deadline)); }
    catch { setStorageError("Sleep timer ကို ဤစာမျက်နှာပိတ်သွားလျှင် ဆက်သိမ်းထားမရပါ။"); }
  };
  useEffect(() => {
    if (!sleepDeadline) { setSleepSeconds(0); return; }
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((sleepDeadline - Date.now()) / 1000));
      setSleepSeconds(remaining);
      if (!remaining) { pauseReaderAudio(); setSleepTimer(0); }
    };
    tick(); const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [sleepDeadline]);
  const clearData = (kind: "favorites" | "history") => {
    if (kind === "favorites") { setFavorites([]); remember(favoriteKey, []); }
    else { setHistory([]); remember(historyKey, []); }
  };
  const exportData = () => {
    const data = { app: "pyonpyin-reader", version: 1, exportedAt: new Date().toISOString(), preferences: readerPrefs, favorites, history };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "pyonpyin-reader-backup.json";
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const importData = async (file: File) => {
    if (file.size > 1024 * 1024) throw new Error("Backup ဖိုင်ကို 1 MB အောက် ရွေးပါ။");
    const text = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("ဖိုင်ဖတ်မရပါ။")); reader.readAsText(file); });
    let data: ReturnType<typeof parseReaderBackup>;
    try { data = parseReaderBackup(text); } catch { throw new Error("PyonPyin Settings မှ ထုတ်ထားသော backup JSON ဖိုင်ကို ရွေးပါ။"); }
    const keys = [readerPreferencesKey, favoriteKey, historyKey];
    const old = keys.map((key) => localStorage.getItem(key));
    try { [data.preferences, data.favorites, data.history].forEach((value, index) => localStorage.setItem(keys[index], JSON.stringify(value))); }
    catch {
      keys.forEach((key, index) => { try { if (old[index] === null) localStorage.removeItem(key); else localStorage.setItem(key, old[index]!); } catch {} });
      throw new Error("Browser storage နေရာမလောက်သဖြင့် backup ပြန်ထည့်မရပါ။");
    }
    setReaderPrefs(data.preferences); setFavorites(data.favorites); setHistory(data.history);
  };
  useEffect(() => {
    if (!readerPrefs.rememberHistory || mode !== "story" || !storyId || !rows.some((story) => story.story_id === storyId)) return;
    setHistory((current) => { const next = [storyId, ...current.filter((id) => id !== storyId)].slice(0, 50); remember(historyKey, next); return next; });
  }, [mode, storyId, stories, readerPrefs.rememberHistory]);
  const toggleFavorite = (id: string) => setFavorites((current) => { const next = current.includes(id) ? current.filter((value) => value !== id) : [...current, id]; remember(favoriteKey, next); return next; });
  const previewStory = (id: string) => {
    // Preview rail မပြသော ဖုန်း/မျက်နှာပြင်သေးတွင် ပုံပြင်စာမျက်နှာကို တိုက်ရိုက်ဖွင့်သည်။
    if (window.matchMedia?.("(max-width:1080px)").matches) navigate(`/stories/${id}`);
    else setSelectedId(id);
  };
  const filter = (key: string, value: string) => { const next = new URLSearchParams(params); if (value && value !== "ALL") next.set(key, value); else next.delete(key); setParams(next); };
  const filtered = rows.filter((story) => (category === "ALL" || story.category === category) && `${story.title} ${story.story}`.toLowerCase().includes(query.toLowerCase()) && (collection !== "favorites" || favorites.includes(story.story_id)) && (collection !== "history" || history.includes(story.story_id)));
  if (collection === "history") filtered.sort((a, b) => history.indexOf(a.story_id) - history.indexOf(b.story_id));
  const selected = mode === "story" ? rows.find((story) => story.story_id === storyId) : filtered.find((story) => story.story_id === selectedId) || filtered[0];
  const title = collection === "favorites" ? "သိမ်းထားသော ပုံပြင်များ" : collection === "history" ? "ဖတ်ရှုခဲ့သော ပုံပြင်များ" : "ပုံပြင်စာကြည့်တိုက်";
  const favoriteButton = (story: PublicStory, className = "") => <button className={`world-favorite ${favorites.includes(story.story_id) ? "saved" : ""} ${className}`} aria-label={`${story.title} ${favorites.includes(story.story_id) ? "သိမ်းထားရာမှ ဖယ်ရန်" : "သိမ်းထားရန်"}`} aria-pressed={favorites.includes(story.story_id)} onClick={() => toggleFavorite(story.story_id)}><Heart size={20} /></button>;
  const cards = (items: PublicStory[]) => <div className="world-story-grid">{items.map((story) => <article className={`world-story-card ${selected?.story_id === story.story_id ? "is-selected" : ""}`} key={story.story_id}>
    <div className="world-card-art"><button className="world-preview-button" aria-label={`${story.title} အကြိုကြည့်ရန်`} onClick={() => previewStory(story.story_id)}><img src={story.cover_image_url || defaultStoryArt} alt="" loading="lazy" /></button><span className={`world-audience ${story.category === "ADULT" ? "adult" : ""}`}>{story.category === "CHILDREN" ? "Kids" : "Adult"}</span>{favoriteButton(story)}</div>
    <div className="world-card-copy"><Link to={`/stories/${story.story_id}`}><h3>{story.title}</h3></Link><p>{story.story.slice(0, 72)}…</p><div className="world-card-meta"><span>{story.audio_url ? <Headphones size={13} /> : <BookOpen size={13} />}{story.audio_url ? "အသံပါဝင်သည်" : "ဖတ်ရှုရန်"}</span><span><Clock3 size={13} />{Math.max(1, Math.ceil(story.story.length / 450))} မိနစ်</span></div></div>
  </article>)}</div>;
  const section = (heading: string, items: PublicStory[], link: string): ReactNode => <section className="world-collection"><div className="world-section-heading"><h2>{heading}</h2><Link to={link}>အားလုံးကြည့်ရန် <ArrowRight size={15} /></Link></div>{items.length ? cards(items.slice(0, 8)) : <div className="world-empty">ဤအမျိုးအစားအတွက် ထုတ်ဝေထားသော ပုံပြင် မရှိသေးပါ။</div>}</section>;
  const share = async () => { try { await navigator.clipboard.writeText(`${location.origin}${location.pathname}#/stories/${selected?.story_id}`); setShareNotice("ပုံပြင် link ကူးယူပြီးပါပြီ။"); } catch { setShareNotice("အပေါ်ရှိ လိပ်စာကို ကူးယူမျှဝေနိုင်ပါသည်။"); } };
  return <div className={`story-world ${night ? "world-night" : ""} ${readerPrefs.theme === "sepia" ? "world-sepia" : ""} reader-accent-${readerPrefs.accent} reader-width-${readerPrefs.readingWidth} ${readerPrefs.focusMode && mode === "story" ? "reader-focus-mode" : ""} ${readerPrefs.reduceMotion ? "reader-reduce-motion" : ""}`} style={{ "--reader-font-size": `${readerPrefs.fontSize}px`, "--reader-line-height": readerPrefs.lineHeight, "--reader-font-family": readerPrefs.font === "serif" ? 'Georgia,"Myanmar Text",serif' : '"Myanmar Text","Noto Sans Myanmar",sans-serif' } as CSSProperties}>
    <aside className={`world-sidebar ${menu ? "world-menu-open" : ""}`}><Link className="world-brand" to="/"><span className="world-logo"><BookOpen size={35} /><Sparkles size={14} /></span><span><strong>PyonPyin</strong><small>Story World</small></span></Link><button className="world-mobile-close" onClick={() => setMenu(false)} aria-label="မီနူးပိတ်ရန်"><X /></button>
      <nav aria-label="စာဖတ်သူမီနူး"><NavLink to="/" end onClick={() => setMenu(false)}><House size={21} />Home</NavLink><Link to="/stories" className={mode === "library" && !category.includes("CHILDREN") && !category.includes("ADULT") && !collection ? "active" : ""} onClick={() => setMenu(false)}><BookOpen size={21} />Stories</Link><Link className={category === "CHILDREN" ? "active" : ""} to="/stories?category=CHILDREN" onClick={() => setMenu(false)}><Smile size={21} />Kids Stories</Link><Link className={category === "ADULT" ? "active" : ""} to="/stories?category=ADULT" onClick={() => setMenu(false)}><Mountain size={21} />Adult Stories</Link><Link className={collection === "favorites" ? "active" : ""} to="/stories?collection=favorites" onClick={() => setMenu(false)}><Heart size={21} />Favorites<span>{favorites.length || ""}</span></Link><Link className={collection === "history" ? "active" : ""} to="/stories?collection=history" onClick={() => setMenu(false)}><History size={21} />My History</Link><button onClick={() => { setPreferences(true); setMenu(false); }}><Settings2 size={21} />Settings</button></nav>
      <div className="world-sidebar-art"><img src={defaultStoryArt} alt="" /><strong>PyonPyin</strong><p>ပုံပြင်တစ်ပုဒ်ဖတ်တိုင်း<br />စိတ်ကူးကမ္ဘာအသစ်ဆီ…</p></div><Link className="world-admin-entry" to="/admin"><ShieldCheck size={16} />စီမံခန့်ခွဲမှု <ChevronRight size={14} /></Link>
    </aside>
    <div className="world-workspace"><header className="world-topbar"><button className="world-mobile-toggle" onClick={() => setMenu(true)} aria-label="မီနူးဖွင့်ရန်"><Menu /></button><form className="world-search" onSubmit={(event) => { event.preventDefault(); navigate(`/stories?q=${encodeURIComponent(query)}`); }}><Search size={21} /><input aria-label="ပုံပြင်ရှာရန်" value={query} placeholder="ပုံပြင်လေး ရှာရန်…" onChange={(event) => filter("q", event.target.value)} /></form><div className="world-top-actions">{sleepSeconds > 0 && <button className="reader-sleep-chip" aria-label="Sleep timer" onClick={() => setPreferences(true)}><Clock3 size={14} />{Math.floor(sleepSeconds / 60)}:{String(sleepSeconds % 60).padStart(2, "0")}</button>}<button aria-label={night ? "နေ့အလင်းပုံစံ" : "ညဖတ်ပုံစံ"} onClick={() => updatePrefs({ theme: night ? "light" : "dark" })}>{night ? <Sun size={20} /> : <Moon size={20} />}</button><span className="world-language"><Globe2 size={19} />မြန်မာ</span><button className="world-reader-profile" onClick={() => setPreferences(true)}><span>စာ</span><strong>စာဖတ်သူ</strong></button></div></header>
    <div className="world-content-layout"><main className="world-main">
      {mode === "home" && !query && <><section className="world-hero" style={{ backgroundImage: `linear-gradient(90deg,rgba(9,55,112,.7),transparent 75%),url("${heroImage || defaultStoryArt}")` }}><span className="world-hero-kicker">WELCOME TO YOUR STORY WORLD</span><h1>ပုံပြင်တစ်ပုဒ်တိုင်းမှာ<br />ကမ္ဘာသစ်တစ်ခု ရှိတယ်</h1><p>ကလေးများအတွက် စိတ်ကူးယဉ်စရာ၊<br />လူကြီးများအတွက် တွေးတောစရာ ပုံပြင်များ…</p><Link className="world-yellow-button" to="/stories"><BookOpen size={20} />စတင်ဖတ်ရှုမယ် <ArrowRight size={18} /></Link><span className="world-hero-caption">ပုံပြင်တစ်ပုဒ် · ကမ္ဘာတစ်ခု</span></section>
        <section className="world-topics"><div className="world-section-heading"><h2>စိတ်ကြိုက် အကြောင်းအရာများ</h2><span>စာသားထဲတွင် ရှာကြည့်ပါ</span></div><div className="world-topic-grid">{topics.map(({ label, mm, icon: Icon, query: word }) => <Link key={label} to={`/stories?q=${encodeURIComponent(word)}`}><Icon size={24} /><span><strong>{label}</strong><small>{mm}</small></span></Link>)}</div></section></>}
      {error ? <div className="world-empty" role="alert"><p>{error}</p><button className="world-blue-button" onClick={() => void reload()}>ပြန်ကြိုးစားရန်</button></div> : stories === null ? <div className="world-empty" role="status">ပုံပြင်များ ဖတ်နေသည်…</div> : mode === "story" ? !selected ? <div className="world-empty"><h2>ပုံပြင်ကို ရှာမတွေ့ပါ</h2><Link to="/stories">စာကြည့်တိုက်သို့ ပြန်သွားရန်</Link></div> : <article className="world-reading"><Link className="world-back" to="/stories">← ပုံပြင်စာကြည့်တိုက်သို့</Link><div className="world-reading-hero" style={{ backgroundImage: `linear-gradient(90deg,#071b32ed,#071b3299),url("${selected.cover_image_url || defaultStoryArt}")` }}><div><span className="world-audience">{selected.category === "CHILDREN" ? "Kids Stories" : "Adult Stories"}</span><h1>{selected.title}</h1><p>{selected.story.slice(0, 100)}…</p>{selected.audio_url && <ReaderAudio preferences={readerPrefs} update={updatePrefs} src={selected.audio_url} aria-label="ပုံပြင်အသံဖိုင်" />}<span className="world-published"><ShieldCheck size={15} />စစ်ဆေးပြီး ထုတ်ဝေထားသည်</span></div><img src={selected.cover_image_url || defaultStoryArt} alt={`${selected.title} မျက်နှာဖုံးပုံ`} /></div><div className="world-reading-body"><p>{selected.story}</p></div>{selected.episodes.length > 1 && <details className="world-episodes"><summary>အပိုင်းအလိုက် ဖတ်ရန် ({selected.episodes.length})</summary>{selected.episodes.map((episode) => <section key={episode.episode_number}><h2>{episode.title}</h2><p>{episode.content}</p></section>)}</details>}{Boolean(selected.quiz?.length) && <section className="world-learning"><h2>ပုံပြင်နားလည်မှု</h2>{selected.quiz?.map((item, index) => <details key={index}><summary>{item.question}</summary><p>{item.answer}</p></details>)}</section>}{selected.reflection && <section className="world-learning"><h2>စဉ်းစားကြည့်ရန်</h2><p>{selected.reflection}</p></section>}</article> : mode === "library" || query ? <section className="world-collection"><div className="world-section-heading"><h1>{title}</h1><span>{filtered.length} ပုဒ်</span></div><div className="world-filter-pills" aria-label="အမျိုးအစား စစ်ထုတ်ရန်">{[["ALL", "အားလုံး"], ["CHILDREN", "ကလေးများ"], ["ADULT", "လူကြီးများ"]].map(([id, label]) => <button className={category === id ? "selected" : ""} key={id} onClick={() => filter("category", id)}>{label}</button>)}</div>{filtered.length ? cards(filtered) : <div className="world-empty"><h2>{rows.length ? "ကိုက်ညီသော ပုံပြင် မရှိပါ" : "ပုံပြင်များ မရှိသေးပါ"}</h2><p>ရှာဖွေမှု သို့မဟုတ် အမျိုးအစားကို ပြောင်းကြည့်ပါ။</p>{collection && <p>ဤစက်တွင် သိမ်းထားသော မှတ်တမ်းများကိုသာ ပြပါသည်။</p>}</div>}</section> : <>{section("နောက်ဆုံး ထုတ်ဝေထားသော ပုံပြင်များ", rows, "/stories")}{section("ကလေးများအတွက် ပုံပြင်များ", rows.filter((story) => story.category === "CHILDREN"), "/stories?category=CHILDREN")}{section("လူကြီးများအတွက် ပုံပြင်များ", rows.filter((story) => story.category === "ADULT"), "/stories?category=ADULT")}</>}
    </main><aside className="world-detail-rail">{selected ? <><section className="world-detail-card"><div className="world-detail-art"><img src={selected.cover_image_url || defaultStoryArt} alt="" />{favoriteButton(selected)}</div><div className="world-detail-copy"><div className="world-detail-title"><h2>{selected.title}</h2><span className="world-audience">{selected.category === "CHILDREN" ? "Kids" : "Adult"}</span></div><div className="world-card-meta"><span><BookOpen size={14} />မြန်မာပုံပြင်</span><span><Clock3 size={14} />{Math.max(1, Math.ceil(selected.story.length / 450))} မိနစ်ဖတ်ချိန်</span></div><p>{selected.story.slice(0, 175)}…</p>{selected.audio_url ? <ReaderAudio key={selected.audio_url} preferences={readerPrefs} update={updatePrefs} src={selected.audio_url} aria-label="ရွေးထားသော ပုံပြင်အသံ" /> : <p className="world-no-audio">ဤပုံပြင်တွင် အသံ မပါဝင်သေးပါ။</p>}<Link className="world-blue-button" to={`/stories/${selected.story_id}`}><BookOpen size={17} />ပုံပြင်အပြည့် ဖတ်မယ်</Link></div></section><section className="world-info-card"><h3>ပုံပြင်အချက်အလက်များ</h3><dl><div><dt><Globe2 size={16} />ဘာသာစကား</dt><dd>မြန်မာ</dd></div><div><dt><Users size={16} />ပရိသတ်</dt><dd>{selected.category === "CHILDREN" ? "ကလေးများ" : "လူကြီးများ"}</dd></div><div><dt><Headphones size={16} />အသံဖိုင်</dt><dd>{selected.audio_url ? "ပါဝင်သည်" : "မပါဝင်သေး"}</dd></div><div><dt><ShieldCheck size={16} />အခြေအနေ</dt><dd className="world-published">Published</dd></div></dl><button className="world-share" onClick={() => void share()}><Share2 size={16} />မျှဝေရန်</button>{shareNotice && <p role="status">{shareNotice}</p>}</section><section className="world-reader-note"><Sparkles size={24} /><h3>သင့်စိတ်ကူးတွေ ပျံသန်းပါစေ</h3><p>နှစ်သက်တဲ့ပုံပြင်ကို နှလုံးပုံလေးနှိပ်ပြီး သိမ်းထားနိုင်ပါတယ်။</p></section></> : <section className="world-info-card"><BookOpen size={32} /><h3>ပုံပြင်တစ်ပုဒ် ရွေးကြည့်ပါ</h3><p>ရွေးလိုက်သည့် ပုံပြင်နှင့် အသံကို ဤနေရာတွင် အကြိုကြည့်နိုင်ပါသည်။</p></section>}</aside></div>
    <footer className="world-footer"><span>“ပုံပြင်လေးတစ်ပုဒ်ကနေ စိတ်ကူးတွေ အဝေးဆုံး ပျံသန်းနိုင်ပါတယ်…” <Heart size={15} /></span><strong><BookOpen size={21} />PyonPyin</strong></footer></div>
    {preferences && <ReaderSettings preferences={readerPrefs} update={updatePrefs} close={() => setPreferences(false)} storageError={storageError} favoriteCount={favorites.length} historyCount={history.length} clearData={clearData} exportData={exportData} importData={importData} sleepSeconds={sleepSeconds} setSleepTimer={setSleepTimer} audioUrl={selected?.audio_url} storyTitle={selected?.title} />}
  </div>;
}
