import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  AudioLines,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Compass,
  FileText,
  History,
  LayoutDashboard,
  LibraryBig,
  LockKeyhole,
  LogOut,
  Menu,
  Music2,
  PenLine,
  Search,
  RotateCcw,
  ShieldAlert,
  Settings2,
  ShieldCheck,
  Sparkles,
  Timer,
  Workflow,
  XCircle,
} from "lucide-react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { api, type AdminStory, type AdminStoryDetail, type JobStatus, type Overview, type PublicStory } from "./api";
import { demoJobs, demoOverview, demoPublicStories, demoTracks, isDemoMode, loadDemoStoryDetail, saveDemoStoryDetail } from "./demo";
import DemoAudioPlayer from "./DemoAudioPlayer";
import { LiveFinder, MvpSettings, MvpStoryActions, MvpWorkspace } from "./MvpWorkflow";
import { LiveAudioStudio, StoryAudioPanel } from "./AudioWorkspace";
import { PublicationArchive } from "./StoryCatalogue";
import { ImageManager } from "./ImageManager";
import { StoryWorld } from "./StoryWorld";
import { ManagementDashboard } from "./ManagementDashboard";
import { defaultStoryArt } from "./uiAssets";

const burmeseCategory: Record<string, string> = {
  CHILDREN: "ကလေးများ",
  ADULT: "လူကြီးများ",
  UNCLASSIFIED: "အမျိုးအစား မသတ်မှတ်ရသေး",
};

const adminSections = [
  { id: "overview", path: "/admin", label: "ခြုံငုံမြင်ကွင်း", icon: LayoutDashboard },
  { id: "finder", path: "/admin/finder", label: "Story Finder", icon: Compass },
  { id: "library", path: "/admin/stories", label: "ပုံပြင်စာကြည့်တိုက်", icon: LibraryBig },
  { id: "rights", path: "/admin/rights", label: "Rights & License", icon: ShieldAlert },
  { id: "production", path: "/admin/production", label: "Story Editor", icon: PenLine },
  { id: "review", path: "/admin/review", label: "Review & Approval", icon: CheckCircle2 },
  { id: "episodes", path: "/admin/episodes", label: "Episode Manager", icon: BookOpen },
  { id: "audio", path: "/admin/audio", label: "အသံနားထောင်ရန်", icon: Music2 },
  { id: "activity", path: "/admin/history", label: "Processing History", icon: History },
  { id: "publishing", path: "/admin/publishing", label: "ထုတ်ဝေမှုမှတ်တမ်း", icon: FileText },
  { id: "settings", path: "/admin/settings", label: "Settings & Safety", icon: Settings2 },
];

function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <header className="site-header">
      <Link className="brand" to="/">
        <span className="brand-mark"><Sparkles size={20} /></span>
        <span><strong>PYONPYIN</strong><small>ပုံပြင်ကမ္ဘာ</small></span>
      </Link>
      <button className="public-menu-toggle" type="button" aria-label="မီနူးဖွင့်ပိတ်ရန်" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Menu size={19} /></button>
      <nav className={`main-nav ${menuOpen ? "menu-open" : ""}`} aria-label="အဓိက လမ်းညွှန်">
        <NavLink to="/" onClick={() => setMenuOpen(false)}>ပင်မစာမျက်နှာ</NavLink>
        <NavLink to="/stories" onClick={() => setMenuOpen(false)}>ပုံပြင်စာကြည့်တိုက်</NavLink>
      </nav>
      <Link className="admin-link" to="/admin"><LayoutDashboard size={16} /> စီမံခန့်ခွဲမှု</Link>
    </header>
  );
}

function SiteFooter() {
  return <footer className="site-footer"><span>PYONPYIN · မြန်မာပုံပြင်များ</span><span>လုံခြုံစွာ ရွေးချယ်ထားသော ပုံပြင်များ</span></footer>;
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toUpperCase();
  const tone = ["APPROVED", "PUBLISHED", "DRAFT_READY"].includes(normalized)
    ? "good"
    : ["FAILED", "REJECTED", "BLOCKED_RIGHTS"].includes(normalized)
      ? "bad"
      : "pending";
  return <span className={`badge ${tone}`}>{value.replaceAll("_", " ") || "မစတင်ရသေး"}</span>;
}

function LoadingState() {
  return <div className="state-card"><span className="spinner" /> အချက်အလက်များ ဖတ်နေပါသည်…</div>;
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <div className="state-card error-state"><XCircle size={22} /><span>{message}</span><button className="button button-quiet" onClick={retry}>ပြန်ကြိုးစားရန်</button></div>;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span className="empty-icon"><BookOpen size={24} /></span><h3>{title}</h3><p>{detail}</p></div>;
}

function StoryCover({ index = 0, imageUrl }: { index?: number; imageUrl?: string }) {
  if (imageUrl) return <div className="story-cover"><img className="story-cover-image" src={imageUrl} alt="" loading="lazy" /></div>;
  return <div className={`story-cover cover-${index % 4}`} aria-hidden="true"><span className="cover-orb" /><span className="cover-hill hill-one" /><span className="cover-hill hill-two" /><Sparkles className="cover-star" size={21} /></div>;
}

function StoryCard({ story, index = 0 }: { story: PublicStory; index?: number }) {
  return (
    <article className="story-card">
      <StoryCover index={index} imageUrl={story.cover_image_url} />
      <div className="story-card-content">
        <div className="card-eyebrow"><span className="category-dot" />{burmeseCategory[story.category]}{story.demo_sample && <span className="sample-chip">DEMO</span>}</div>
        <h3>{story.title}</h3>
        <p>{story.story.slice(0, 110)}{story.story.length > 110 ? "…" : ""}</p>
        <div className="card-bottom"><span className="reading-time"><Timer size={13} /> {story.reading_minutes ?? 3} မိနစ်</span><Link to={`/stories/${story.story_id}`} className="text-link">ဖတ်ရှုရန် <ArrowRight size={15} /></Link>{story.audio_url && <AudioLines className="audio-ready" size={17} aria-label="အသံဖိုင်ရှိသည်" />}</div>
      </div>
    </article>
  );
}

function usePublishedStories() {
  // Demo ဆို fixture ပြပြီး live ဆို publication စစ်ပြီးသော public API ကို ဖတ်သည်။
  const [stories, setStories] = useState<PublicStory[] | null>(null);
  const [error, setError] = useState("");
  const load = async () => {
    setError("");
    if (isDemoMode()) {
      setStories(demoPublicStories);
      return;
    }
    try {
      setStories(await api.stories());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "အချက်အလက် ဖတ်မရပါ။");
    }
  };
  useEffect(() => { void load(); }, []);
  return { stories, error, reload: load };
}

function HomePage() {
  const { stories, error, reload } = usePublishedStories();
  const [heroImage, setHeroImage] = useState("");
  useEffect(() => { if (!isDemoMode()) void api.site().then((site) => setHeroImage(site.hero_image_url)).catch(() => {}); }, []);
  if (!isDemoMode()) return <StoryWorld stories={stories} error={error} reload={reload} heroImage={heroImage} />;
  return (
    <div className="public-site">
      <SiteHeader />
      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow"><span className="eyebrow-line" /> MYANMAR STORY LIBRARY</span>
            <h1>စိတ်ကူးကမ္ဘာဆီ<br /><span>အတူသွားကြမယ်</span></h1>
            <p>ဖတ်ရှုရန်၊ နားထောင်ရန်နှင့် စိတ်ကူးယဉ်ရန် — မြန်မာဘာသာဖြင့် စုစည်းထားသော ပုံပြင်ကမ္ဘာ။</p>
            <Link className="button button-primary" to="/stories">ပုံပြင်များ ရှာဖွေရန် <ArrowRight size={17} /></Link>
            <div className="hero-proof"><ShieldCheck size={17} /><span>{isDemoMode() ? "DEMO နမူနာအကြောင်းအရာ · ထုတ်ဝေထားသော ပုံပြင်မဟုတ်ပါ" : "စစ်ဆေးပြီး ထုတ်ဝေထားသော ပုံပြင်များသာ"}</span></div>
          </div>
          <div className="hero-art" aria-hidden="true">{heroImage ? <img className="hero-custom-image" src={heroImage} alt="" /> : <><div className="hero-moon" /><div className="hero-planet">✦</div><div className="hero-mountain mountain-back" /><div className="hero-mountain mountain-front" /></>}<div className="hero-caption">ပုံပြင်တစ်ပုဒ် · ကမ္ဘာတစ်ခု</div></div>
        </section>
        <section className="section-block">
          <div className="section-heading"><div><span className="eyebrow">DISCOVER</span><h2>ပုံပြင်အသစ်များ</h2><p>{isDemoMode() ? "နမူနာအကြောင်းအရာများ · အများမြင်ထုတ်ဝေမှု မဟုတ်ပါ" : "အတည်ပြုပြီး မျှဝေထားသော ပုံပြင်များ"}</p></div><Link to="/stories" className="text-link">အားလုံးကြည့်ရန် <ArrowRight size={16} /></Link></div>
          {error ? <ErrorState message={error} retry={() => void reload()} /> : stories === null ? <LoadingState /> : stories.length === 0 ? <EmptyState title="ပုံပြင်များ မရှိသေးပါ" detail="စစ်ဆေးပြီး ထုတ်ဝေထားသော ပုံပြင်အသစ်များ မကြာမီ ရောက်လာပါမည်။" /> : <div className="story-grid">{stories.slice(0, 3).map((story, index) => <StoryCard key={story.story_id} story={story} index={index} />)}</div>}
        </section>
        <section className="reader-note"><div className="reader-note-icon"><BookOpen size={24} /></div><div><span className="eyebrow">READ AT YOUR OWN PACE</span><h2>စာမျက်နှာတိုင်းမှာ စိတ်ကူးအသစ်</h2><p>ဖုန်း၊ တက်ဘလက်နှင့် ကွန်ပျူတာများတွင် သက်တောင့်သက်သာ ဖတ်ရှုနိုင်ပါသည်။</p></div><ArrowDownRight className="note-arrow" size={34} /></section>
      </main>
      <SiteFooter />
    </div>
  );
}

function LibraryPage() {
  // ရယူထားသော ပုံပြင်များကို browser ထဲမှာ စာသားနှင့် category အလိုက် စစ်ထုတ်ပြသည်။
  const { stories, error, reload } = usePublishedStories();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const category = params.get("category") ?? "ALL";
  const filtered = useMemo(() => (stories ?? []).filter((story) => {
    const matchQuery = `${story.title} ${story.story}`.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    return matchQuery && (category === "ALL" || story.category === category);
  }), [stories, query, category]);
  const updateParams = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (!value || value === "ALL") next.delete(key); else next.set(key, value);
    setParams(next);
  };
  if (!isDemoMode()) return <StoryWorld stories={stories} error={error} reload={reload} mode="library" />;
  return (
    <div className="public-site">
      <SiteHeader />
      <main className="page-main">
        <section className="page-intro"><span className="eyebrow">THE COLLECTION</span><h1>ပုံပြင်စာကြည့်တိုက်</h1><p>သင့်စိတ်ကြိုက် ပုံပြင်များကို ရှာဖွေဖတ်ရှုပါ။</p>{isDemoMode() && <span className="public-demo-banner"><CircleHelp size={15} /> DEMO နမူနာများသာ · အများမြင်ထုတ်ဝေထားသော ဇာတ်လမ်းများ မဟုတ်ပါ</span>}</section>
        <div className="library-controls"><label className="search-field"><Search size={18} /><input aria-label="ပုံပြင်ရှာရန်" placeholder="ခေါင်းစဉ် သို့မဟုတ် စာသားဖြင့် ရှာရန်…" value={query} onChange={(event) => updateParams("q", event.target.value)} /></label><div className="filter-pills" aria-label="အမျိုးအစား စစ်ထုတ်ရန်">{[["ALL", "အားလုံး"], ["CHILDREN", "ကလေးများ"], ["ADULT", "လူကြီးများ"]].map(([value, label]) => <button key={value} className={`filter-pill ${category === value ? "selected" : ""}`} onClick={() => updateParams("category", value)}>{label}</button>)}</div></div>
        {error ? <ErrorState message={error} retry={() => void reload()} /> : stories === null ? <LoadingState /> : filtered.length === 0 ? <EmptyState title={stories.length === 0 ? "ပုံပြင်များ မရှိသေးပါ" : "ကိုက်ညီသော ပုံပြင် မရှိပါ"} detail={stories.length === 0 ? "စစ်ဆေးပြီး ထုတ်ဝေထားသော ပုံပြင်အသစ်များ မကြာမီ ရောက်လာပါမည်။" : "ရှာဖွေမှု သို့မဟုတ် အမျိုးအစားကို ပြောင်းကြည့်ပါ။"} /> : <div className="story-grid">{filtered.map((story, index) => <StoryCard key={story.story_id} story={story} index={index} />)}</div>}
      </main>
      <SiteFooter />
    </div>
  );
}

function StoryPage() {
  const { storyId = "" } = useParams();
  const navigate = useNavigate();
  const { stories, error, reload } = usePublishedStories();
  const story = stories?.find((item) => item.story_id === storyId);
  if (!isDemoMode()) return <StoryWorld stories={stories} error={error} reload={reload} mode="story" storyId={storyId} />;
  return (
    <div className="public-site">
      <SiteHeader />
      <main className="page-main story-page">
        <button className="back-link" onClick={() => navigate(-1)}>← ပုံပြင်စာကြည့်တိုက်သို့</button>
        {error ? <ErrorState message={error} retry={() => void reload()} /> : stories === null ? <LoadingState /> : !story ? <EmptyState title="ပုံပြင်ကို ရှာမတွေ့ပါ" detail="ဤပုံပြင်ကို ထုတ်ဝေထားခြင်း မရှိတော့ပါ။" /> : <article className="story-reading">
          <div className="reading-top"><span className="category-chip">{burmeseCategory[story.category]}</span><span className="reading-mark"><BookOpen size={17} /> {story.demo_sample ? "DEMO SAMPLE · NOT PUBLISHED" : "PYONPYIN STORY"}</span></div>
          <h1>{story.title}</h1>
          {story.cover_image_url && <img className="reading-cover-image" src={story.cover_image_url} alt={`${story.title} မျက်နှာဖုံးပုံ`} />}
          {story.demo_sample && <div className="public-demo-banner"><CircleHelp size={15} /> သရုပ်ပြရန် ဖန်တီးထားသော နမူနာသာဖြစ်ပြီး rights review မပြီးသေးပါ</div>}
          {story.audio_url && <audio className="story-audio" controls preload="none" src={story.audio_url} aria-label="ပုံပြင်အသံဖိုင်" />}
          {!story.audio_url && story.demo_sample && <DemoAudioPlayer compact title={`${story.title} · sound UI preview`} frequency={196} />}
          <div className="reading-body"><p>{story.story}</p></div>
          {story.episodes.length > 1 && <nav className="episode-navigation" aria-label="အပိုင်းများသို့ သွားရန်">{story.episodes.map((episode) => <a key={episode.episode_number} href={`#episode-${episode.episode_number}`}>အပိုင်း {episode.episode_number}</a>)}</nav>}
          {story.episodes.map((episode) => <section className="episode" id={`episode-${episode.episode_number}`} key={episode.episode_number}><span className="episode-label">အပိုင်း {episode.episode_number}</span><h2>{episode.title}</h2><p>{episode.content}</p>{episode.audio_url && episode.audio_status === "READY" && <audio controls preload="none" src={episode.audio_url} />}</section>)}
          {story.quiz?.length ? <section className="public-learning"><span className="eyebrow">CHECK YOUR READING</span><h2>ပုံပြင်နားလည်မှု</h2>{story.quiz.map((item, index) => <details key={index}><summary>{item.question}</summary><p>{item.answer}</p></details>)}</section> : null}
          {story.reflection && <section className="public-learning reflection-card"><span className="eyebrow">A MOMENT TO REFLECT</span><h2>စဉ်းစားကြည့်ရန်</h2><p>{story.reflection}</p></section>}
        </article>}
      </main>
      <SiteFooter />
    </div>
  );
}

function AdminLogin({ onLogin }: { onLogin: (token: string) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(password);
      setPassword("");
      onLogin(result.csrf_token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "ဝင်ရောက်၍ မရပါ။");
    } finally {
      setBusy(false);
    }
  };
  return <div className="login-wrap"><form className="login-card" onSubmit={(event) => void submit(event)}><span className="login-icon"><LockKeyhole size={22} /></span><span className="eyebrow">PRIVATE WORKSPACE</span><h1>စီမံခန့်ခွဲသူ ဝင်ရန်</h1><p>ဤနေရာသည် ခွင့်ပြုထားသော စီမံခန့်ခွဲသူများအတွက်သာ ဖြစ်သည်။</p><label className="form-label" htmlFor="admin-password">စီမံခန့်ခွဲသူ စကားဝှက်</label><input id="admin-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><button className="button button-primary full-width" disabled={busy}>{busy ? "စစ်ဆေးနေသည်…" : "လုံခြုံစွာ ဝင်ရောက်ရန်"} <ArrowRight size={17} /></button>{error && <p className="form-error" role="alert">{error}</p>}</form></div>;
}

function AdminPage() {
  // Admin စာမျက်နှာများ၏ session၊ CSRF၊ စာရင်းအနှစ်ချုပ်နှင့် sidebar လမ်းကြောင်းကို စီမံသည်။
  const location = useLocation();
  const navigate = useNavigate();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [jobs, setJobs] = useState<JobStatus | null>(null);
  const [csrf, setCsrf] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [authenticated, setAuthenticated] = useState(isDemoMode());
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(0);
  const [selectedStory, setSelectedStory] = useState<AdminStory | null>(null);
  const editorStoryId = location.pathname.match(/^\/admin\/stories\/([^/]+)$/)?.[1] ?? "";
  const section = editorStoryId
    ? "editor"
    : adminSections.find((item) => item.path === location.pathname)?.id ?? "overview";
  const pageSize = 6;
  const load = async () => {
    setError("");
    try {
      const [nextOverview, nextJobs] = await Promise.all([api.overview(), api.jobs()]);
      setOverview(nextOverview);
      setJobs(nextJobs);
      setCsrf(nextOverview.csrf_token);
      setAuthenticated(true);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "အချက်အလက် ဖတ်မရပါ။";
      if (message.includes("Authentication required")) setAuthenticated(false);
      else setError(message);
    }
  };
  useEffect(() => {
    if (isDemoMode()) {
      setOverview(demoOverview);
      setJobs(demoJobs);
    } else {
      void load();
    }
  }, []);
  const login = (token: string) => {
    setCsrf(token);
    setAuthenticated(true);
    void load();
  };
  const logout = async () => {
    setBusy(true);
    try {
      await api.logout(csrf);
      setAuthenticated(false);
      setOverview(null);
      setJobs(null);
      setCsrf("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Logout failed.");
    } finally {
      setBusy(false);
    }
  };
  const data = overview ?? (isDemoMode() ? demoOverview : null);
  const jobData = jobs ?? (isDemoMode() ? demoJobs : null);
  const visibleStories = useMemo(() => {
    const rows = (data?.stories ?? []).filter((story) => {
      const matchesSearch = `${story.title} ${story.story_id} ${story.source_name}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase());
      const matchesFilter = filter === "ALL"
        || (filter === "RIGHTS_REVIEW" && story.rights_cleared !== "YES")
        || (filter === "QUEUED" && ["QUEUED", "GENERATING"].includes(story.processing_status))
        || (filter === "DRAFT" && ["DRAFT_READY", "HUMAN_EDITING"].includes(story.processing_status));
      return matchesSearch && matchesFilter;
    });
    return rows.sort((left, right) => sort === "title"
      ? left.title.localeCompare(right.title)
      : sort === "status"
        ? left.processing_status.localeCompare(right.processing_status)
        : left.story_id.localeCompare(right.story_id));
  }, [data, filter, search, sort]);
  if (!authenticated) return <><SiteHeader /><AdminLogin onLogin={login} /><SiteFooter /></>;
  const pages = Math.max(1, Math.ceil(visibleStories.length / pageSize));
  const pagedStories = visibleStories.slice(page * pageSize, (page + 1) * pageSize);
  const sections = adminSections;
  const mainSectionIds = ["overview", "finder", "library", "audio", "publishing", "settings"];
  const displaySectionNames: Record<string, string> = { overview: "Dashboard", finder: "Story Finder", library: "Stories", audio: "Audio Library", publishing: "Published Stories", settings: "Settings" };
  const navigationItem = ({ id, path, label, icon: Icon }: typeof adminSections[number]) => <button key={id} className={`sidebar-item ${section === id || (id === "library" && section === "editor") ? "active" : ""}`} onClick={() => navigate(path)} title={collapsed ? label : undefined}><Icon size={18} /><span>{!isDemoMode() ? displaySectionNames[id] || label : label}</span>{id === "library" && <small>{data?.counts.stories ?? 0}</small>}</button>;
  const renderStoriesTable = (rows: AdminStory[]) => rows.length === 0
    ? <EmptyState title="ပုံပြင်မရှိသေးပါ" detail="ရွေးချယ်ထားသော စစ်ထုတ်မှုနှင့် ကိုက်ညီသည့် မှတ်တမ်း မရှိပါ။" />
    : <div className="table-scroll"><table><thead><tr><th>ပုံပြင်</th><th>အမျိုးအစား</th><th>အခွင့်အရေး</th><th>စစ်ဆေးမှု</th><th>ထုတ်လုပ်မှု</th><th /></tr></thead><tbody>{rows.map((story) => <StoryRow key={story.story_id} story={story} onSelect={() => setSelectedStory(story)} />)}</tbody></table></div>;
  return (
    <div className={`admin-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="admin-sidebar">
        <Link className="brand admin-brand" to="/"><span className="brand-mark"><BookOpen size={29} /></span><span className="brand-word"><strong>PyonPyin</strong><small>Auto Story Project</small></span></Link>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="စီမံခန့်ခွဲမှု">
          {(isDemoMode() ? sections : sections.filter((item) => mainSectionIds.includes(item.id))).map(navigationItem)}
          {!isDemoMode() && <details className="admin-advanced-nav" open={!mainSectionIds.includes(section) && section !== "editor"}><summary>လုပ်ငန်းစဉ် အသေးစိတ်</summary>{sections.filter((item) => !mainSectionIds.includes(item.id)).map(navigationItem)}</details>}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-safety"><span className="safety-icon"><ShieldCheck size={17} /></span><div><strong>လုံခြုံမှု အခြေအနေ</strong><small>{isDemoMode() ? "ထုတ်ဝေမှု ပိတ်ထားသည်" : "ထုတ်ဝေမှုအတွက် Settings ကိုစစ်ပါ"}</small></div><span className="safety-dot" /></div>
        <button className="collapse-button" onClick={() => setCollapsed(!collapsed)}><ChevronLeft size={16} /><span>ဘေးမီနူး ခေါက်ရန်</span></button>
      </aside>
      <div className="admin-workspace">
        <header className="admin-topbar"><div className="topbar-left"><button className="icon-button menu-toggle" onClick={() => setCollapsed(!collapsed)} aria-label="ဘေးမီနူး ဖွင့်ပိတ်"><Menu size={18} /></button><span className="breadcrumb">PYONPYIN <span>/</span> {sections.find((item) => item.id === section)?.label ?? "Story Editor"}</span></div><div className="admin-header-actions">{isDemoMode() && <span className="demo-badge"><span /> DEMO DATA · နမူနာ</span>}{!isDemoMode() && <button className="icon-button" onClick={() => void load()} aria-label="ပြန်လည်ဖတ်ရှုရန်"><Compass size={18} /></button>}<Link className="admin-site-link" to="/">ပုံပြင်ဝဘ်ဆိုက် <ArrowRight size={14} /></Link>{!isDemoMode() && <button className="icon-button" onClick={() => void logout()} disabled={busy} aria-label="ထွက်ရန်"><LogOut size={18} /></button>}</div></header>
        <main className="admin-main">
          <div className="admin-title-row"><div><span className="eyebrow">CONTROL CENTER · {new Date().toLocaleDateString("my-MM")}</span><h1>{!isDemoMode() ? displaySectionNames[section] || sections.find((item) => item.id === section)?.label : sections.find((item) => item.id === section)?.label}</h1><p>PyonPyin Auto Story Project · Story Management Center</p></div><div className="admin-title-icon"><LayoutDashboard size={23} /></div></div>
          {isDemoMode() && <div className="demo-notice"><CircleHelp size={18} /><span><strong>Demo preview — နမူနာဒေတာသာ ဖြစ်သည်။</strong> ဤအချက်အလက်များသည် Google Sheets မှ မဟုတ်သလို အမှန်တကယ် ထုတ်ဝေထားသော ပုံပြင်များ မဟုတ်ပါ။</span></div>}
          {notice && <div className="toast-note" role="status"><CheckCircle2 size={17} />{notice}</div>}
          {error && <ErrorState message={error} retry={() => void load()} />}
          {data ? <div className="section-transition" key={section}>
            {section === "overview" && !isDemoMode() && <ManagementDashboard counts={data.counts} stories={data.stories} jobs={jobData} />}
            {section === "overview" && isDemoMode() && <>
              <section className="metrics-grid" aria-label="အနှစ်ချုပ်">
                <Metric icon={<LibraryBig />} label="ပုံပြင်ရှာဖွေတွေ့ရှိမှု" count={data.counts.stories} color="blue" />
                <Metric icon={<Clock3 />} label="အခွင့်အရေး စစ်ဆေးရန်" count={data.counts.rights_review} color="amber" />
                <Metric icon={<FileText />} label="အကြောင်းအရာ စစ်ဆေးရန်" count={data.counts.content_review} color="violet" />
                <Metric icon={<CheckCircle2 />} label="အတည်ပြုမူကြမ်း" count={data.counts.approved} color="green" />
                <Metric icon={<AudioLines />} label="အသံဖိုင် အဆင်သင့်" count={data.counts.audio_ready} color="cyan" />
                <Metric icon={<BookOpen />} label="မူကြမ်းများ" count={data.counts.drafts} color="violet" />
                <Metric icon={<Sparkles />} label="ထုတ်ဝေပြီး" count={data.counts.published} color="blue" />
              </section>
              <div className="dashboard-columns">
                <section className="admin-panel chart-panel"><div className="panel-heading"><div><span className="eyebrow">PIPELINE HEALTH</span><h2>လုပ်ငန်းစဉ်အခြေအနေ</h2></div><span className="panel-icon"><Workflow size={18} /></span></div><PipelineChart counts={data.counts} /></section>
                <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">PRODUCTION QUEUE</span><h2>အလုပ်တန်းစီ</h2></div><button className="small-link" onClick={() => navigate("/admin/production")}>အသေးစိတ် <ArrowRight size={13} /></button></div><QueuePreview stories={data.stories} /></section>
              </div>
              <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">RECENT STORIES</span><h2>နောက်ဆုံး လုပ်ဆောင်မှု</h2></div><button className="small-link" onClick={() => navigate("/admin/stories")}>စာကြည့်တိုက် <ArrowRight size={13} /></button></div>{renderStoriesTable(data.stories.slice(0, 5))}</section>
              {jobData && <section className="admin-panel jobs-panel"><JobTimeline jobs={jobData} /></section>}
            </>}
            {section === "finder" && (isDemoMode() ? <FinderStudio /> : <LiveFinder csrf={csrf} onUpdated={() => { void load(); }} />)}
            {section === "library" && <section className="admin-panel library-panel"><div className="panel-heading"><div><span className="eyebrow">STORY LIBRARY</span><h2>ရင်းမြစ်နှင့် အခွင့်အရေး စစ်ဆေးမှု</h2></div><span className="panel-count">{visibleStories.length} ခု</span></div><div className="library-toolbar"><label className="search-field"><Search size={17} /><input aria-label="စီမံခန့်ခွဲမှု ပုံပြင်ရှာရန်" placeholder="ခေါင်းစဉ်၊ ID သို့မဟုတ် ရင်းမြစ်…" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} /></label><select aria-label="အခြေအနေ စစ်ထုတ်ရန်" value={filter} onChange={(event) => { setFilter(event.target.value); setPage(0); }}><option value="ALL">အခြေအနေအားလုံး</option><option value="RIGHTS_REVIEW">အခွင့်အရေး စစ်ဆေးရန်</option><option value="QUEUED">တန်းစီနေသည်</option><option value="DRAFT">မူကြမ်းရှိသည်</option></select><select aria-label="စီစဉ်ရန်" value={sort} onChange={(event) => setSort(event.target.value)}><option value="recent">ID အလိုက်</option><option value="title">ခေါင်းစဉ်အလိုက်</option><option value="status">အခြေအနေအလိုက်</option></select></div>{renderStoriesTable(pagedStories)}<div className="pagination"><span>{visibleStories.length ? `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, visibleStories.length)} / ${visibleStories.length}` : "မှတ်တမ်း မရှိပါ"}</span><div><button className="icon-button" aria-label="ယခင်စာမျက်နှာ" disabled={page === 0} onClick={() => setPage(Math.max(0, page - 1))}><ChevronLeft size={16} /></button><span>{page + 1} / {pages}</span><button className="icon-button" aria-label="နောက်စာမျက်နှာ" disabled={page + 1 >= pages} onClick={() => setPage(Math.min(pages - 1, page + 1))}><ChevronRight size={16} /></button></div></div></section>}
            {section === "rights" && <RightsReview stories={data.stories} csrfToken={csrf} onUpdated={() => { void load(); }} />}
            {section === "production" && <>{!isDemoMode() && <MvpWorkspace csrf={csrf} onUpdated={() => { void load(); }} onOpen={(id) => navigate(`/admin/stories/${id}`)} />}{!jobData?.local_jobs && <ProductionQueue stories={data.stories} jobs={jobData} csrfToken={csrf} onUpdated={() => { void load(); }} />}{jobData && <section className="admin-panel"><JobTimeline jobs={jobData} /></section>}</>}
            {section === "editor" && <StoryEditor storyId={editorStoryId} csrfToken={csrf} onClose={() => navigate("/admin/stories")} onUpdated={() => { void load(); }} />}
            {section === "review" && <ReviewWorkspace stories={data.stories} onOpen={(id) => navigate(`/admin/stories/${encodeURIComponent(id)}`)} />}
            {section === "episodes" && <EpisodeWorkspace stories={data.stories} onOpen={(id) => navigate(`/admin/stories/${encodeURIComponent(id)}`)} />}
            {section === "audio" && (isDemoMode() ? <AudioStudio onNotice={setNotice} /> : <LiveAudioStudio />)}
            {section === "activity" && <section className="admin-panel"><JobTimeline jobs={jobData ?? demoJobs} expanded /></section>}
            {section === "publishing" && !isDemoMode() && <PublicationArchive stories={data.stories} />}
            {section === "publishing" && isDemoMode() && <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">PUBLICATION AUDIT</span><h2>ထုတ်ဝေမှုမှတ်တမ်း</h2></div><StatusBadge value={isDemoMode() ? "PUBLISHING_DISABLED" : "HUMAN_APPROVAL_REQUIRED"} /></div>{jobData?.publishing_history.length ? <div className="history-list">{jobData.publishing_history.map((item, index) => <div className="history-row" key={`${item.story_id}-${index}`}><span>{item.published_title || item.story_id}</span><StatusBadge value={item.publication_status} /><small>{item.published_at} · {item.approved_by}</small></div>)}</div> : <EmptyState title="ထုတ်ဝေမှုမှတ်တမ်း မရှိသေးပါ" detail="အတည်ပြုထားသော ထုတ်ဝေမှုမှတ်တမ်းများကို ဤနေရာတွင်သာ ဖတ်ရှုနိုင်ပါသည်။" />}</section>}
            {section === "settings" && !isDemoMode() && <><ImageManager csrf={csrf} /><MvpSettings /></>}{section === "settings" && isDemoMode() && <><section className="admin-panel settings-panel"><div className="panel-heading"><div><span className="eyebrow">PLATFORM SAFETY</span><h2>လုံခြုံရေးနှင့် ထုတ်ဝေမှု</h2></div><ShieldCheck size={20} /></div><div className="setting-row"><div><strong>အလိုအလျောက် ထုတ်ဝေမှု</strong><p>လူသား၏ အတည်ပြုချက် မပါဘဲ ပုံပြင် မထုတ်ဝေပါ။</p></div><StatusBadge value="DISABLED" /></div><div className="setting-row"><div><strong>AI job ကို ဤမျက်နှာပြင်မှ စတင်ခြင်း</strong><p>Agent job dispatch ကို မချိတ်ဆက်ရသေးပါ။ လက်ရှိတွင် status များကိုသာ ကြည့်နိုင်ပါသည်။</p></div><StatusBadge value="NOT_CONFIGURED" /></div><div className="setting-row"><div><strong>အမျိုးအစား သတ်မှတ်ချက်</strong><p>ကလေး/လူကြီး အမျိုးအစားကို အထောက်အထားမရှိဘဲ မခန့်မှန်းပါ။</p></div><StatusBadge value="HUMAN_REVIEW" /></div><div className="setting-row"><div><strong>လျှို့ဝှက်ချက်များ</strong><p>Google၊ Gemini နှင့် GitHub credentials များကို server-side environment တွင်သာ ထားပါသည်။</p></div><StatusBadge value="SERVER_ONLY" /></div></section><section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">AUDIO PROVIDER</span><h2>မြန်မာအသံဖိုင်</h2></div><AudioLines size={18} /></div><p className="panel-description">လက်ရှိတွင် အတည်ပြုပြီးသော မြန်မာ TTS voice မရှိသေးပါ။ အသံဖိုင်များကို READY အဖြစ် အလိုအလျောက် မမှတ်သားပါ။</p></section></>}
          </div> : error ? null : <LoadingState />}
        </main>
        <footer className="admin-footer"><span>PYONPYIN AI · ADMIN WORKSPACE</span><span>အတည်ပြုမှု မရှိလျှင် ထုတ်ဝေမှု မပြုပါ</span></footer>
      </div>
      {selectedStory && <StoryDetailDrawer story={selectedStory} onClose={() => setSelectedStory(null)} onEdit={() => { navigate(`/admin/stories/${encodeURIComponent(selectedStory.story_id)}`); setSelectedStory(null); }} />}
    </div>
  );
}

function FinderStudio() {
  // လက်ရှိ demo scan သာဖြစ်ပြီး တကယ့် feed သို့မဟုတ် discovery job ကို မခေါ်သေးပါ။
  const [checked, setChecked] = useState(false);
  const [message, setMessage] = useState("");
  return <div className="admin-subpages">
    <section className="admin-panel finder-hero">
      <div><span className="eyebrow">SOURCE DISCOVERY · DEMO</span><h2>Story Finder</h2><p>Configured source feeds and candidate discovery, shown with fixtures only.</p></div>
      <button className="button button-primary" onClick={() => { setChecked(true); setMessage("Demo scan complete — no feeds, Sheets, or external services were contacted."); }}>Run demo scan <Compass size={16} /></button>
    </section>
    {message && <div className="toast-note" role="status"><CheckCircle2 size={17} />{message}</div>}
    <div className="subpage-grid two">
      <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">SOURCE CONNECTORS</span><h2>Configured sources</h2></div><span className="badge pending">DEMO MODE</span></div>
        {[["Open Library sample catalog", "Catalog metadata only", "READY"], ["Public-domain text feed", "HTTPS source · rights evidence required", "REVIEW GATE"], ["Local theme prompt", "No source text or identifying details", "SAFE PATH"]].map(([name, note, state]) => <div className="source-fixture" key={name}><span className="source-status-dot" /><div><strong>{name}</strong><small>{note}</small></div><StatusBadge value={state} /></div>)}
      </section>
      <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">LAST DISCOVERY CYCLE</span><h2>{checked ? "Just now · simulated" : "Today · fixture"}</h2></div><Workflow size={19} /></div><div className="finder-stat-grid"><div><strong>{checked ? "08" : "12"}</strong><span>candidates checked</span></div><div><strong>{checked ? "03" : "05"}</strong><span>new candidates</span></div><div><strong>00</strong><span>sent to AI</span></div></div><p className="panel-description">Only source-level policy and verified audience evidence can move a story forward. This demo scan never calls the agent.</p></section>
    </div>
    <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">CANDIDATE INBOX</span><h2>Discovery candidates</h2></div><span className="panel-count">3 sample records</span></div>
      <div className="candidate-grid">{demoOverview.stories.slice(0, 3).map((story, index) => <article className="candidate-card" key={story.story_id}><div className="candidate-number">0{index + 1}</div><div><h3>{story.title}</h3><p>Source: demonstration fixture · audience remains unclassified</p><div className="badge-row"><StatusBadge value={story.license_status} /><StatusBadge value={story.category} /></div></div><span className="candidate-lock"><ShieldAlert size={16} /> Review required</span></article>)}</div>
    </section>
  </div>;
}

function RightsReview({ stories, csrfToken, onUpdated }: { stories: AdminStory[]; csrfToken: string; onUpdated: () => void }) {
  const demoMode = isDemoMode();
  return <div className="admin-subpages">
    <section className="admin-panel rights-intro"><div className="rights-icon"><ShieldAlert size={22} /></div><div><span className="eyebrow">COPYRIGHT & LICENSE WORKSPACE</span><h2>Rights review is required</h2><p>{demoMode ? "Records below are demo fixtures. Unknown or pending rights are not permission and cannot be approved here." : "Record only verified evidence and permissions. A category remains unclassified until you enter reliable evidence."}</p></div><span className="badge bad">NO AUTO-CLEARANCE</span></section>
    <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">UNRESOLVED SOURCES</span><h2>Evidence checklist</h2></div><span className="panel-count">{stories.length} awaiting review</span></div>
      <div className="rights-list">{stories.map((story) => <article className="rights-row" key={story.story_id}><div className="rights-story"><span className="rights-lock"><LockKeyhole size={16} /></span><div><strong>{story.title}</strong><small>{story.source_name} · {story.story_id}</small><a href={story.source_url} target="_blank" rel="noreferrer">Open source record</a></div></div><div><span className="field-caption">License status</span><StatusBadge value={story.license_status || "NEEDS_REVIEW"} /></div><div><span className="field-caption">Rights clearance</span><StatusBadge value={story.rights_cleared || "NO"} /></div><div><span className="field-caption">Audience evidence</span><StatusBadge value={story.category} /></div><details className="rights-evidence"><summary>View evidence and review requirements</summary><div><span>License evidence</span><p>{story.license_evidence || "No evidence recorded; human review required."}</p><span>Jurisdiction</span><p>{story.rights_jurisdiction || "Not established"}</p><span>Category evidence</span><p>{story.category_evidence || "Audience unclassified — do not guess."}</p><span>Reviewer</span><p>{story.human_reviewer || "Not assigned"}</p><small>Source text is not sent to Gemini from this page.</small></div></details>{!demoMode && <RightsReviewForm story={story} csrfToken={csrfToken} onUpdated={onUpdated} />}</article>)}</div>
      <div className="safety-inline"><ShieldCheck size={17} /> {demoMode ? "Demo rights are not changed or approved. " : "Every decision is saved with explicit reviewer-entered evidence. "}Theme-only generation never receives source text, title, author, or URL.</div>
    </section>
  </div>;
}

function RightsReviewForm({ story, csrfToken, onUpdated }: { story: AdminStory; csrfToken: string; onUpdated: () => void }) {
  // ပုံပြင်တစ်ပုဒ်စီ၏ အသက်အုပ်စုနှင့် အသုံးပြုခွင့်ဆိုင်ရာ လူစစ်ချက်ကို သိမ်းပေးသော form ဖြစ်သည်။
  const [draft, setDraft] = useState({
    category: story.category || "UNCLASSIFIED",
    category_evidence: story.category_evidence || "",
    license_status: story.license_status || "NEEDS_LICENSE_REVIEW",
    rights_cleared: story.rights_cleared || "NO",
    human_reviewer: story.human_reviewer || "",
    license_evidence: story.license_evidence || "",
    rights_jurisdiction: story.rights_jurisdiction || "",
    permission_for_translation: story.permission_for_translation || "NO",
    permission_for_ai_processing: story.permission_for_ai_processing || "NO",
    permission_for_publication: story.permission_for_publication || "NO",
    permission_for_audio: story.permission_for_audio || "NO",
    permission_for_commercial_use: story.permission_for_commercial_use || "NO",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const update = (key: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api.reviewRights(story.story_id, csrfToken, draft);
      setSaved(true);
      onUpdated();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Rights review could not be saved.");
    } finally {
      setBusy(false);
    }
  };
  const permission = (key: keyof typeof draft, label: string) => (
    <label>{label}<select value={draft[key]} onChange={(event) => update(key, event.target.value)}><option value="NO">NO</option><option value="YES">YES</option></select></label>
  );
  return <form className="rights-review-form" onSubmit={(event) => void submit(event)}>
    <span className="field-caption">Human-entered review — saving a decision does not publish</span>
    <div className="rights-form-grid">
      <label>Audience classification<select value={draft.category} onChange={(event) => update("category", event.target.value)}><option value="UNCLASSIFIED">UNCLASSIFIED</option><option value="CHILDREN">CHILDREN</option><option value="ADULT">ADULT</option></select></label>
      <label>License status<select value={draft.license_status} onChange={(event) => update("license_status", event.target.value)}><option value="NEEDS_LICENSE_REVIEW">NEEDS_LICENSE_REVIEW</option><option value="PENDING_REVIEW">PENDING_REVIEW</option><option value="APPROVED">APPROVED</option><option value="REJECTED">REJECTED</option></select></label>
      <label>Rights cleared<select value={draft.rights_cleared} onChange={(event) => update("rights_cleared", event.target.value)}><option value="NO">NO</option><option value="YES">YES</option></select></label>
      <label>Rights jurisdiction<input maxLength={5000} value={draft.rights_jurisdiction} onChange={(event) => update("rights_jurisdiction", event.target.value)} /></label>
      <label>Human reviewer<input required maxLength={5000} value={draft.human_reviewer} onChange={(event) => update("human_reviewer", event.target.value)} /></label>
      <label className="rights-form-wide">Audience evidence<textarea maxLength={5000} value={draft.category_evidence} onChange={(event) => update("category_evidence", event.target.value)} /></label>
      <label className="rights-form-wide">License evidence<textarea maxLength={5000} value={draft.license_evidence} onChange={(event) => update("license_evidence", event.target.value)} /></label>
      {permission("permission_for_translation", "Translation permission")}
      {permission("permission_for_ai_processing", "AI processing permission")}
      {permission("permission_for_publication", "Publication permission")}
      {permission("permission_for_audio", "Audio permission")}
      {permission("permission_for_commercial_use", "Commercial use permission")}
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {saved && <p className="rights-saved" role="status">Rights review saved. No content was published.</p>}
    <button className="button button-quiet" disabled={busy}>{busy ? "Saving…" : "Save rights review"}</button>
  </form>;
}

function ReviewWorkspace({ stories, onOpen }: { stories: AdminStory[]; onOpen: (id: string) => void }) {
  const demoMode = isDemoMode();
  const [decisions, setDecisions] = useState<Record<string, string>>(() => {
    if (!isDemoMode()) return {};
    const stored = window.localStorage.getItem("pyonpyin-demo-review-status");
    return stored ? JSON.parse(stored) as Record<string, string> : {};
  });
  const [message, setMessage] = useState("");
  const decide = (storyId: string, action: "APPROVED" | "REJECTED") => {
    const next = { ...decisions, [storyId]: action };
    window.localStorage.setItem("pyonpyin-demo-review-status", JSON.stringify(next));
    setDecisions(next);
    setMessage(`DEMO · Content review marked ${action.toLowerCase()} in this browser only. No publication approval was granted.`);
  };
  return <div className="admin-subpages">
    <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">HUMAN REVIEW WORKSPACE</span><h2>Draft review queue</h2><p className="panel-description">Demo content approval is separate from rights clearance and publication approval.</p></div><StatusBadge value={isDemoMode() ? "PUBLISHING_DISABLED" : "HUMAN_APPROVAL_REQUIRED"} /></div>{message && <div className="toast-note" role="status"><CheckCircle2 size={16} />{message}</div>}
      <div className="review-cards">{stories.filter((story) => story.processing_status === "DRAFT_READY" || story.processing_status === "HUMAN_EDITING" || story.processing_status === "QUEUED").map((story) => <article className="review-card" key={story.story_id}><div className="review-card-top"><span className="eyebrow">{demoMode ? "DEMO DRAFT" : "SERVER DRAFT"} · {story.story_id}</span><StatusBadge value={decisions[story.story_id] ?? story.processing_status} /></div><h3>{story.title}</h3><p>Rights: {story.license_status} · Audience: {story.category}</p><div className="review-action-row"><button className="button button-quiet" onClick={() => onOpen(story.story_id)}><PenLine size={15} /> Review draft</button>{demoMode && <><button className="button button-review" onClick={() => decide(story.story_id, "APPROVED")}><CheckCircle2 size={15} /> Demo approve content</button><button className="button button-reject" onClick={() => decide(story.story_id, "REJECTED")}><XCircle size={15} /> Demo reject</button></>}</div><small>{demoMode ? "Browser-only content decision · not rights approval · never publishes" : "Use the authenticated editor for content review. Rights clearance remains separate."}</small></article>)}</div>
      {!stories.some((story) => ["DRAFT_READY", "HUMAN_EDITING", "QUEUED"].includes(story.processing_status)) && <EmptyState title="Review queue is clear" detail="New drafts will appear here after a production run." />}
    </section>
  </div>;
}

function EpisodeWorkspace({ stories, onOpen }: { stories: AdminStory[]; onOpen: (id: string) => void }) {
  const demoMode = isDemoMode();
  const [episodesByStory, setEpisodesByStory] = useState<Record<string, {
    episodes: AdminStoryDetail["episodes"];
    error: string;
  }>>({});
  useEffect(() => {
    let cancelled = false;
    setEpisodesByStory({});
    const loadEpisodes = async () => {
      const results = await Promise.all(stories.map(async (story) => {
        try {
          const detail = demoMode
            ? loadDemoStoryDetail(story.story_id)
            : await api.story(story.story_id);
          return [story.story_id, { episodes: detail.episodes, error: "" }] as const;
        } catch (cause) {
          return [story.story_id, {
            episodes: [],
            error: cause instanceof Error ? cause.message : "Episode details could not be loaded.",
          }] as const;
        }
      }));
      if (!cancelled) setEpisodesByStory(Object.fromEntries(results));
    };
    void loadEpisodes();
    return () => { cancelled = true; };
  }, [demoMode, stories]);

  return <section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">CONTINUITY WORKSPACE</span><h2>Episode manager</h2><p className="panel-description">{demoMode ? "Demo episode details are read from the local sample fixture." : "Episode sequence and review state are read from the authenticated Flask API; edits open in the story editor."}</p></div><BookOpen size={20} /></div>
    {!stories.length && <EmptyState title="No story records" detail="Stories will appear here after discovery." />}
    <div className="episode-manager-list">{stories.map((story, index) => {
      const record = episodesByStory[story.story_id];
      return <article className="episode-manager-card" key={story.story_id}>
        <div className={`episode-manager-cover cover-${index % 4}`}><BookOpen size={21} /></div>
        <div className="episode-manager-main">
          <span className="eyebrow">{story.story_id}{demoMode ? " · DEMO" : " · SERVER RECORD"}</span>
          <h3>{story.title}</h3>
          <p>{burmeseCategory[story.category] || "Audience unclassified"} · {record ? `${record.episodes.length} episode(s)` : "Loading episode details…"}</p>
          {record?.error && <p className="form-error" role="alert">{record.error}</p>}
          {!!record?.episodes.length && <div className="episode-sequence">{record.episodes.map((episode, episodeIndex) => <span className="episode-step current" key={`${story.story_id}-${episode.episode_number}`}>{String(episode.episode_number).padStart(2, "0")} <small>{episode.title || `Episode ${episodeIndex + 1}`}</small></span>)}</div>}
          {record && !record.error && !record.episodes.length && <p>No episodes are saved for this story yet.</p>}
        </div>
        <button className="button button-quiet" onClick={() => onOpen(story.story_id)}>Open editor <ArrowRight size={15} /></button>
      </article>;
    })}</div>
  </section>;
}

function AudioStudio({ onNotice }: { onNotice: (message: string) => void }) {
  const [selectedId, setSelectedId] = useState(demoTracks[0].id);
  const selected = demoTracks.find((track) => track.id === selectedId) ?? demoTracks[0];
  return <div className="admin-subpages">
    <section className="admin-panel audio-studio-hero"><div><span className="eyebrow">AUDIO STUDIO · PROVIDER NOT CONFIGURED</span><h2>မြန်မာအသံအတွေ့အကြုံကို ဒီဇိုင်းဆွဲပါ</h2><p>Preview သည် ဘရောက်ဇာတွင် ဖန်တီးသော tone သာဖြစ်ပြီး TTS၊ မြန်မာစကားပြောသံ သို့မဟုတ် ဇာတ်လမ်းအသံ မဟုတ်ပါ။</p></div><span className="audio-wave-icon"><AudioLines size={24} /></span></section>
    <div className="audio-studio-layout">
      <section className="admin-panel audio-track-panel"><div className="panel-heading"><div><span className="eyebrow">STORY TRACKS</span><h2>Audio library</h2></div><span className="panel-count">{demoTracks.length} demos</span></div><div className="audio-track-list">{demoTracks.map((track, index) => <button className={`audio-track-row ${selectedId === track.id ? "selected" : ""}`} key={track.id} onClick={() => setSelectedId(track.id)}><span className={`audio-track-art track-art-${index}`}><Music2 size={18} /></span><span className="audio-track-title"><strong>{track.title}</strong><small>{track.language} · {Math.floor(track.duration / 60)}:{String(track.duration % 60).padStart(2, "0")}</small></span><StatusBadge value={track.status} /></button>)}</div></section>
      <div className="audio-studio-right"><section className="admin-panel"><div className="panel-heading"><div><span className="eyebrow">PLAYER PREVIEW</span><h2>{selected.title}</h2></div><span className="voice-pill"><Music2 size={14} /> DEMO VOICE</span></div><DemoAudioPlayer key={selected.id} title={selected.title} duration={selected.duration} frequency={selected.frequency} onNotice={onNotice} /></section><section className="admin-panel audio-metadata"><div className="panel-heading"><div><span className="eyebrow">TRACK METADATA</span><h2>Provider & generation</h2></div><ShieldCheck size={18} /></div><div className="audio-meta-grid"><div><small>Voice</small><strong>{selected.voice}</strong></div><div><small>Language</small><strong>{selected.language}</strong></div><div><small>Generation status</small><StatusBadge value={selected.status} /></div><div><small>Rights permission</small><StatusBadge value="NEEDS REVIEW" /></div></div><div className="audio-generation-actions"><button className="button button-primary" onClick={() => onNotice("DEMO · Reset a browser-generated tone only. No TTS provider was called.")}><RotateCcw size={15} /> Regenerate demo preview</button><span>Does not create or store a story audio file.</span></div></section></div>
    </div>
  </div>;
}

function ProductionQueue({ stories, jobs, csrfToken, onUpdated }: {
  stories: AdminStory[];
  jobs: JobStatus | null;
  csrfToken: string;
  onUpdated: () => void;
}) {
  // QUEUED ပုံပြင်ကိုရွေး၍ server-side GitHub dispatch ခေါ်ရန်ဖြစ်ပြီး configuration လိုသည်။
  const queuedStories = stories.filter((story) => story.processing_status === "QUEUED");
  const [storyId, setStoryId] = useState(queuedStories[0]?.story_id ?? "");
  const anotherJobActive = stories.some((story) =>
    story.story_id !== storyId && ["DISPATCHED", "GENERATING"].includes(story.processing_status),
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const dispatch = async () => {
    if (!storyId || !jobs?.dispatch_configured) return;
    if (!window.confirm("This starts a GitHub Actions job that may use Gemini quota or incur cost. Continue?")) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await api.dispatchJob(storyId, csrfToken);
      setMessage(`Workflow dispatch accepted for ${result.story_id}. Check job status for progress; content remains a draft.`);
      onUpdated();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Workflow dispatch failed.");
    } finally {
      setBusy(false);
    }
  };
  return <section className="admin-panel">
    <div className="panel-heading"><div><span className="eyebrow">STORY WORKSPACE</span><h2>Story Production queue</h2></div><StatusBadge value={isDemoMode() ? "PUBLISHING_DISABLED" : "HUMAN_APPROVAL_REQUIRED"} /></div>
    <p className="panel-description">Only an already-queued, policy-eligible story can be selected. Dispatch is separately disabled until the server and Gemini automation are explicitly configured.</p>
    <div className="production-dispatch">
      <label>Queued story<select aria-label="Queued story to process" value={storyId} onChange={(event) => setStoryId(event.target.value)} disabled={!queuedStories.length || busy}>
        {queuedStories.length ? queuedStories.map((story) => <option key={story.story_id} value={story.story_id}>{story.title} · {story.story_id}</option>) : <option value="">No queued stories</option>}
      </select></label>
      <button className="button button-primary" type="button" disabled={!jobs?.dispatch_configured || !queuedStories.length || anotherJobActive || busy} onClick={() => void dispatch()}>
        {busy ? "Dispatching…" : "Run selected story"}
      </button>
    </div>
    {!jobs?.dispatch_configured && <p className="panel-description">Not configured: enable server-side GitHub dispatch and Gemini automation, and provide the Actions token, repository, and branch. No action was taken.</p>}
    {anotherJobActive && <p className="panel-description">A story is already dispatched or generating. Wait for its status to resolve before dispatching another.</p>}
    {message && <p className="rights-saved" role="status">{message}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {stories.length ? <div className="production-status-list">{stories.filter((story) => ["QUEUED", "DISPATCHED", "DISPATCH_UNKNOWN", "GENERATING", "DRAFT_READY", "HUMAN_EDITING", "CONTENT_APPROVED", "REJECTED", "FAILED", "DISPATCH_FAILED"].includes(story.processing_status)).map((story) => <div key={story.story_id}><span>{story.title}</span><StatusBadge value={story.processing_status} />{story.processing_error && <small>{story.processing_error}</small>}</div>)}</div> : <EmptyState title="No stories available" detail="Discovered stories will appear after the backend has records." />}
  </section>;
}

function StoryEditor({ storyId, csrfToken, onClose, onUpdated }: { storyId: string; csrfToken: string; onClose: () => void; onUpdated: () => void }) {
  // စာသား၊ အပိုင်း၊ quiz နှင့် အသံ URL ပြင်နိုင်သည်။ Demo တွင် browser ထဲသာသိမ်းပြီး live တွင် API သုံးသည်။
  const [detail, setDetail] = useState<AdminStoryDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [editorStep, setEditorStep] = useState("basic");

  const load = async () => {
    setError("");
    try {
      const result = isDemoMode()
        ? loadDemoStoryDetail(storyId)
        : await api.story(storyId);
      setDetail(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "မူကြမ်း ဖတ်မရပါ။");
    }
  };
  useEffect(() => { void load(); }, [storyId]);

  const updateProduction = (key: string, value: string) => {
    setDetail((current) => current ? {
      ...current,
      production: { ...current.production, [key]: value },
    } : current);
  };
  const updateEpisode = (index: number, key: string, value: string) => {
    setDetail((current) => current ? {
      ...current,
      episodes: current.episodes.map((episode, episodeIndex) => episodeIndex === index
        ? { ...episode, [key]: key === "episode_number" ? Number(value) : value }
        : episode),
    } : current);
  };
  const updateQuiz = (index: number, key: "question" | "answer", value: string) => {
    setDetail((current) => current ? {
      ...current,
      quiz: current.quiz.map((item, itemIndex) => itemIndex === index
        ? { ...item, [key]: value }
        : item),
    } : current);
  };
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!detail) return;
    if (isDemoMode()) {
      const updated = {
        ...detail,
        production: {
          ...detail.production,
          audio_url: "",
          audio_status: "NOT_READY",
          processing_status: "HUMAN_EDITING",
          content_review_status: "PENDING",
          approval_status: "",
        },
      };
      saveDemoStoryDetail(storyId, updated);
      setDetail(updated);
      setNotice("DEMO · ပြင်ဆင်မှုကို ဤဘရောက်ဇာတွင်သာ သိမ်းထားသည်။ Google Sheets သို့ မပို့ပါ။");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.saveDraft(storyId, csrfToken, {
        myanmar_title: detail.production.myanmar_title || "",
        myanmar_story: detail.production.myanmar_story || "",
        episodes: detail.episodes,
        quiz: detail.quiz,
        reflection: detail.reflection,
      });
      setNotice("မူကြမ်း သိမ်းပြီးပါပြီ။ စာသားပြင်ထားလျှင် အကြောင်းအရာကို ပြန်စစ်အတည်ပြုပါ။");
      onUpdated();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "မူကြမ်း သိမ်းမရပါ။");
    } finally {
      setBusy(false);
    }
  };
  const review = async (action: "approve" | "reject") => {
    if (!detail) return;
    if (isDemoMode()) {
      const updated = {
        ...detail,
        production: {
          ...detail.production,
          content_review_status: action === "approve" ? "APPROVED" : "REJECTED",
          processing_status: action === "approve" ? "CONTENT_APPROVED" : "REJECTED",
          approval_status: "",
        },
      };
      saveDemoStoryDetail(storyId, updated);
      setDetail(updated);
      setNotice(action === "approve"
        ? "DEMO · Content review ကို အတည်ပြုပြီးပါပြီ။ ထုတ်ဝေခွင့်မဟုတ်ပါ။"
        : "DEMO · မူကြမ်းကို ပယ်ချထားသည်။ ပြောင်းလဲမှုကို ဤဘရောက်ဇာတွင်သာ သိမ်းထားသည်။");
      return;
    }
    const prompt = action === "approve"
      ? "ဤမူကြမ်း၏ အကြောင်းအရာကို အတည်ပြုမည်လား။ ထုတ်ဝေခွင့် မပေးပါ။"
      : "ဤမူကြမ်းအကြောင်းအရာကို ပယ်ချမည်လား။";
    if (!window.confirm(prompt)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.reviewContent(storyId, action, csrfToken);
      setNotice(action === "approve"
        ? "အကြောင်းအရာ review အတည်ပြုပြီးပါပြီ။ ဤလုပ်ဆောင်ချက်သည် ထုတ်ဝေခြင်း မဟုတ်ပါ။"
        : "မူကြမ်းအကြောင်းအရာကို ပယ်ချပြီး မှတ်တမ်းတင်ထားပါသည်။");
      updateProduction("content_review_status", result.content_review_status);
      onUpdated();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Review လုပ်ဆောင်မရပါ။");
    } finally {
      setBusy(false);
    }
  };
  if (error && !detail) return <section className="admin-panel"><button className="back-link" onClick={onClose}>← ပြန်သွားရန်</button><ErrorState message={error} retry={() => void load()} /></section>;
  if (!detail) return <LoadingState />;
  const hasWorkspace = Boolean(detail.production.draft_mode || detail.production.processing_status || detail.production.myanmar_story);
  if (!hasWorkspace) return <section className="admin-panel story-editor workspace-not-started">
    <span className="eyebrow">ရှာတွေ့ထားသော ရင်းမြစ်</span>
    <h2>{detail.story.original_title || "ပုံပြင်ရင်းမြစ်"}</h2>
    <div className="workflow-callout"><h3>မူကြမ်း မစတင်ရသေးပါ</h3>
      <p>ဤမှတ်တမ်းသည် ရှာတွေ့ထားသော ရင်းမြစ်စာရင်းဖြစ်ပြီး AI မူကြမ်း မရှိသေးပါ။ ပုံပြင်အသစ် စမ်းထုတ်ရန် အောက်ပါခလုတ်မှ ခေါင်းစဉ်၊ ပရိသတ်နှင့် theme ကိုရွေးပါ။</p>
      <p>ရင်းမြစ်၏ အမျိုးအစား — {burmeseCategory[detail.story.category] || "မသတ်မှတ်ရသေး"}</p>
    </div>
    <div className="workflow-actions"><Link className="button button-primary" to="/admin/production">AI ပုံပြင်အသစ် ဖန်တီးရန် <ArrowRight size={16} /></Link>
      <Link className="button button-quiet" to="/admin/rights">ရင်းမြစ်အခွင့်အရေး စစ်ဆေးရန်</Link></div>
  </section>;
  if (!detail.production.myanmar_story) return <section className="admin-panel story-editor">
    <button className="back-link" onClick={onClose}>← စာရင်းသို့</button>
    <h2>{detail.story.original_title || "ပုံပြင်အသစ်"}</h2>
    <p>Workspace ဖန်တီးပြီးပါပြီ။ AI မူကြမ်းကို အရင်ထုတ်ပြီးမှ စာသားပြင်ခြင်း၊ review နှင့် အသံထုတ်ခြင်း ဆက်လုပ်နိုင်ပါမည်။</p>
    <MvpStoryActions storyId={storyId} csrf={csrfToken} detail={detail} refresh={async () => { await load(); onUpdated(); }} />
  </section>;
  const setEpisodeContent = (index: number, content: string) => updateEpisode(index, "content", content);
  return <section className={`admin-panel story-editor ${!isDemoMode() ? "editor-redesign" : ""}`} onClickCapture={(event) => {
    const anchor = (event.target as HTMLElement).closest("a");
    if (anchor?.getAttribute("href") === "#story-audio") { event.preventDefault(); setEditorStep("audio"); }
    if (anchor?.getAttribute("href") === "#story-review") { event.preventDefault(); setEditorStep("review"); }
  }}>
    <div className="editor-heading"><div><button className="back-link" onClick={onClose}>← Story Production တန်းစီသို့</button><span className="eyebrow">DRAFT WORKSPACE · {storyId}</span><h2>{detail.story.original_title || "မူကြမ်း workspace"}</h2></div><StatusBadge value={detail.production.content_review_status || "PENDING"} /></div>
    {isDemoMode() && <div className="demo-notice"><CircleHelp size={17} /><span>Demo fixture — ဤဇာတ်လမ်းနှင့် rights metadata သည် စမ်းသပ်နမူနာသာဖြစ်သည်။ ပြင်ဆင်မှုများကို browser local storage တွင်သာ သိမ်းဆည်းပါသည်။</span></div>}
    {error && <ErrorState message={error} retry={() => void load()} />}
    {notice && <div className="toast-note" role="status"><CheckCircle2 size={17} />{notice}</div>}
    {!isDemoMode() && <nav className="editor-step-nav" aria-label="ပုံပြင်ပြင်ဆင်မှု အဆင့်များ">{[["basic", "Basic Information"], ["content", "Story Content"], ["image", "Image (Optional)"], ["audio", "Audio"], ["review", "Review & Publish"]].map(([id, label], index) => <button className={editorStep === id ? "active" : ""} aria-pressed={editorStep === id} onClick={() => setEditorStep(id)} key={id}><span>{index + 1}</span>{label}</button>)}</nav>}
    <div className="editor-step-content">
    {!isDemoMode() && editorStep === "basic" && <section className="editor-basic-summary"><span className="eyebrow">STORY INFORMATION</span><h3>{detail.production.myanmar_title || detail.story.original_title}</h3><dl><div><dt>ပရိသတ်</dt><dd>{burmeseCategory[detail.story.category]}</dd></div><div><dt>စာသားစစ်ဆေးချက်</dt><dd>{detail.production.content_review_status}</dd></div><div><dt>ပုံ</dt><dd>{detail.production.cover_image_url ? "ထည့်ပြီး" : "မပါဝင် · ရွေးချယ်စရာ"}</dd></div><div><dt>အသံ</dt><dd>{detail.production.audio_url ? detail.production.audio_status === "READY" ? "အတည်ပြုပြီး" : "နားထောင်စစ်ရန်" : "မထုတ်ရသေး"}</dd></div></dl><p>စာသား၊ ပုံ၊ အသံနှင့် ထုတ်ဝေမှုကို ဘေးရှိ အဆင့်များမှ သီးခြားစီ ပြင်ဆင်နိုင်ပါသည်။</p><button className="button button-primary" onClick={() => setEditorStep("content")}>စာသားပြင်ဆင်ရန် <ArrowRight size={16} /></button></section>}
    {detail.production.episode_partition_rebuilt === "YES" && <p role="status">AI ပေးသော အပိုင်းစာသားများ မကိုက်ညီသဖြင့် ပုံပြင်အပြည့်မှ အပိုင်းပြန်ခွဲထားပါသည်။ စာသားနှင့် အပိုင်းခေါင်းစဉ်များကို လူက ပြန်စစ်ပါ။</p>}
    <details className="source-review"><summary>ရင်းမြစ်နှင့် အခွင့်အရေး အချက်အလက်</summary><div className="source-review-grid"><div><span>Audience</span><strong>{burmeseCategory[detail.story.category] || "အမျိုးအစား မသတ်မှတ်ရသေး"}</strong></div><div><span>License</span><StatusBadge value={detail.story.license_status || "NEEDS_REVIEW"} /></div><div><span>Rights</span><StatusBadge value={detail.story.rights_cleared || "NO"} /></div><div><span>Reviewer</span><strong>{detail.story.human_reviewer || "မရှိသေး"}</strong></div></div><p>{detail.story.license_evidence || "အထောက်အထား မထည့်ရသေးပါ"} · {detail.story.rights_jurisdiction || "jurisdiction မသတ်မှတ်ရသေး"}</p>{detail.story.source_text && <details className="private-source"><summary>Admin-only source text</summary><pre>{detail.story.source_text}</pre></details>}</details>
    <div hidden={!isDemoMode() && editorStep !== "audio"}>{!isDemoMode() && <StoryAudioPanel storyId={storyId} csrf={csrfToken} refreshKey={`${detail.production.content_review_status}:${detail.story.permission_for_audio}`} defaultReviewer={detail.story.original_reviewer || ""} onReviewed={(status) => {
      // အသံစစ်ဆေးချက်ကိုသာ ပြောင်း၍ မသိမ်းရသေးသော စာသားပြင်ဆင်မှုများကို ထိန်းထားသည်။
      setDetail((current) => current ? { ...current, production: { ...current.production, audio_status: status, approval_status: "" } } : current);
      onUpdated();
    }} />}</div>
    <div hidden={!isDemoMode() && editorStep !== "image"}>{!isDemoMode() && <ImageManager storyId={storyId} csrf={csrfToken} imageUrl={detail.production.cover_image_url || ""} onChanged={(url) => {
      setDetail((current) => current ? { ...current, production: { ...current.production, cover_image_url: url } } : current);
      onUpdated();
    }} />}</div>
    <form hidden={!isDemoMode() && editorStep !== "content"} onSubmit={(event) => void save(event)}>
      <label className="editor-field">မြန်မာခေါင်းစဉ်<input value={detail.production.myanmar_title || ""} onChange={(event) => updateProduction("myanmar_title", event.target.value)} required /></label>
      <label className="editor-field">မြန်မာပုံပြင်<textarea className="story-textarea" value={detail.production.myanmar_story || ""} onChange={(event) => updateProduction("myanmar_story", event.target.value)} required /></label>
      <div className="editor-subhead"><div><span className="eyebrow">EPISODE SEQUENCE</span><h3>အပိုင်းများ</h3></div><button className="small-link" type="button" onClick={() => setDetail({ ...detail, episodes: [...detail.episodes, { episode_number: detail.episodes.length + 1, title: "", content: "" }] })}>+ အပိုင်းထည့်ရန်</button></div>
      {detail.episodes.map((episode, index) => <fieldset className="episode-editor" key={index}><legend>အပိုင်း {index + 1}</legend><div className="episode-editor-title"><label className="editor-field">ခေါင်းစဉ်<input value={episode.title} onChange={(event) => updateEpisode(index, "title", event.target.value)} required /></label><button className="remove-button" type="button" disabled={detail.episodes.length === 1} onClick={() => setDetail({ ...detail, episodes: detail.episodes.filter((_, episodeIndex) => episodeIndex !== index).map((item, episodeIndex) => ({ ...item, episode_number: episodeIndex + 1 })) })}>ဖယ်ရှားရန်</button></div><label className="editor-field">စာသား<textarea value={episode.content} onChange={(event) => setEpisodeContent(index, event.target.value)} required /></label></fieldset>)}
      <div className="editor-subhead"><div><span className="eyebrow">LEARNING MOMENTS</span><h3>Quiz မေးခွန်းများ</h3></div><button className="small-link" type="button" onClick={() => setDetail({ ...detail, quiz: [...detail.quiz, { question: "", answer: "" }] })}>+ မေးခွန်းထည့်ရန်</button></div>
      {detail.quiz.map((item, index) => <div className="quiz-editor" key={index}><label className="editor-field">မေးခွန်း<input value={item.question} onChange={(event) => updateQuiz(index, "question", event.target.value)} required /></label><label className="editor-field">အဖြေ<input value={item.answer} onChange={(event) => updateQuiz(index, "answer", event.target.value)} required /></label><button className="remove-button" type="button" disabled={detail.quiz.length === 1} onClick={() => setDetail({ ...detail, quiz: detail.quiz.filter((_, itemIndex) => itemIndex !== index) })}>ဖယ်ရှားရန်</button></div>)}
      <label className="editor-field">စဉ်းစားရန်<textarea value={Array.isArray(detail.reflection) ? detail.reflection.join("\n") : detail.reflection} onChange={(event) => setDetail({ ...detail, reflection: event.target.value })} required /></label>
      {isDemoMode() && <DemoAudioPlayer compact title={`${detail.production.myanmar_title || "Myanmar story"} · UI preview`} onNotice={setNotice} />}
      <div className="editor-actions"><button className="button button-primary" disabled={busy}>{busy ? "လုပ်ဆောင်နေသည်…" : isDemoMode() ? "Demo ပြင်ဆင်မှု သိမ်းရန်" : "မူကြမ်း သိမ်းဆည်းရန်"}</button><button className="button button-approve" type="button" disabled={busy} onClick={() => void review("approve")}>{isDemoMode() ? "Demo content approve" : "အကြောင်းအရာ အတည်ပြုရန်"}</button><button className="button button-reject" type="button" disabled={busy} onClick={() => void review("reject")}>{isDemoMode() ? "Demo reject" : "မူကြမ်း ပယ်ချရန်"}</button></div>
      <p className="editor-safety"><ShieldCheck size={15} /> Content approval သည် publication approval မဟုတ်ပါ။ ထုတ်ဝေရန် သီးခြားလူအတည်ပြုချက် လိုသည်။</p>
    </form>
    <div hidden={!isDemoMode() && editorStep !== "review"}>{!isDemoMode() && <MvpStoryActions storyId={storyId} csrf={csrfToken} detail={detail} refresh={async () => { await load(); onUpdated(); }} />}</div>
    </div>
    {!isDemoMode() && <aside className="editor-info-rail"><img src={detail.production.cover_image_url || defaultStoryArt} alt="ပုံပြင် အကြိုကြည့်ရန်" /><h3>Story Information</h3><p>{detail.production.myanmar_title || detail.story.original_title}</p><span className="management-status stage-draft">{detail.production.content_review_status}</span><dl><div><dt>ပရိသတ်</dt><dd>{burmeseCategory[detail.story.category]}</dd></div><div><dt>Image Status</dt><dd>{detail.production.cover_image_url ? "✓ Has Image" : "Optional"}</dd></div><div><dt>Audio</dt><dd>{detail.production.audio_status || "NOT_READY"}</dd></div></dl><button className="button button-primary" onClick={() => setEditorStep("review")}>Review & Publish <ArrowRight size={16} /></button></aside>}
  </section>;
}

function Metric({ icon, label, count, color }: { icon: ReactNode; label: string; count: number; color: string }) {
  return <article className="metric-card"><span className={`metric-icon ${color}`}>{icon}</span><span className="metric-label">{label}</span><strong>{count.toLocaleString("my-MM")}</strong><span className="metric-foot">ယခုအခြေအနေ</span></article>;
}

function StoryRow({ story, onSelect }: { story: AdminStory; onSelect: () => void }) {
  return <tr className="clickable-row" onClick={onSelect} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") onSelect(); }}><td><span className="story-cell-title">{story.title || story.story_id}</span><small>{story.story_id}</small></td><td>{burmeseCategory[story.category] ?? "အမျိုးအစား မသတ်မှတ်ရသေး"}</td><td><StatusBadge value={story.license_status || "REVIEW_REQUIRED"} /></td><td><StatusBadge value={story.review_status || "PENDING_REVIEW"} /></td><td><StatusBadge value={story.processing_status || "NOT_QUEUED"} />{story.processing_error && <small className="error-detail">{story.processing_error}</small>}</td><td><ChevronRight size={15} /></td></tr>;
}

function PipelineChart({ counts }: { counts: Overview["counts"] }) {
  const total = Math.max(1, counts.stories);
  const stages = [
    { label: "အခွင့်အရေး စစ်ဆေးရန်", value: counts.rights_review, color: "bar-amber" },
    { label: "မူကြမ်း စစ်ဆေးရန်", value: counts.content_review, color: "bar-violet" },
    { label: "ထုတ်ဝေပြီး", value: counts.published, color: "bar-green" },
  ];
  return <div className="pipeline-chart">{stages.map((stage) => <div className="pipeline-row" key={stage.label}><div className="pipeline-label"><span>{stage.label}</span><strong>{stage.value}</strong></div><div className="progress-track" role="progressbar" aria-label={stage.label} aria-valuenow={stage.value} aria-valuemin={0} aria-valuemax={total}><span className={stage.color} style={{ width: `${Math.min(100, stage.value / total * 100)}%` }} /></div></div>)}<div className="chart-foot"><span>စာကြည့်တိုက် စုစုပေါင်း</span><strong>{counts.stories.toLocaleString("my-MM")} ခု</strong></div></div>;
}

function QueuePreview({ stories }: { stories: AdminStory[] }) {
  const queue = stories.filter((story) => ["QUEUED", "GENERATING"].includes(story.processing_status)).slice(0, 4);
  return queue.length ? <div className="queue-preview">{queue.map((story) => <div className="queue-preview-row" key={story.story_id}><span className="job-pulse" /><div><strong>{story.title || story.story_id}</strong><small>{burmeseCategory[story.category] ?? "အမျိုးအစား မသတ်မှတ်ရသေး"}</small></div><StatusBadge value={story.processing_status} /></div>)}</div> : <div className="compact-empty"><Workflow size={20} /><span>တန်းစီထားသော အလုပ် မရှိသေးပါ</span></div>;
}

function JobTimeline({ jobs, expanded = false }: { jobs: JobStatus; expanded?: boolean }) {
  const history = jobs.history.slice(0, expanded ? 30 : 5);
  return <><div className="panel-heading"><div><span className="eyebrow">AGENT ACTIVITY</span><h2>Workflow လုပ်ဆောင်မှုများ</h2></div><span className="panel-icon"><Clock3 size={18} /></span></div>{jobs.active.length ? <div className="job-list">{jobs.active.map((job) => <div className="job-row" key={job.story_id}><span className="job-pulse" /><div><strong>{job.story_id}</strong><small>{job.updated_at || "အခြေအနေ စောင့်ကြည့်နေသည်"}</small></div><StatusBadge value={job.status} />{job.error && <span className="job-error">{job.error}</span>}</div>)}</div> : <p className="quiet-line">လက်ရှိ လုပ်ဆောင်နေသော agent အလုပ် မရှိပါ။</p>}{history.length > 0 && <div className="history-list">{history.map((job) => <div className="history-row" key={job.processing_id}><span>{job.story_id}</span><StatusBadge value={job.status} /><small>{job.completed_at || job.started_at} · retry {job.retry_count}</small>{job.error_details && <span className="job-error">{job.error_details}</span>}</div>)}</div>}<div className="dispatch-note"><ShieldCheck size={17} /><span>ဤနေရာမှ job dispatch မလုပ်ပါ။ {jobs.dispatch_configured ? "လက်ရှိ dispatch status ကိုပြသနေသည်။" : "GitHub Actions dispatch မချိတ်ဆက်ရသေးပါ။"}</span></div></>;
}

function StoryDetailDrawer({ story, onClose, onEdit }: { story: AdminStory; onClose: () => void; onEdit: () => void }) {
  const safeSourceUrl = /^https?:\/\//i.test(story.source_url);
  return <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><aside className="story-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title"><div className="drawer-heading"><div><span className="eyebrow">STORY REVIEW</span><h2 id="drawer-title">{story.title || story.story_id}</h2></div><button className="icon-button" onClick={onClose} aria-label="ပိတ်ရန်"><XCircle size={18} /></button></div><div className="drawer-section"><span className="drawer-label">အမျိုးအစားနှင့် အထောက်အထား</span><p>{burmeseCategory[story.category] ?? "အမျိုးအစား မသတ်မှတ်ရသေး"}</p><small>{story.category_evidence || "အမျိုးအစားအထောက်အထား မရှိသေးပါ"}</small></div><div className="drawer-section"><span className="drawer-label">မူရင်းရင်းမြစ်</span><p>{story.source_name || "ရင်းမြစ် မဖော်ပြထားပါ"}</p>{safeSourceUrl && <a className="text-link" href={story.source_url} target="_blank" rel="noopener noreferrer">ရင်းမြစ်ကို ကြည့်ရန် <ArrowRight size={13} /></a>}</div><div className="drawer-section"><span className="drawer-label">အခွင့်အရေး သုံးသပ်ချက်</span><p>အခြေအနေ <StatusBadge value={story.license_status || "NEEDS_REVIEW"} /></p><small>{story.license_evidence || "လိုင်စင်အထောက်အထား မထည့်ရသေးပါ"}</small><p>စီရင်ပိုင်ခွင့်: {story.rights_jurisdiction || "မသတ်မှတ်ရသေး"}</p><p>ပြန်လည်သုံးသပ်သူ: {story.human_reviewer || "မသတ်မှတ်ရသေး"}</p><p>အခွင့်အရေးရှင်းလင်းမှု: <StatusBadge value={story.rights_cleared} /></p></div><div className="drawer-section"><span className="drawer-label">Agent အခြေအနေ</span><StatusBadge value={story.processing_status} />{story.processing_error && <p className="job-error">{story.processing_error}</p>}</div><button className="button button-primary drawer-edit" onClick={onEdit}>မူကြမ်း workspace ဖွင့်ရန် <ArrowRight size={15} /></button><div className="drawer-safety"><ShieldCheck size={17} /><span>ရင်းမြစ်အခွင့်အရေးနှင့် အမျိုးအစားကို အလိုအလျောက် အတည်မပြုပါ။ Content approval သည် publication approval မဟုတ်ပါ။</span></div></aside></div>;
}

function RouteMotion() {
  const { pathname } = useLocation();

  useEffect(() => {
    if (
      (typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches)
      || !("IntersectionObserver" in window)
    ) return;

    const elements = Array.from(document.querySelectorAll<HTMLElement>(
      ".public-site .section-block, .public-site .reader-note, .public-site .story-card, .public-site .story-reading, .admin-main .admin-panel, .admin-main .metric-card, .admin-main .demo-notice, .admin-main .candidate-card, .admin-main .review-card, .admin-main .episode-manager-card, .admin-main .audio-player",
    ));
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        (entry.target as HTMLElement).dataset.motionReveal = "visible";
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.04, rootMargin: "0px 0px -6% 0px" });

    elements.forEach((element, index) => {
      element.style.setProperty("--motion-order", String(index % 5));
      element.dataset.motionReveal = "pending";
      observer.observe(element);
    });

    return () => {
      observer.disconnect();
      elements.forEach((element) => {
        delete element.dataset.motionReveal;
        element.style.removeProperty("--motion-order");
      });
    };
  }, [pathname]);

  return null;
}

function App() {
  return <><RouteMotion /><Routes><Route path="/" element={<HomePage />} /><Route path="/stories" element={<LibraryPage />} /><Route path="/stories/:storyId" element={<StoryPage />} /><Route path="/library" element={<LibraryPage />} /><Route path="/story/:storyId" element={<StoryPage />} /><Route path="/admin/*" element={<AdminPage />} /><Route path="*" element={<HomePage />} /></Routes></>;
}

export default App;
