import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { demoOverview } from "./demo";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("PyonPyin frontend", () => {
  it("preserves unsaved live story text while switching between content and optional image steps", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      const payload = path === "/api/admin/overview" ? { ...demoOverview, csrf_token: "csrf", stories: [] }
        : path === "/api/admin/jobs" ? { active: [], history: [], publishing_history: [] }
        : path === "/api/admin/settings" ? { storage: "sqlite", local_jobs: true }
        : path === "/api/admin/audio" ? []
        : path === "/api/admin/story/live-story" ? { story: { original_title: "Live title", category: "CHILDREN" }, production: { draft_mode: "ORIGINAL_THEME", myanmar_title: "Live title", myanmar_story: "Saved story", content_review_status: "PENDING" }, episodes: [{ episode_number: 1, title: "One", content: "Saved story" }], quiz: [], reflection: "" }
        : [];
      return { ok: true, json: async () => payload };
    }));
    render(<MemoryRouter initialEntries={["/admin/stories/live-story"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Story Content/ }));
    fireEvent.change(screen.getByLabelText("မြန်မာပုံပြင်"), { target: { value: "Unsaved edit" } });
    fireEvent.click(screen.getByRole("button", { name: /Image \(Optional\)/ }));
    expect(screen.getByLabelText("ပုံဖိုင် ရွေးရန်")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Story Content/ }));
    expect(screen.getByLabelText("မြန်မာပုံပြင်")).toHaveValue("Unsaved edit");
  });

  it("shows a failed public request and allows retry instead of staying in loading", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error("Temporary outage")).mockResolvedValue({
      ok: true, json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/stories"]}><App /></MemoryRouter>);
    expect(await screen.findByText("Temporary outage")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ပြန်ကြိုးစားရန်" }));
    expect(await screen.findByText("ပုံပြင်များ မရှိသေးပါ")).toBeInTheDocument();
  });

  it("renders a nonempty production queue without accessing uninitialized story state", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/production"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Story Production queue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run selected story" })).toBeDisabled();
  });

  it("creates an original workspace from the live production page and opens its editor", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      let payload: unknown = {};
      if (path === "/api/admin/overview") payload = { ...demoOverview, csrf_token: "live-csrf", stories: [] };
      else if (path === "/api/admin/jobs") payload = { active: [], history: [], publishing_history: [], dispatch_configured: false };
      else if (path === "/api/admin/settings") payload = { local_jobs: true, storage: "sqlite" };
      else if (path === "/api/admin/local-jobs") payload = [];
      else if (path === "/api/admin/stories") {
        expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("live-csrf");
        expect(JSON.parse(String(init?.body)).title).toBe("New original");
        payload = { story_id: "new-original" };
      } else if (path === "/api/admin/story/new-original") payload = {
        story: { original_title: "New original", category: "CHILDREN" },
        production: { draft_mode: "ORIGINAL_THEME", myanmar_story: "" }, episodes: [], quiz: [], reflection: "",
      };
      return { ok: true, json: async () => payload };
    }));
    render(<MemoryRouter initialEntries={["/admin/production"]}><App /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText("အလုပ်ခေါင်းစဉ်"), { target: { value: "New original" } });
    fireEvent.click(screen.getByRole("button", { name: "Workspace ဖန်တီးရန်" }));
    expect(await screen.findByRole("heading", { name: "AI မူကြမ်း စတင်ရန်" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI မူကြမ်း job စတင်ရန်" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ထုတ်ဝေမည်" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("မြန်မာပုံပြင်")).not.toBeInTheDocument();
  });

  it("explains an unclassified discovery without displaying an unusable editor or generation action", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      let payload: unknown = {};
      if (path === "/api/admin/overview") payload = { ...demoOverview, csrf_token: "csrf", stories: [] };
      else if (path === "/api/admin/jobs") payload = { active: [], history: [], publishing_history: [], dispatch_configured: false };
      else if (path === "/api/admin/story/discovered-source") payload = {
        story: { original_title: "Discovered book", category: "UNCLASSIFIED", source_name: "Standard Ebooks" },
        production: { processing_status: "", draft_mode: "", myanmar_story: "" },
        episodes: [], quiz: [], reflection: "",
      };
      return { ok: true, json: async () => payload };
    }));
    render(<MemoryRouter initialEntries={["/admin/stories/discovered-source"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "မူကြမ်း မစတင်ရသေးပါ" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /AI ပုံပြင်အသစ် ဖန်တီးရန်/ })).toHaveAttribute("href", "/admin/production");
    expect(screen.queryByRole("button", { name: "AI မူကြမ်း job စတင်ရန်" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("မြန်မာပုံပြင်")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ထုတ်ဝေမည်" })).not.toBeInTheDocument();
  });
  it("labels admin fixtures as demo data and exposes no publish action", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin"]}><App /></MemoryRouter>);
    expect(await screen.findByText(/Demo preview/)).toBeInTheDocument();
    expect(screen.getByText(/DEMO DATA/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Workflow လုပ်ဆောင်မှုများ" })).toBeInTheDocument();
    expect(screen.getByText("ထုတ်ဝေမှု ပိတ်ထားသည်")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve.*publish|publish story|ထုတ်ဝေမည်/i })).not.toBeInTheDocument();
  });

  it("shows clearly labeled demo samples rather than presenting fixtures as published stories", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/stories"]}><App /></MemoryRouter>);
    expect(await screen.findByText(/DEMO နမူနာများသာ/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "လမင်းရောင်ကန်ကလေး" })).toBeInTheDocument();
    expect(screen.getAllByText("DEMO")).toHaveLength(3);
    expect(screen.queryByText(/စစ်ဆေးပြီး ထုတ်ဝေထားသော ပုံပြင်များသာ/)).not.toBeInTheDocument();
  });

  it("updates the public category filter without displaying unknown categories", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }));
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/stories"]}><App /></MemoryRouter>);
    const categoryFilters = screen.getByLabelText("အမျိုးအစား စစ်ထုတ်ရန်");
    const childrenFilter = within(categoryFilters).getByRole("button", { name: "ကလေးများ" });
    fireEvent.click(childrenFilter);
    expect(childrenFilter).toHaveClass("selected");
    expect(screen.queryByRole("heading", { name: "စက္ကူလှေနှင့် အိမ်ပြန်လမ်း" })).not.toBeInTheDocument();
  });

  it("opens a demo story detail with reading, quiz, reflection, and a clearly synthetic audio preview", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/stories/demo-moonlit-lake"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "လမင်းရောင်ကန်ကလေး" })).toBeInTheDocument();
    expect(screen.getByText(/DEMO SAMPLE · NOT PUBLISHED/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC UI DEMO · NOT NARRATION/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ပုံပြင်နားလည်မှု" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "စဉ်းစားကြည့်ရန်" })).toBeInTheDocument();
  });

  it("renders the demo Audio Studio with selectable tracks and usable player controls", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/audio"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Audio library" })).toBeInTheDocument();
    expect(screen.getByText(/PROVIDER NOT CONFIGURED/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /မိုးစက်တို့ရဲ့ သစ်ပင်/ }));
    expect(screen.getByRole("heading", { name: "မိုးစက်တို့ရဲ့ သစ်ပင်" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Demo audio seek" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Demo audio volume" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Demo playback speed" }), { target: { value: "1.25" } });
    expect(screen.getByRole("combobox", { name: "Demo playback speed" })).toHaveValue("1.25");
  });

  it("plays and pauses an explicitly synthetic audio preview through the Web Audio API", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const start = vi.fn();
    const stop = vi.fn();
    vi.stubGlobal("AudioContext", class {
      currentTime = 0;
      destination = {};
      resume = vi.fn().mockResolvedValue(undefined);
      close = vi.fn().mockResolvedValue(undefined);
      createOscillator = () => ({
        type: "sine",
        frequency: { value: 0 },
        connect: vi.fn(),
        start,
        stop,
        disconnect: vi.fn(),
      });
      createGain = () => ({
        gain: { value: 0, setTargetAtTime: vi.fn() },
        connect: vi.fn(),
        disconnect: vi.fn(),
      });
    });
    render(<MemoryRouter initialEntries={["/admin/audio"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Play demo audio" }));
    expect(await screen.findByRole("button", { name: "Pause demo audio" })).toBeInTheDocument();
    expect(start).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Pause demo audio" }));
    expect(await screen.findByRole("button", { name: "Play demo audio" })).toBeInTheDocument();
    expect(stop).toHaveBeenCalledOnce();
  });

  it("simulates finder and review actions without calling services or enabling publication", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/finder"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Story Finder", level: 2 })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Run demo scan/ }));
    expect(await screen.findByText(/no feeds, Sheets, or external services were contacted/)).toBeInTheDocument();
    expect(screen.getByText("ထုတ်ဝေမှု ပိတ်ထားသည်")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(publish|publish story|publish now|ထုတ်ဝေမည်)$/i })).not.toBeInTheDocument();
  });

  it("keeps demo review decisions local and separate from source rights", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/review"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Draft review queue" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Demo approve content" })[0]);
    expect(await screen.findByRole("status")).toHaveTextContent(/in this browser only/);
    expect(screen.getAllByText(/Rights: NEEDS_REVIEW · Audience: UNCLASSIFIED/).length).toBeGreaterThan(0);
    const reviewState = JSON.parse(window.localStorage.getItem("pyonpyin-demo-review-status") ?? "{}");
    expect(Object.values(reviewState)).toContain("APPROVED");
    expect(screen.getByText("ထုတ်ဝေမှု ပိတ်ထားသည်")).toBeInTheDocument();
  });

  it("navigates to rights and episode management without auto-clearing rights", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/rights"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Rights review is required" })).toBeInTheDocument();
    expect(screen.getByText("NO AUTO-CLEARANCE")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Episode Manager" }));
    expect(await screen.findByRole("heading", { name: "Episode manager" })).toBeInTheDocument();
    expect(await screen.findAllByText("နမူနာအပိုင်း")).not.toHaveLength(0);
    fireEvent.click(screen.getAllByRole("button", { name: "Open editor" })[0]);
    expect(await screen.findByLabelText("မြန်မာခေါင်းစဉ်")).toBeInTheDocument();
  });

  it("loads episode records from the authenticated API outside demo mode", async () => {
    const story = {
      story_id: "server-story",
      title: "Server story",
      category: "CHILDREN",
      license_status: "NEEDS_REVIEW",
      review_status: "PENDING",
      processing_status: "DRAFT_READY",
      processing_error: "",
      audio_status: "NOT_READY",
      published: false,
      source_name: "Test source",
      source_url: "",
      license_evidence: "",
      rights_jurisdiction: "",
      rights_cleared: "NO",
      human_reviewer: "",
      category_evidence: "",
    };
    const detail = {
      story: { category: "CHILDREN" },
      production: {},
      episodes: [{ episode_number: 1, title: "Live API episode", content: "Server content" }],
      quiz: [],
      reflection: "",
    };
    let loggedIn = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      let body: unknown;
      let status = 200;
      if (path === "/api/admin/login") {
        loggedIn = true;
        body = { csrf_token: "test-csrf" };
      } else if (!loggedIn) {
        status = 401;
        body = { error: "Authentication required." };
      }
      else if (path === "/api/admin/overview") body = {
        csrf_token: "test-csrf",
        counts: { stories: 1, pending_review: 1, rights_review: 1, content_review: 1, approved: 0, drafts: 1, audio_ready: 0, published: 0 },
        stories: [story],
      };
      else if (path === "/api/admin/jobs") body = { active: [], history: [], publishing_history: [], dispatch_configured: false };
      else if (path === "/api/admin/story/server-story") body = detail;
      else {
        status = 401;
        body = { error: "Authentication required." };
      }
      return { ok: status === 200, status, json: async () => body };
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("VITE_DEMO_MODE", "false");
    render(<MemoryRouter initialEntries={["/admin/episodes"]}><App /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText("စီမံခန့်ခွဲသူ စကားဝှက်"), { target: { value: "not-a-real-password" } });
    fireEvent.click(screen.getByRole("button", { name: /လုံခြုံစွာ ဝင်ရောက်ရန်/ }));
    expect(await screen.findByText("Live API episode")).toBeInTheDocument();
    expect(screen.getByText(/SERVER RECORD/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/admin/story/server-story", expect.objectContaining({ credentials: "same-origin" }));
  });

  it("saves draft edits to browser-local demo state and keeps review distinct from publishing", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    render(<MemoryRouter initialEntries={["/admin/stories/demo-story-002"]}><App /></MemoryRouter>);
    const title = await screen.findByLabelText("မြန်မာခေါင်းစဉ်");
    fireEvent.change(title, { target: { value: "သိမ်းထားသော နမူနာခေါင်းစဉ်" } });
    fireEvent.click(screen.getByRole("button", { name: "Demo ပြင်ဆင်မှု သိမ်းရန်" }));
    expect(await screen.findByText(/ဤဘရောက်ဇာတွင်သာ သိမ်းထားသည်/)).toBeInTheDocument();
    const saved = JSON.parse(window.localStorage.getItem("pyonpyin-demo-detail:demo-story-002") ?? "{}");
    expect(saved.production.myanmar_title).toBe("သိမ်းထားသော နမူနာခေါင်းစဉ်");
    expect(saved.production.approval_status).toBe("");
    expect(screen.getByText("ထုတ်ဝေမှု ပိတ်ထားသည်")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(publish|publish story|ထုတ်ဝေမည်)$/i })).not.toBeInTheDocument();
  });
});
