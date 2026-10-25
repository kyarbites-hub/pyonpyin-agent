import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AudioLines, Headphones, RefreshCw } from "lucide-react";
import { api, type AdminStory, type AudioStory, type Overview } from "./api";
import { StoryCatalogue } from "./StoryCatalogue";

export function SimpleDashboard({ counts, stories }: { counts: Overview["counts"]; stories: AdminStory[] }) {
  return <section className="simple-dashboard"><div className="dashboard-intro"><h2>ဒီနေ့ ဘာလုပ်ချင်ပါသလဲ</h2><p>ပုံပြင်ဖန်တီးပါ။ စာသားကို စစ်ဆေးပြီး AI အသံထုတ်ပါ။ အသံအားလုံးကို တစ်နေရာတည်းတွင် နားထောင်နိုင်ပါသည်။</p></div>
    <div className="dashboard-start-grid"><Link to="/admin/production" className="dashboard-start-card"><strong>၁</strong><h3>ပုံပြင်အသစ် ရေးရန်</h3><p>ခေါင်းစဉ်၊ ပရိသတ်နှင့် theme ရွေး၍ AI မူကြမ်းထုတ်ပါ။</p><span>ပုံပြင်ဖန်တီးမည် →</span></Link>
      <Link to="/admin/audio" className="dashboard-start-card audio-start"><Headphones size={30} /><h3>အသံနားထောင်ရန်</h3><p>AI ထုတ်ထားသော ပုံပြင်အသံများကို ဖွင့်နားထောင်ပါ။</p><span>အသံဖိုင်များ ဖွင့်မည် →</span></Link></div>
    <div className="dashboard-small-counts"><span>စုစုပေါင်း {stories.length} မှတ်တမ်း</span><span>လက်ရှိ Public ပေါ်ရှိ {counts.published} ပုဒ်</span></div>
    <Link className="button button-quiet" to="/admin/publishing">ပုံပြင်နှင့် အသံ ထုတ်ဝေမှုမှတ်တမ်း ကြည့်ရန် →</Link>
    <Link className="button button-quiet" to="/admin/settings">ပင်မစာမျက်နှာပုံ ပြောင်းရန် →</Link>
    <StoryCatalogue stories={stories} />
  </section>;
}

function useAudioLibrary(refreshKey = "") {
  const [stories, setStories] = useState<AudioStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = async () => {
    try { setStories(await api.audio()); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "အသံစာရင်း ဖတ်မရပါ။"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void refresh(); }, [refreshKey]);
  const active = stories.some((story) => ["QUEUED", "RUNNING"].includes(story.job?.status ?? ""));
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => { void refresh(); }, 2_000);
    return () => clearInterval(timer);
  }, [active]);
  return { stories, loading, error, refresh };
}

function audioLabel(story: AudioStory): string {
  if (["QUEUED", "RUNNING"].includes(story.job?.status ?? "")) return "AI က အသံထုတ်နေပါသည်…";
  if (!story.audio_url) return story.job?.status === "FAILED" ? "အသံထုတ်မှု မအောင်မြင်သေးပါ" : "အသံ မထုတ်ရသေးပါ";
  return story.audio_status === "READY" ? "နားထောင်စစ်ပြီး အတည်ပြုထားသည်" : "နားထောင်၍ စစ်ဆေးနိုင်ပါပြီ";
}

export function LiveAudioStudio() {
  const { stories, loading, error, refresh } = useAudioLibrary();
  const [showMissing, setShowMissing] = useState(false);
  const available = stories.filter((story) => story.audio_url).length;
  const visible = stories.filter((story) => showMissing ? !story.audio_url : Boolean(story.audio_url));
  return <section className="admin-panel audio-workspace">
    <div className="audio-workspace-heading"><div><span className="eyebrow">ပုံပြင်အသံများ</span><h2><Headphones size={24} /> အသံနားထောင်ရန်</h2><p>အသံဖိုင်ရှိသော ပုံပြင်ကို ဤနေရာမှ တိုက်ရိုက် ဖွင့်နားထောင်နိုင်ပါသည်။</p></div>
      <button className="button button-quiet" onClick={() => void refresh()}><RefreshCw size={16} /> ပြန်ဖတ်ရန်</button></div>
    <p className="audio-library-count">နားထောင်နိုင်သော ပုံပြင် — {available} / {stories.length}</p>
    <div className="catalogue-tabs"><button aria-pressed={!showMissing} onClick={() => setShowMissing(false)}>အသံထုတ်ပြီး ({available})</button><button aria-pressed={showMissing} onClick={() => setShowMissing(true)}>အသံမထုတ်ရသေး ({stories.length - available})</button></div>
    {loading && <p role="status">အသံစာရင်း ဖတ်နေပါသည်…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !stories.length && <div className="workflow-callout"><p>ပုံပြင်တစ်ပုဒ် အရင်ဖန်တီးပါ။ ပြီးလျှင် AI အသံထုတ်နိုင်ပါမည်။</p><Link to="/admin/production">ပုံပြင်အသစ် ဖန်တီးရန် →</Link></div>}
    {!loading && stories.length > 0 && !visible.length && <p>ဤစာရင်းတွင် ပုံပြင် မရှိသေးပါ။</p>}
    <div className="audio-library-grid">{visible.map((story) => <article className="audio-story-card" key={story.story_id}>
      <AudioLines size={26} /><h3>{story.title}</h3><p>{audioLabel(story)}</p>
      {story.audio_url ? <audio aria-label={`${story.title} အသံနားထောင်ရန်`} controls preload="none" src={story.audio_url} />
        : <p className="audio-empty-hint">ပုံပြင်ကို စစ်ဆေးအတည်ပြုပြီး “AI အသံထုတ်ရန်” ကိုနှိပ်ပါ။</p>}
      <Link className="button button-quiet" to={`/admin/stories/${story.story_id}`}>{story.audio_url ? "ပုံပြင်နှင့် အသံစီမံရန်" : "အသံဖန်တီးရန် ပုံပြင်ဖွင့်မည်"}</Link>
    </article>)}</div>
  </section>;
}

export function StoryAudioPanel({ storyId, csrf, refreshKey, defaultReviewer = "", onReviewed }: { storyId: string; csrf: string; refreshKey: string; defaultReviewer?: string; onReviewed?: (status: string) => void }) {
  const { stories, loading, error, refresh } = useAudioLibrary(refreshKey);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [reviewer, setReviewer] = useState("");
  // ပုံပြင်စစ်ဆေးသူအမည်ကို ပြန်သုံးပေးသော်လည်း အသံနားထောင်ပြီး အတည်ပြုခလုတ်ကို လူက နှိပ်ရမည်။
  useEffect(() => { setReviewer(defaultReviewer); }, [storyId, defaultReviewer]);
  const [narrationConsent, setNarrationConsent] = useState(false);
  const story = stories.find((row) => row.story_id === storyId);
  const active = ["QUEUED", "RUNNING"].includes(story?.job?.status ?? "");
  const canGenerate = story?.content_review_status === "APPROVED" && (story.narration_permitted || (story.original_workspace && narrationConsent));
  const perform = async (action: string, data: unknown) => {
    setBusy(true); setMessage("");
    try {
      await api.storyAction(storyId, action, data, csrf);
      if (action === "audio/review") onReviewed?.((data as { action: string }).action === "approve" ? "READY" : "NOT_READY");
      await refresh();
      setMessage(action === "jobs" ? "AI အသံထုတ်နေပါသည်။ ပြီးလျှင် ဤနေရာတွင် နားထောင်နိုင်ပါမည်။" : "အသံစစ်ဆေးချက် သိမ်းပြီးပါပြီ။");
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : "လုပ်ဆောင်မရပါ။"); }
    finally { setBusy(false); }
  };
  const generate = () => {
    if (window.confirm("Gemini ဖြင့် ဤပုံပြင်ကို အသံထုတ်မည်လား။ API quota သုံးနိုင်ပါသည်။")) void perform("jobs", { kind: "AUDIO", ...(story?.original_workspace && !story.narration_permitted ? { confirm_original_narration: narrationConsent } : {}) });
  };
  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true); setMessage("");
    try { await api.uploadAudio(storyId, file, csrf); await refresh(); setMessage("အသံဖိုင် ရပါပြီ။ အရင်နားထောင်စစ်ပါ။"); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Upload မရပါ။"); }
    finally { setBusy(false); }
  };
  return <section className="audio-listening-panel" id="story-audio" aria-label="ပုံပြင်အသံ">
    <div className="audio-workspace-heading"><div><span className="eyebrow">AI အသံဖတ်ပြခြင်း</span><h2><Headphones size={23} /> အသံနားထောင်ရန်</h2></div><Link className="text-link" to="/admin/audio">အသံအားလုံး →</Link></div>
    {loading && <p role="status">အသံအခြေအနေ ဖတ်နေပါသည်…</p>}
    {error && <p role="alert">{error}</p>}
    {story && <><p className="audio-state-label">{audioLabel(story)}</p>
      {story.audio_url ? <audio className="primary-story-player" aria-label="ဤပုံပြင်အသံ နားထောင်ရန်" controls preload="none" src={story.audio_url} />
        : <div className="audio-empty-state"><AudioLines size={28} /><p>အသံဖိုင် မရှိသေးပါ။ AI က ထုတ်ပေးရန် အောက်ပါခလုတ်ကို သုံးပါ။</p></div>}
      {!canGenerate && !story.audio_url && <div className="workflow-callout"><p>အသံမထုတ်မီ လိုအပ်သောအချက်များ</p><ul>
        {!story.narration_permitted && <li>{story.original_workspace ? "အောက်တွင် ကိုယ်ပိုင်ပုံပြင် အသံဖတ်ပြခွင့်ကို အမှန်ခြစ်ရန်" : "အသံဖတ်ပြခွင့်ကို အမှန်ခြစ်ပြီး review သိမ်းရန်"}</li>}
        {story.content_review_status !== "APPROVED" && <li>ပုံပြင်စာသားကို ဖတ်စစ်၍ အကြောင်းအရာ အတည်ပြုရန်</li>}
      </ul><a href="#story-review">အတည်ပြုရန် နေရာသို့ သွားမည် ↓</a></div>}
      {story.original_workspace && !story.narration_permitted && <label className="workflow-check"><input type="checkbox" checked={narrationConsent} disabled={busy || active} onChange={(event) => setNarrationConsent(event.target.checked)} /> ဤကိုယ်ပိုင်ပုံပြင်ကို AI အသံဖတ်ပြရန် ခွင့်ပြုသည်</label>}
      <p>အသံရရန် “AI အသံထုတ်ရန်” ကိုနှိပ်ပါ။ ထုတ်ပြီးလျှင် ဤနေရာတွင် နားထောင်နိုင်ပါမည်။</p>
      <div className="workflow-actions"><button className="button button-primary" disabled={busy || active || !canGenerate} onClick={generate}>{active ? "AI အသံထုတ်နေသည်…" : story.audio_url ? "အသံအသစ် ပြန်ထုတ်ရန်" : "AI အသံထုတ်ရန်"}</button>
        <button className="button button-quiet" disabled={busy} onClick={() => void refresh()}>အခြေအနေ ပြန်ဖတ်ရန်</button></div>
      {active && <p role="status">အခြေအနေကို အလိုအလျောက် ပြန်ဖတ်နေပါသည်။ ပြီးလျှင် အသံ player ပေါ်လာပါမည်။</p>}
      {story.audio_url && !active && <div className="audio-listening-review"><p>{story.audio_status === "READY" ? "ဤအသံကို အတည်ပြုထားပြီးပါပြီ။" : "အသံကို အရင်နားထောင်ပါ။ အသံထွက်မှန်ကန်မှ အတည်ပြုပါ။"}</p>
        <label className="editor-field">နားထောင်စစ်သူအမည်<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
        <div className="workflow-actions"><button className="button button-primary" disabled={busy || !reviewer.trim()} onClick={() => void perform("audio/review", { action: "approve", reviewer })}>နားထောင်ပြီး အသံအတည်ပြုရန်</button>
          <button className="button button-quiet" disabled={busy || !reviewer.trim()} onClick={() => void perform("audio/review", { action: "reject", reviewer })}>အသံပယ်ချရန်</button></div>
      </div>}
      <details className="audio-upload-option"><summary>ရှိပြီးသား အသံဖိုင် သုံးချင်လျှင်</summary><label className="editor-field">MP3 / WAV ဖိုင်ရွေးရန်<input type="file" accept=".mp3,.wav" disabled={busy || active || !story.narration_permitted} onChange={(event) => { void upload(event.target.files?.[0]); event.target.value = ""; }} /></label></details>
    </>}
    {message && !active && <p role="status">{story?.audio_url && message.startsWith("AI အသံထုတ်") ? "အသံထုတ်ပြီးပါပြီ။ အပေါ်က player တွင် နားထောင်နိုင်ပါပြီ။" : message}</p>}
  </section>;
}
