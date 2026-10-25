import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search, FileText, Sparkles, Volume2, UserRound, Globe2, Plus, ArrowUpRight, ArrowRight, BookOpen, Clock3, ShieldCheck, Headphones, Image as ImageIcon } from "lucide-react";
import { api, type AdminStory, type JobStatus, type Overview } from "./api";
import { storyStage, displayDate } from "./StoryCatalogue";
import { defaultStoryArt } from "./uiAssets";

const statusLabels = { NEW: "မလုပ်ရသေး", DRAFT: "စာသားမူကြမ်း", AUDIO: "အသံထုတ်ပြီး", PUBLISHED: "ထုတ်ဝေပြီး" };
export function ManagementDashboard({ counts, stories, jobs }: { counts: Overview["counts"]; stories: AdminStory[]; jobs?: JobStatus | null }) {
  const [filter, setFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [page, setPage] = useState(0);
  const ordered = [...stories].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  const selected = stories.find((story) => story.story_id === selectedId) || ordered.find((story) => story.published || story.audio_url) || ordered[0];
  const metrics = [
    { label: "Story Finder", mm: "မလုပ်ရသေးသော ရင်းမြစ်များ", value: stories.filter((story) => storyStage(story) === "NEW").length, icon: Search, color: "blue", filter: "NEW" },
    { label: "Draft Stories", mm: "စာသားရှိ · အသံမထုတ်ရသေး", value: stories.filter((story) => storyStage(story) === "DRAFT").length, icon: FileText, color: "yellow", filter: "DRAFT" },
    { label: "AI Processing", mm: "တန်းစီ / လုပ်ဆောင်နေဆဲ", value: (jobs?.active || []).length, icon: Sparkles, color: "purple", path: "/admin/production" },
    { label: "Audio Library", mm: "အသံရှိ · မထုတ်ဝေရသေး", value: stories.filter((story) => storyStage(story) === "AUDIO").length, icon: Volume2, color: "teal", filter: "AUDIO" },
    { label: "Content Review", mm: "စာသား ဖတ်စစ်ရန် ကျန်နေဆဲ", value: counts.content_review, icon: UserRound, color: "blue", path: "/admin/review" },
    { label: "Published Stories", mm: "လက်ရှိ Public ပေါ်ရှိ ပုံပြင်များ", value: counts.published, icon: Globe2, color: "green", filter: "PUBLISHED" },
  ];
  useEffect(() => {
    let cancelled = false; setExcerpt("");
    if (selected?.has_story) void api.story(selected.story_id).then((detail) => { if (!cancelled) setExcerpt(detail.production.myanmar_story?.slice(0, 180) || ""); }).catch(() => {});
    return () => { cancelled = true; };
  }, [selected?.story_id, selected?.updated_at]);
  const rows = ordered.filter((story) => (filter === "ALL" || storyStage(story) === filter) && `${story.title} ${story.story_id}`.toLowerCase().includes(query.toLowerCase()));
  const changeFilter = (value: string) => { setFilter(value); setPage(0); };
  return <div className="management-dashboard"><div className="management-actions"><p>သင့်ပုံပြင်များ၏ လုပ်ငန်းစဉ်ကို တစ်နေရာတည်းမှ ကြည့်ရှုစီမံပါ။</p><Link className="button button-primary" to="/admin/production"><Plus size={17} />ပုံပြင်အသစ် ဖန်တီးရန်</Link></div>
    <div className="management-metrics">{metrics.map(({ label, mm, value, icon: Icon, color, filter: stage, path }) => {
      const content = <><span className={`management-metric-icon ${color}`}><Icon size={22} /></span><strong>{value}</strong><span>{label}</span><small>{mm}</small></>;
      return path ? <Link className="management-metric" to={path} key={label}>{content}</Link> : <button className={`management-metric ${filter === stage ? "selected" : ""}`} onClick={() => changeFilter(stage!)} key={label}>{content}</button>;
    })}</div>
    <div className="management-content"><section className="management-table-panel"><div className="management-panel-heading"><div><h2>Recent Stories</h2><p>ပုံပြင်များကို အဆင့်အလိုက် ခွဲကြည့်ရန်</p></div><Link to="/admin/stories">စာရင်းအားလုံး <ArrowUpRight size={15} /></Link></div>
      <div className="management-table-tools"><div className="management-filter-tabs" role="group" aria-label="ပုံပြင်အဆင့်">{[["ALL", "အားလုံး"], ...Object.entries(statusLabels)].map(([id, label]) => <button className={filter === id ? "active" : ""} onClick={() => changeFilter(id)} key={id}>{label}</button>)}</div><label className="management-search"><Search size={16} /><input aria-label="Dashboard ပုံပြင်ရှာရန်" placeholder="ခေါင်းစဉ်ဖြင့် ရှာရန်…" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} /></label></div>
      <div className="table-scroll"><table className="management-table"><thead><tr><th>#</th><th>Image</th><th>Title</th><th>Status</th><th>Audio</th><th>Updated</th><th>Actions</th></tr></thead><tbody>{rows.slice(page * 8, (page + 1) * 8).map((story, index) => <tr className={selected?.story_id === story.story_id ? "selected" : ""} key={story.story_id}><td>{page * 8 + index + 1}</td><td><button className="management-thumb" aria-label={`${story.title} အကြိုကြည့်ရန်`} onClick={() => setSelectedId(story.story_id)}>{story.cover_image_url ? <img src={story.cover_image_url} alt="" /> : <ImageIcon size={23} />}</button></td><td><button className="management-story-title" onClick={() => setSelectedId(story.story_id)}>{story.title}</button><small>{story.category === "CHILDREN" ? "Kids Stories" : story.category === "ADULT" ? "Adult Stories" : "ရင်းမြစ် · အမျိုးအစားစစ်ရန်"}</small></td><td><span className={`management-status stage-${storyStage(story).toLowerCase()}`}>{statusLabels[storyStage(story)]}</span></td><td>{story.audio_url ? <span className="management-audio-state"><Volume2 size={15} />{story.audio_status === "READY" ? "စစ်ပြီး" : "စစ်ရန်"}</span> : "—"}</td><td><time>{displayDate(story.updated_at)}</time></td><td><Link className="management-edit-link" to={`/admin/stories/${story.story_id}`}>{story.published ? "View / Edit" : "Edit"}</Link></td></tr>)}</tbody></table></div>
      {!rows.length && <div className="world-empty">ကိုက်ညီသော ပုံပြင် မရှိသေးပါ။</div>}<div className="management-pagination"><span>မှတ်တမ်း {rows.length} ခု · စာမျက်နှာ {page + 1} / {Math.max(1, Math.ceil(rows.length / 8))}</span><div><button disabled={!page} onClick={() => setPage(page - 1)}>ယခင်</button><button disabled={(page + 1) * 8 >= rows.length} onClick={() => setPage(page + 1)}>နောက်</button></div></div>
    </section><aside className="management-preview"><h2>ပုံပြင် အကြိုကြည့်ရန်</h2>{selected ? <><img className="management-preview-image" src={selected.cover_image_url || defaultStoryArt} alt="ရွေးထားသော ပုံပြင်မျက်နှာဖုံး" /><h3>{selected.title}</h3><span className={`management-status stage-${storyStage(selected).toLowerCase()}`}>{statusLabels[storyStage(selected)]}</span><p>{excerpt || (selected.has_story ? "စာသားအပြည့်ကို editor တွင် ဖတ်ရှုနိုင်ပါသည်။" : "ရင်းမြစ်အချက်အလက်ကို စစ်ဆေးရန် လိုအပ်သေးသည်။")}</p>{selected.audio_url && <audio key={selected.audio_url} controls preload="metadata" src={selected.audio_url} aria-label="Dashboard ရွေးထားသောပုံပြင်အသံ" />}<dl><div><dt><Headphones size={15} />အသံအခြေအနေ</dt><dd>{selected.audio_url ? selected.audio_status === "READY" ? "အတည်ပြုပြီး" : "နားထောင်စစ်ရန်" : "မထုတ်ရသေး"}</dd></div><div><dt><Clock3 size={15} />နောက်ဆုံးပြင်ဆင်</dt><dd>{displayDate(selected.updated_at)}</dd></div><div><dt><ShieldCheck size={15} />Public</dt><dd>{selected.published ? "ထုတ်ဝေထားသည်" : "မထုတ်ဝေရသေး"}</dd></div></dl><Link className="button button-primary" to={`/admin/stories/${selected.story_id}`}><BookOpen size={16} />ပုံပြင်ကို စီမံရန်</Link>{selected.published && <a className="management-public-link" href={`/app/#/stories/${selected.story_id}`} target="_blank" rel="noreferrer">Public ပုံပြင်ဖွင့်ရန် <ArrowUpRight size={15} /></a>}</> : <p>ပုံပြင်အသစ် ဖန်တီးပြီး စတင်နိုင်ပါသည်။</p>}</aside></div>
    <div className="management-bottom-links"><Link to="/admin/publishing"><Globe2 size={18} />ပုံပြင်နှင့် အသံ ထုတ်ဝေမှုမှတ်တမ်း <ArrowRight size={16} /></Link><Link to="/admin/settings"><ImageIcon size={18} />ပင်မစာမျက်နှာပုံ ပြောင်းရန် <ArrowRight size={16} /></Link></div>
  </div>;
}
