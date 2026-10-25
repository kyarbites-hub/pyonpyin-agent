import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type AdminStoryDetail, type LocalJob, type PlatformSettings } from "./api";

// UI အသစ်မဆောက်ခင် အစမှအဆုံးလုပ်ငန်းစဉ်ကို စမ်းနိုင်ရန် ရိုးရှင်းသော control များဖြစ်သည်။
export function MvpSettings() {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void api.settings().then(setSettings).catch((e: Error) => setError(e.message)); }, []);
  return <section className="admin-panel"><h2>ချိတ်ဆက်မှု အခြေအနေ</h2>
    {error && <p role="alert">{error}</p>}
    {settings && <dl>
      <dt>Database</dt><dd>{settings.storage}</dd>
      <dt>ပုံပြင် AI</dt><dd>{settings.gemini_configured && settings.generation_enabled ? "ချိတ်ဆက်ရန်ပြင်ဆင်ပြီး" : "Gemini key / enable setting လိုသည်"}</dd>
      <dt>မြန်မာအသံ</dt><dd>{settings.tts_provider} · {settings.tts_configured && settings.tts_enabled ? settings.voice : "ရွေးထားသော provider ၏ key / enable setting လိုသည်"}</dd>
      <dt>ထုတ်ဝေမှု</dt><dd>{settings.publishing_enabled ? "ဖွင့်ထားသည် · လူအတည်ပြုချက်လိုသည်" : "ပိတ်ထားသည်"}</dd>
      <dt>Local worker</dt><dd>{settings.local_jobs ? "သီးခြား terminal တွင် python -m pyonpyin.worker ကိုဖွင့်ပါ" : "SQLite storage လိုသည်"}</dd>
    </dl>}
    <p>ဤအခြေအနေများသည် configuration စစ်ချက်ဖြစ်ပြီး provider API အမှန်တကယ်အလုပ်လုပ်ကြောင်း မစမ်းရသေးပါ။</p>
  </section>;
}

export function MvpWorkspace({ csrf, onUpdated, onOpen }: { csrf: string; onUpdated: () => void; onOpen: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("CHILDREN");
  const [theme, setTheme] = useState("kindness");
  const [story, setStory] = useState("");
  const [jobs, setJobs] = useState<LocalJob[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = async () => {
    try {
      const settings = await api.settings();
      if (settings.local_jobs) setJobs(await api.localJobs());
    } catch (e) { setError(e instanceof Error ? e.message : "ဖတ်မရပါ"); }
  };
  useEffect(() => { void refresh(); }, []);
  const create = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api.createStory({ title, category, theme, story }, csrf);
      onUpdated(); onOpen(result.story_id);
    } catch (e) { setError(e instanceof Error ? e.message : "ဖန်တီးမရပါ"); }
    finally { setBusy(false); }
  };
  const retry = async (job: LocalJob) => {
    if (!window.confirm("Job ရလဒ်နှင့် provider usage ကိုစစ်ပြီးပါပြီလား။ Retry က API quota သုံးနိုင်ပါသည်။")) return;
    setBusy(true); setError("");
    try { await api.retryJob(job.job_id, csrf); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Retry မရပါ"); }
    finally { setBusy(false); }
  };
  return <section className="admin-panel mvp-workflow"><h2>MVP ပုံပြင်ဖန်တီးရန်</h2>
    <p>စာသားထည့်လျှင် ကိုယ်တိုင်ရေး original၊ မထည့်လျှင် theme အခြေခံ AI မူကြမ်းအဖြစ် ဖန်တီးသည်။</p>
    <form onSubmit={(event) => void create(event)}>
      <label className="editor-field">အလုပ်ခေါင်းစဉ်<input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={500} /></label>
      <label className="editor-field">ပရိသတ်<select value={category} onChange={(e) => setCategory(e.target.value)}><option value="CHILDREN">ကလေးများ</option><option value="ADULT">လူကြီးများ</option></select></label>
      <label className="editor-field">အယူအဆ<select value={theme} onChange={(e) => setTheme(e.target.value)}>{["kindness", "friendship", "courage", "nature", "resilience", "curiosity", "cooperation", "adventure", "belonging", "perseverance"].map((v) => <option key={v}>{v}</option>)}</select></label>
      <label className="editor-field">ကိုယ်တိုင်ရေးစာသား (AI ထုတ်မည်ဆိုလျှင် လွတ်ထားပါ)<textarea value={story} onChange={(e) => setStory(e.target.value)} maxLength={40000} /></label>
      <button className="button button-primary" disabled={busy}>Workspace ဖန်တီးရန်</button>
    </form>
    {error && <p role="alert" className="form-error">{error}</p>}
    <h3>Local အလုပ်မှတ်တမ်း</h3><button type="button" onClick={() => void refresh()}>အခြေအနေ ပြန်ဖတ်ရန်</button>
    <p>Job မရွေ့ပါက worker terminal ကို ဖွင့်ထားကြောင်းစစ်ပါ။ INTERRUPTED ဆိုလျှင် provider ရလဒ်ကို စစ်ပြီးမှ retry လုပ်ပါ။</p>
    {jobs.map((job) => <div className="history-row" key={job.job_id}><Link to={`/admin/stories/${job.story_id}`}>{job.story_id}</Link><span>{job.kind} · {job.status}</span><small>{job.error}</small>{["FAILED", "INTERRUPTED"].includes(job.status) && <button disabled={busy} onClick={() => void retry(job)}>Retry</button>}</div>)}
  </section>;
}

export function LiveFinder({ csrf, onUpdated }: { csrf: string; onUpdated?: () => void }) {
  const [job, setJob] = useState<LocalJob | null>(null);
  const [count, setCount] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const started = useRef(false);
  const updated = useRef(onUpdated);
  updated.current = onUpdated;
  const active = job?.status === "QUEUED" || job?.status === "RUNNING";
  useEffect(() => {
    let cancelled = false;
    // စာမျက်နှာပြန်ဖွင့်လျှင် နောက်ဆုံး discovery အခြေအနေကို ပြန်ပြသည်။ Job အသစ် မတောင်းပါ။
    void api.localJobs().then((jobs) => {
      if (!cancelled && !started.current) setJob(jobs.find((item) => item.kind === "DISCOVER") ?? null);
    }).catch((cause: Error) => { if (!cancelled) setError(cause.message); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!job?.job_id) return;
    const jobId = job.job_id;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const jobs = await api.localJobs();
        const current = jobs.find((item) => item.job_id === jobId);
        if (cancelled) return;
        if (!current) { setError("ဤအလုပ်၏ မှတ်တမ်းကို မတွေ့တော့ပါ။ စာမျက်နှာကို ပြန်ဖွင့်ပါ။"); return; }
        setJob(current);
        setError("");
        if (current.status === "SUCCEEDED") {
          const overview = await api.overview();
          if (!cancelled) { setCount(overview.counts.stories); updated.current?.(); }
          return;
        }
        if (!["QUEUED", "RUNNING"].includes(current.status)) return;
      } catch (cause) {
        if (cancelled) return;
        setError(cause instanceof Error ? cause.message : "အခြေအနေ ဖတ်မရပါ။");
      }
      if (!cancelled) timer = setTimeout(() => { void poll(); }, 2_000);
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job?.job_id]);
  const run = async () => {
    started.current = true;
    setBusy(true); setError(""); setCount(null);
    try { setJob(await api.discover(csrf)); }
    catch (e) { setError(e instanceof Error ? e.message : "Discovery မရပါ"); }
    finally { setBusy(false); }
  };
  const labels: Record<string, string> = { QUEUED: "ရှာဖွေရန် တန်းစီနေပါသည်…", RUNNING: "ရင်းမြစ်များကို ရှာဖွေဖတ်နေပါသည်…",
    SUCCEEDED: "ရှာဖွေခြင်း ပြီးပါပြီ", FAILED: "ရှာဖွေမှု မအောင်မြင်ပါ။ အလုပ်မှတ်တမ်းကို စစ်ပါ။",
    INTERRUPTED: "အလုပ် ရပ်တန့်သွားပါသည်။ အလုပ်မှတ်တမ်းမှ ပြန်စစ်ပါ။" };
  const status = job ? labels[job.status] ?? job.status : "";
  return <section className="admin-panel mvp-workflow"><h2>Story Finder</h2>
    <p>ခွင့်ပြုထားသော ရင်းမြစ်များမှ ပုံပြင်အချက်အလက်များကို ရှာဖွေစုဆောင်းပါသည်။ ရလာသောမှတ်တမ်းများကို စာကြည့်တိုက်တွင် စစ်ဆေးနိုင်သည်။</p>
    <p>၎င်းသည် feed ထဲက ရင်းမြစ်စာရင်းကို ရှာခြင်းဖြစ်သည်။ မြန်မာပုံပြင်အသစ်ကို AI ဖြင့်ရေးရန် “ပုံပြင်အသစ် ဖန်တီးရန်” ကိုသုံးပါ။ အရင်တွေ့ပြီးသားကို ထပ်မသိမ်းပါ။</p>
    <button className="button button-primary" disabled={busy || active} onClick={() => void run()}>{busy || active ? "ရှာဖွေနေသည်…" : "Discovery job စတင်ရန်"}</button>
    {job && <div className="workflow-callout" role="status"><strong>{status}</strong>{active && <p>အခြေအနေကို အလိုအလျောက် ပြန်ဖတ်ပေးနေပါသည်။ ထပ်နှိပ်ရန် မလိုပါ။</p>}
      {count !== null && <p>စာကြည့်တိုက်ရှိ ရင်းမြစ်မှတ်တမ်းစုစုပေါင်း — {count} ခု</p>}</div>}
    {job?.result && <div className="workflow-callout"><h3>ဤတစ်ကြိမ် ရှာဖွေမှုရလဒ်</h3><p>ရှာတွေ့ {job.result.found} · အရင်ရှိပြီး/ထပ်နေ {job.result.duplicates} · အသစ်သိမ်း {job.result.added} · နောက်တစ်ကြိမ်ဆက်သိမ်းရန် {job.result.deferred}</p>
      {job.status === "SUCCEEDED" && job.result.added === 0 && <p>အသစ်မထည့်ရခြင်းသည် အလုပ်မလုပ်ခြင်း မဟုတ်ပါ။ လက်ရှိ feed မှာ မတွေ့ဖူးသေးသော မှတ်တမ်းအသစ် မရှိပါ။</p>}
      {!job.result.sources.length && <p>ဖတ်ခွင့်ပြုထားသော feed မရှိပါ။ approved_sources.json ကို စစ်ပါ။</p>}
      {job.result.sources.map((source) => <p key={source.name}>{source.name} — {source.found} ခု {source.errors.length > 0 && <strong>· ရင်းမြစ်ဖတ်မရပါ: {source.errors.join(", ")}</strong>}</p>)}
      <p>ရင်းမြစ်တွေ့ခြင်းသည် ဘာသာပြန်၊ အသံထုတ်၊ ထုတ်ဝေခွင့် အတည်ပြုပြီးခြင်း မဟုတ်ပါ။</p>
    </div>}
    {error && <p role="alert">{error}</p>}
    <div className="workflow-actions"><Link className="button button-quiet" to="/admin/stories">တွေ့ရှိထားသော စာရင်းကြည့်ရန်</Link><Link className="button button-quiet" to="/admin/production">AI ပုံပြင်အသစ် ဖန်တီးရန်</Link></div>
  </section>;
}

export function MvpStoryActions({ storyId, csrf, detail, refresh }: { storyId: string; csrf: string; detail: AdminStoryDetail; refresh: () => Promise<void> }) {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [settingsError, setSettingsError] = useState("");
  useEffect(() => { void api.settings().then(setSettings).catch(() => setSettingsError("ထုတ်ဝေမှု setting ကို ဖတ်မရပါ။ စာမျက်နှာကို ပြန်ဖွင့်ပါ။")); }, []);
  const [reviewer, setReviewer] = useState("");
  const [evidence, setEvidence] = useState("");
  const [publication, setPublication] = useState(false);
  const [narration, setNarration] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const original = ["ORIGINAL_THEME", "MANUAL_ORIGINAL"].includes(detail.production.draft_mode);
  useEffect(() => {
    setReviewer(detail.story.original_reviewer || "");
    setEvidence(detail.story.original_evidence || "");
    setPublication(detail.story.permission_for_publication === "YES");
    setNarration(detail.story.permission_for_audio === "YES");
  }, [storyId, detail.story.original_reviewer, detail.story.original_evidence, detail.story.permission_for_publication, detail.story.permission_for_audio]);
  const action = async (path: string, data: unknown, method = "POST") => {
    setBusy(true); setMessage("");
    try { await api.storyAction(storyId, path, data, csrf, method); setMessage(path === "publish" ? "ထုတ်ဝေပြီးပါပြီ။ အောက်ရှိ link မှ စာဖတ်သူစာမျက်နှာကို ဖွင့်နိုင်ပါပြီ။" : "သိမ်းပြီးပါပြီ။"); await refresh(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "လုပ်ဆောင်မရပါ"); }
    finally { setBusy(false); }
  };
  const publish = () => {
    if (window.confirm("သိမ်းထားသောမူကြမ်းကို စစ်ပြီး အများမြင်ထုတ်ဝေမည်လား။")) void action("publish", { confirm: true, approved_by: reviewer });
  };
  if (!detail.production.myanmar_story) return <section className="admin-panel mvp-workflow">
    <h2>AI မူကြမ်း စတင်ရန်</h2>
    <p>ခလုတ်နှိပ်လျှင် Gemini ဖြင့် မူကြမ်းတစ်ပုဒ် ထုတ်မည်ဖြစ်သည်။ ပြီးလျှင် ရလဒ်ကို ပြန်ဖတ်ပါ။</p>
    <div className="workflow-actions"><button className="button button-primary" disabled={busy} onClick={() => {
      if (window.confirm("Gemini quota သုံးပြီး မူကြမ်းထုတ်မည်လား။")) void action("jobs", { kind: "GENERATE" });
    }}>AI မူကြမ်း job စတင်ရန်</button>
    <button className="button button-quiet" disabled={busy} onClick={() => void refresh()}>မူကြမ်းနှင့် job ရလဒ် ပြန်ဖတ်ရန်</button></div>
    {message && <p role="status" className="workflow-callout">{message}</p>}
  </section>;
  return <section className="admin-panel mvp-workflow" id="story-review"><h2>ပုံပြင် စစ်ဆေးအတည်ပြုရန်</h2>
    <p>Editor ထဲကပြင်ဆင်မှုကို အရင်သိမ်းပါ။ အောက်ပါလုပ်ဆောင်ချက်များသည် server တွင်သိမ်းထားသောမူကြမ်းကို သုံးသည်။</p>
    <button type="button" disabled={busy} onClick={() => void refresh()}>မူကြမ်းနှင့် job ရလဒ် ပြန်ဖတ်ရန်</button>
    <label className="editor-field">စစ်ဆေးသူအမည်<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="သင့်အမည်ကို ထည့်ပါ" /></label>
    {original && <><label className="editor-field">ပုံပြင်ကို ဘာတွေ ဖတ်စစ်ထားသလဲ<textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="ပရိသတ်အသက်အုပ်စု၊ အကြောင်းအရာနှင့် မူကြမ်း၏ ကိုယ်ပိုင်ဖန်တီးမှုကို စစ်ဆေးထားပုံ ရေးပါ" /></label>
      <p>Original review: {detail.story.original_review_status || "PENDING"}</p>
      <label className="workflow-check"><input type="checkbox" checked={publication} onChange={(e) => setPublication(e.target.checked)} /> အများမြင်မျှဝေခွင့် အတည်ပြုသည်</label>
      <label className="workflow-check"><input type="checkbox" checked={narration} onChange={(e) => setNarration(e.target.checked)} /> အသံဖတ်ပြခွင့် အတည်ပြုသည်</label>
      {(!reviewer.trim() || !evidence.trim()) && <p>သင့်အမည်နှင့် ဖတ်စစ်ထားသောအချက်ကို ဖြည့်ပြီးမှ review သိမ်းနိုင်ပါမည်။</p>}
      <button type="button" disabled={busy || !reviewer.trim() || !evidence.trim()} onClick={() => void action("original-review", { reviewer, evidence, permission_for_publication: publication ? "YES" : "NO", permission_for_audio: narration ? "YES" : "NO" })}>စစ်ဆေးချက်နှင့် အသံဖတ်ပြခွင့် သိမ်းရန်</button>
    </>}
    <h3>စာသားကို ဖတ်စစ်ပြီးပြီလား</h3>
    <p>{detail.production.content_review_status === "APPROVED" ? "စာသား အတည်ပြုပြီးပါပြီ။ အသံထုတ်ရန် ဆက်လုပ်နိုင်သည်။" : "စာသား၊ အပိုင်းနှင့် quiz ကို ဖတ်စစ်ပြီးမှ အတည်ပြုပါ။"}</p>
    <button className="button button-primary" disabled={busy || detail.production.content_review_status === "APPROVED"} onClick={() => {
      if (window.confirm("သိမ်းထားသော ပုံပြင်စာသားကို ဖတ်စစ်ပြီး အတည်ပြုမည်လား။")) void action("content-review", { action: "approve" });
    }}>စာသား ဖတ်စစ်ပြီး အတည်ပြုရန်</button>
    <a href="#story-audio">AI အသံထုတ်ရန် / နားထောင်ရန် ↑</a>
    <details><summary>အများမြင် ဝက်ဘ်ဆိုက်ပေါ် ထုတ်ဝေရန်</summary><p>အသံနားထောင်ရန် အပေါ်ရှိ “AI အသံထုတ်ရန်” ကိုသုံးပါ။ ဤအပိုင်းသည် အများမြင်ထုတ်ဝေရန် ဖြစ်သည်။</p><p>Content review: {detail.production.content_review_status} · Publication approval: {detail.production.approval_status || "မရှိသေး"}</p>
    {/* ထုတ်ဝေခလုတ် မနှိပ်ခင် မပြီးသေးသော စစ်ဆေးချက်များကို မြင်နိုင်ရန် ပြသည်။ */}
    <div className="workflow-callout"><strong>ထုတ်ဝေရန် လိုအပ်ချက်များ</strong><ul>
      <li>{settings ? settings.publishing_enabled ? "✓ Server ထုတ်ဝေခွင့် ဖွင့်ထားသည်" : "ကျန်နေသည် — Server ထုတ်ဝေခွင့် ပိတ်ထားသည်။ .env တွင် PYONPYIN_PUBLISHING_ENABLED=true ပြောင်းပြီး server ကို ပြန်စပါ။" : settingsError || "Server setting စစ်နေသည်…"}</li>
      {original && <li>{detail.story.original_review_status === "APPROVED" ? "✓ မူရင်းပုံပြင် စစ်ဆေးချက် သိမ်းပြီး" : "ကျန်နေသည် — အပေါ်တွင် စစ်ဆေးသူအမည်နှင့် ဖတ်စစ်ထားသည့်အချက်ကို ဖြည့်ပြီး စစ်ဆေးချက် သိမ်းပါ။"}</li>}
      <li>{detail.story.permission_for_publication === "YES" ? "✓ အများမြင်မျှဝေခွင့် ရှိသည်" : "ကျန်နေသည် — အများမြင်မျှဝေခွင့်ကို အမှန်ခြစ်ပြီး စစ်ဆေးချက် သိမ်းပါ။"}</li>
      <li>{detail.production.content_review_status === "APPROVED" ? "✓ စာသား အတည်ပြုပြီး" : "ကျန်နေသည် — စာသားကို ဖတ်စစ်အတည်ပြုပါ။"}</li>
      {detail.production.audio_required === "YES" && <li>{detail.production.audio_status === "READY" ? "✓ အသံ နားထောင်စစ်ဆေးပြီး" : <>ကျန်နေသည် — အသံထုတ်ပြီးရုံဖြင့် စစ်ဆေးချက် မသိမ်းရသေးပါ။ <a href="#story-audio">အသံနေရာသို့ သွားပြီး “နားထောင်ပြီး အသံအတည်ပြုရန်” နှိပ်ပါ ↑</a></>}</li>}
    </ul><p>ထုတ်ဝေခြင်းက စာမျက်နှာကို အလိုအလျောက် ပြောင်းမဖွင့်ပါ။ အောင်မြင်လျှင် စာဖတ်သူစာမျက်နှာ link ပေါ်လာပါမည်။</p></div>
    <label className="workflow-check"><input type="checkbox" checked={detail.production.audio_required === "YES"} disabled={busy} onChange={(e) => void action("audio-requirement", { required: e.target.checked }, "PUT")} /> ထုတ်ဝေရန် အသံဖိုင် မဖြစ်မနေလိုသည်</label>
    <label className="editor-field">ထုတ်ဝေမှု အတည်ပြုသူအမည်<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
    <button className="button button-primary" type="button" disabled={busy || !reviewer.trim()} onClick={publish}>အများမြင် ထုတ်ဝေမည်</button>
    <button className="button" type="button" disabled={busy} onClick={() => {
      if (window.confirm("ဤပုံပြင်ကို public မှ ပြန်ဖယ်မည်လား။")) void action("unpublish", { approved_by: reviewer });
    }}>Public မှ ပြန်ဖယ်ရန်</button></details>
    {detail.production.approval_status === "APPROVED" && <a className="button button-primary" href={`/app/#/stories/${encodeURIComponent(storyId)}`} target="_blank" rel="noreferrer">ထုတ်ဝေထားသော ပုံပြင်ကို ဖွင့်ရန် ↗</a>}
    {message && <p role="status">{message}</p>}
  </section>;
}
