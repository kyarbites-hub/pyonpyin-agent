import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type AdminStory, type PublicationRecord, type PublicationSnapshot } from "./api";

const stages = [
  { id: "NEW", label: "မလုပ်ရသေး" },
  { id: "DRAFT", label: "စာသားရှိ · အသံမထုတ်ရသေး" },
  { id: "AUDIO", label: "အသံထုတ်ပြီး · မထုတ်ဝေရသေး" },
  { id: "PUBLISHED", label: "ထုတ်ဝေပြီး" },
] as const;
type Stage = typeof stages[number]["id"];
// ပုံပြင်တစ်ပုဒ်ကို အဆင့်တစ်ခုထဲတွင်သာ ထည့်ပြီး ထုတ်ဝေပြီးသားများကို မူကြမ်းစာရင်းနှင့် မရောစေပါ။
export function storyStage(story: AdminStory): Stage {
  if (story.published) return "PUBLISHED";
  if (story.audio_url) return "AUDIO";
  if (story.has_story) return "DRAFT";
  return "NEW";
}
export function displayDate(value?: string) {
  if (!value) return "အချိန်မှတ်တမ်း မရှိသေး";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-GB");
}
export function StoryCatalogue({ stories }: { stories: AdminStory[] }) {
  const [stage, setStage] = useState<Stage>(() => (["AUDIO", "PUBLISHED", "DRAFT", "NEW"] as Stage[]).find((id) => stories.some((story) => storyStage(story) === id)) || "NEW");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filtered = stories.filter((story) => storyStage(story) === stage && `${story.title} ${story.story_id}`.toLowerCase().includes(query.toLowerCase()));
  const rows = [...filtered].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  return <section className="admin-panel story-catalogue"><h2>ပုံပြင်များကို အဆင့်အလိုက် ကြည့်ရန်</h2>
    <div className="catalogue-tabs" role="group" aria-label="ပုံပြင်အဆင့်"><>{stages.map((item) => <button key={item.id} aria-pressed={stage === item.id} onClick={() => { setStage(item.id); setPage(0); }}><strong>{stories.filter((story) => storyStage(story) === item.id).length}</strong>{item.label}</button>)}</></div>
    <label className="editor-field">ပုံပြင်ခေါင်းစဉ် ရှာရန်<input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} /></label>
    <p>{stages.find((item) => item.id === stage)?.label} — {rows.length} ပုဒ်</p>
    {!rows.length && <p>ဤအဆင့်တွင် ပုံပြင် မရှိသေးပါ။ အခြားအဆင့်ကို ရွေးကြည့်နိုင်ပါသည်။</p>}
    <div className="audio-library-grid">{rows.slice(page * 12, (page + 1) * 12).map((story) => <article className="audio-story-card" key={story.story_id}>
      {story.cover_image_url && <img className="catalogue-cover-image" src={story.cover_image_url} alt="" loading="lazy" />}
      <span className="eyebrow">{story.category === "CHILDREN" ? "ကလေးပုံပြင်" : story.category === "ADULT" ? "လူကြီးပုံပြင်" : "ရင်းမြစ် · အမျိုးအစားစစ်ရန်"}</span><h3>{story.title}</h3>
      <p>{story.audio_url ? story.audio_status === "READY" ? "အသံ နားထောင်စစ်ဆေးပြီး" : "အသံရှိပြီ · နားထောင်အတည်ပြုရန်" : story.has_story ? "စာသားပြင်ဆင်ပြီး အသံဆက်ထုတ်နိုင်သည်" : "စာသား မဖန်တီးရသေးပါ"}</p>
      {story.audio_url && <audio controls preload="none" src={story.audio_url} aria-label={`${story.title} အသံနားထောင်ရန်`} />}
      <small>နောက်ဆုံးပြင်ဆင်ချိန် · {displayDate(story.updated_at)}</small>
      <div className="workflow-actions"><Link className="button button-quiet" to={`/admin/stories/${story.story_id}`}>စီမံရန်</Link>{story.published && <a className="button button-primary" href={`/app/#/stories/${story.story_id}`} target="_blank" rel="noreferrer">Public ပုံပြင်ဖွင့်ရန် ↗</a>}</div>
    </article>)}</div>
    {rows.length > 12 && <div className="workflow-actions"><button disabled={!page} onClick={() => setPage(page - 1)}>ယခင်</button><span>{page + 1} / {Math.ceil(rows.length / 12)}</span><button disabled={(page + 1) * 12 >= rows.length} onClick={() => setPage(page + 1)}>နောက်</button></div>}
  </section>;
}

function PublicationCard({ record }: { record: PublicationRecord }) {
  const [snapshot, setSnapshot] = useState<PublicationSnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true); setError("");
    try { setSnapshot(await api.publication(record.publication_id)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "မှတ်တမ်းဖတ်မရပါ"); }
    finally { setBusy(false); }
  };
  return <article className="publication-record"><div><span className="eyebrow">{record.publication_status === "PUBLISHED" ? "ထုတ်ဝေခဲ့သည်" : "Public မှ ဖယ်ခဲ့သည်"}</span><h3>{record.published_title || record.story_id}</h3><p>{displayDate(record.published_at)} · အတည်ပြုသူ {record.approved_by}</p></div>
    {record.audio_url && <audio controls preload="none" src={record.audio_url} aria-label="ထုတ်ဝေချိန်က အသံ" />}
    <div className="workflow-actions"><Link className="button button-quiet" to={`/admin/stories/${record.story_id}`}>လက်ရှိပုံပြင် စီမံရန်</Link>{record.snapshot_available && <button className="button button-primary" disabled={busy} onClick={() => snapshot ? setSnapshot(null) : void open()}>{busy ? "ဖတ်နေသည်…" : snapshot ? "စာသားမှတ်တမ်း ပိတ်ရန်" : "ထုတ်ဝေချိန်က စာသားဖတ်ရန်"}</button>}</div>
    {!record.snapshot_available && record.publication_status === "PUBLISHED" && <p>ယခင်မှတ်တမ်းဖြစ်၍ ထိုအချိန်က စာသားနှင့် အသံ snapshot မပါပါ။ နောက်ထုတ်ဝေမှုများတွင် အပြည့်အစုံ သိမ်းပေးပါမည်။</p>}
    {snapshot && <div className="publication-snapshot"><h4>{snapshot.title}</h4>{snapshot.cover_image_url && <img className="catalogue-cover-image" src={snapshot.cover_image_url} alt="ထုတ်ဝေချိန်က မျက်နှာဖုံးပုံ" />}<p>{snapshot.story}</p></div>}
    {error && <p role="alert">{error}</p>}
  </article>;
}
export function PublicationArchive({ stories = [] }: { stories?: AdminStory[] }) {
  const [records, setRecords] = useState<PublicationRecord[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const load = async () => {
    setLoading(true); setError("");
    try { setRecords(await api.publications()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "မှတ်တမ်းဖတ်မရပါ"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const rows = records.filter((record) => `${record.published_title} ${record.story_id} ${record.approved_by}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="admin-panel story-catalogue"><div className="audio-workspace-heading"><div><span className="eyebrow">ထုတ်ဝေမှု မှတ်တမ်းတိုက်</span><h2>ပုံပြင်နှင့် အသံ ထုတ်ဝေမှုမှတ်တမ်း</h2></div><button className="button button-quiet" onClick={() => void load()}>ပြန်ဖတ်ရန်</button></div>
    <h3>လက်ရှိ Public ပေါ်ရှိ ပုံပြင်များ</h3>
    <div className="audio-library-grid">{stories.filter((story) => story.published).map((story) => <article className="audio-story-card" key={story.story_id}><h3>{story.title}</h3>{story.audio_url && <audio controls preload="none" src={story.audio_url} aria-label={`${story.title} လက်ရှိထုတ်ဝေထားသောအသံ`} />}<a className="button button-primary" href={`/app/#/stories/${story.story_id}`} target="_blank" rel="noreferrer">စာသားနှင့် အသံ ဖွင့်ရန် ↗</a></article>)}</div>
    {!stories.some((story) => story.published) && <p>လက်ရှိ Public ပေါ်တွင် ပုံပြင် မရှိသေးပါ။</p>}
    <h3>ထုတ်ဝေခဲ့သည့် ဖြစ်ရပ်မှတ်တမ်းများ</h3>
    <p>ထုတ်ဝေသည့်အချိန်၊ အတည်ပြုသူ၊ ထိုအချိန်က စာသားနှင့် အသံဖိုင်ကို သိမ်းထားသည်။ ဤစာရင်းသည် ထုတ်ဝေခဲ့သည့် ဖြစ်ရပ်မှတ်တမ်း ဖြစ်သည်။ လက်ရှိ public ပုံပြင်များကို Dashboard ရှိ “ထုတ်ဝေပြီး” တွင် ကြည့်ပါ။</p>
    <label className="editor-field">မှတ်တမ်း ရှာရန်<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
    {loading && <p role="status">မှတ်တမ်းဖတ်နေသည်…</p>}{error && <p role="alert">{error}</p>}
    {!loading && !rows.length && <p>ကိုက်ညီသော ထုတ်ဝေမှုမှတ်တမ်း မရှိသေးပါ။</p>}
    {rows.map((record) => <PublicationCard key={record.publication_id} record={record} />)}
  </section>;
}
