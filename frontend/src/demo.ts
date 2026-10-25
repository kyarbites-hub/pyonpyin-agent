import type { AdminStory, AdminStoryDetail, JobStatus, Overview, PublicStory } from "./api";

export const demoPublicStories: PublicStory[] = [
  {
    story_id: "demo-moonlit-lake",
    category: "CHILDREN",
    title: "လမင်းရောင်ကန်ကလေး",
    story: "မိုးရွာပြီးနောက် တောင်ကုန်းလေးတစ်ခုအောက်မှာ ရေကန်ပြာပြာလေး ပေါ်လာတယ်။ မေသွယ်က ရေထဲက လရောင်ကို ကြည့်ပြီး လမ်းပျောက်နေတဲ့ ပိုးစုန်းကြူးလေးကို အိမ်ပြန်လမ်း ရှာပေးခဲ့တယ်။ နှစ်ယောက်သား ရေကန်ဘေးက ပန်းရိုင်းလမ်းကို လျှောက်ရင်း ကြယ်တွေကို ရေတွက်ကြတယ်။ နောက်ဆုံးမှာ ပိုးစုန်းကြူးလေးက သူ့မီးရောင်နဲ့ မေသွယ်ကို အိမ်ပြန်လမ်း ပြပေးခဲ့တယ်။",
    episodes: [{ episode_number: 1, title: "ရေကန်ဘေးက မိတ်ဆွေ", content: "မိုးရွာပြီးနောက် တောင်ကုန်းလေးတစ်ခုအောက်မှာ ရေကန်ပြာပြာလေး ပေါ်လာတယ်။ မေသွယ်က ရေထဲက လရောင်ကို ကြည့်ပြီး လမ်းပျောက်နေတဲ့ ပိုးစုန်းကြူးလေးကို အိမ်ပြန်လမ်း ရှာပေးခဲ့တယ်။ နှစ်ယောက်သား ရေကန်ဘေးက ပန်းရိုင်းလမ်းကို လျှောက်ရင်း ကြယ်တွေကို ရေတွက်ကြတယ်။ နောက်ဆုံးမှာ ပိုးစုန်းကြူးလေးက သူ့မီးရောင်နဲ့ မေသွယ်ကို အိမ်ပြန်လမ်း ပြပေးခဲ့တယ်။" }],
    audio_url: "",
    reading_minutes: 3,
    quiz: [{ question: "မေသွယ်က ဘယ်သူ့ကို ကူညီခဲ့သလဲ။", answer: "လမ်းပျောက်နေတဲ့ ပိုးစုန်းကြူးလေးကို ကူညီခဲ့တယ်။" }],
    reflection: "မိတ်ဆွေတစ်ယောက်ကို ကူညီပေးခဲ့ဖူးတဲ့ အချိန်ကို စဉ်းစားကြည့်ပါ။",
    demo_sample: true,
  },
  {
    story_id: "demo-rain-tree",
    category: "CHILDREN",
    title: "မိုးစက်တို့ရဲ့ သစ်ပင်",
    story: "ရွာလေးရဲ့ အလယ်မှာ အရွက်မရှိတော့တဲ့ သစ်ပင်အိုကြီးတစ်ပင် ရှိတယ်။ ကလေးတွေက ရေခွက်လေးတွေယူလာပြီး နေ့တိုင်း ရေလောင်းကြတယ်။ တစ်ညမှာ မိုးစက်တွေက သစ်ကိုင်းတွေကို တီးခတ်ပြီး သီချင်းဆိုသလို ဖြစ်လာတယ်။ မနက်ရောက်တော့ အစိမ်းရောင်အဖူးလေးတွေ ပွင့်လာပြီး ရွာသားအားလုံး အတူတူ သစ်ပင်ကို စောင့်ရှောက်ကြတယ်။",
    episodes: [{ episode_number: 1, title: "အဖူးလေးတစ်ဖူး", content: "ရွာလေးရဲ့ အလယ်မှာ အရွက်မရှိတော့တဲ့ သစ်ပင်အိုကြီးတစ်ပင် ရှိတယ်။ ကလေးတွေက ရေခွက်လေးတွေယူလာပြီး နေ့တိုင်း ရေလောင်းကြတယ်။ တစ်ညမှာ မိုးစက်တွေက သစ်ကိုင်းတွေကို တီးခတ်ပြီး သီချင်းဆိုသလို ဖြစ်လာတယ်။ မနက်ရောက်တော့ အစိမ်းရောင်အဖူးလေးတွေ ပွင့်လာပြီး ရွာသားအားလုံး အတူတူ သစ်ပင်ကို စောင့်ရှောက်ကြတယ်။" }],
    audio_url: "",
    reading_minutes: 4,
    quiz: [{ question: "ကလေးတွေက သစ်ပင်အတွက် ဘာလုပ်ပေးခဲ့သလဲ။", answer: "နေ့တိုင်း ရေလောင်းပေးခဲ့တယ်။" }],
    reflection: "ကိုယ့်ပတ်ဝန်းကျင်ကို စောင့်ရှောက်ဖို့ ဘာလုပ်နိုင်မလဲ။",
    demo_sample: true,
  },
  {
    story_id: "demo-paper-boat",
    category: "ADULT",
    title: "စက္ကူလှေနှင့် အိမ်ပြန်လမ်း",
    story: "မြို့သစ်တစ်မြို့မှာ နေထိုင်လာတာ ဆယ်နှစ်ပြည့်တဲ့ညမှာ ကိုထက်က မိုးရေထဲ စက္ကူလှေတစ်စင်း လွှတ်လိုက်တယ်။ လှေပေါ်မှာ ရေးထားတာက သူ့အမေ သင်ပေးခဲ့တဲ့ စကားတစ်ခွန်းပဲ။ အိမ်ပြန်လမ်းဆိုတာ နေရာတစ်ခုတည်း မဟုတ်ဘူး၊ ကိုယ့်ကို နားထောင်ပေးတဲ့သူရှိတဲ့ နေရာလည်း ဖြစ်နိုင်တယ်။ လှေက ရေမြောင်းထဲကွေ့ဝင်သွားချိန်မှာ သူ့ဖုန်းမြည်လာတယ်။ အမေက ညစာအတွက် စောင့်နေတယ်လို့ ပြောတယ်။",
    episodes: [{ episode_number: 1, title: "မိုးညစာ", content: "မြို့သစ်တစ်မြို့မှာ နေထိုင်လာတာ ဆယ်နှစ်ပြည့်တဲ့ညမှာ ကိုထက်က မိုးရေထဲ စက္ကူလှေတစ်စင်း လွှတ်လိုက်တယ်။ လှေပေါ်မှာ ရေးထားတာက သူ့အမေ သင်ပေးခဲ့တဲ့ စကားတစ်ခွန်းပဲ။ အိမ်ပြန်လမ်းဆိုတာ နေရာတစ်ခုတည်း မဟုတ်ဘူး၊ ကိုယ့်ကို နားထောင်ပေးတဲ့သူရှိတဲ့ နေရာလည်း ဖြစ်နိုင်တယ်။ လှေက ရေမြောင်းထဲကွေ့ဝင်သွားချိန်မှာ သူ့ဖုန်းမြည်လာတယ်။ အမေက ညစာအတွက် စောင့်နေတယ်လို့ ပြောတယ်။" }],
    audio_url: "",
    reading_minutes: 5,
    quiz: [{ question: "ကိုထက်အတွက် အိမ်ပြန်လမ်းဆိုတာ ဘာကို ဆိုလိုသလဲ။", answer: "သူ့ကို နားထောင်ပေးတဲ့သူရှိတဲ့ နေရာလို့ တွေးမိတယ်။" }],
    reflection: "သင့်အတွက် 'အိမ်' ဆိုတဲ့ခံစားချက်ကို ဖော်ပြပေးတဲ့ အရာက ဘာလဲ။",
    demo_sample: true,
  },
];

export const demoTracks = [
  { id: "track-moon", storyId: "demo-moonlit-lake", title: "လမင်းရောင်ကန်ကလေး", duration: 74, voice: "သရုပ်ပြသံစဉ်", language: "မြန်မာ UI preview", status: "PREVIEW ONLY", frequency: 220 },
  { id: "track-rain", storyId: "demo-rain-tree", title: "မိုးစက်တို့ရဲ့ သစ်ပင်", duration: 91, voice: "သရုပ်ပြသံစဉ်", language: "မြန်မာ UI preview", status: "NOT GENERATED", frequency: 174 },
  { id: "track-boat", storyId: "demo-paper-boat", title: "စက္ကူလှေနှင့် အိမ်ပြန်လမ်း", duration: 103, voice: "သရုပ်ပြသံစဉ်", language: "မြန်မာ UI preview", status: "NOT GENERATED", frequency: 196 },
];

export const demoOverview: Overview = {
  csrf_token: "",
  counts: {
    stories: 12,
    pending_review: 12,
    rights_review: 12,
    content_review: 4,
    approved: 0,
    drafts: 4,
    audio_ready: 0,
    published: 0,
  },
  stories: [
    {
      story_id: "demo-story-001",
      title: "စိတ်ကူးယဉ် နမူနာပုံပြင်",
      category: "UNCLASSIFIED",
      license_status: "NEEDS_REVIEW",
      review_status: "PENDING_REVIEW",
      processing_status: "NOT_QUEUED",
      processing_error: "",
      audio_status: "NOT_READY",
      published: false,
      source_name: "နမူနာရင်းမြစ်",
      source_url: "",
      license_evidence: "",
      rights_jurisdiction: "",
      rights_cleared: "NO",
      human_reviewer: "",
      category_evidence: "",
    },
    {
      story_id: "demo-story-002",
      title: "နမူနာမူကြမ်း",
      category: "UNCLASSIFIED",
      license_status: "NEEDS_REVIEW",
      review_status: "PENDING_REVIEW",
      processing_status: "DRAFT_READY",
      processing_error: "",
      audio_status: "WAITING",
      published: false,
      source_name: "နမူနာရင်းမြစ်",
      source_url: "",
      license_evidence: "",
      rights_jurisdiction: "",
      rights_cleared: "NO",
      human_reviewer: "",
      category_evidence: "",
    },
    {
      story_id: "demo-story-003",
      title: "ပြန်လည်စစ်ဆေးရန် နမူနာ",
      category: "UNCLASSIFIED",
      license_status: "REVIEWING",
      review_status: "PENDING_REVIEW",
      processing_status: "QUEUED",
      processing_error: "",
      audio_status: "NOT_READY",
      published: false,
      source_name: "နမူနာရင်းမြစ်",
      source_url: "",
      license_evidence: "",
      rights_jurisdiction: "",
      rights_cleared: "NO",
      human_reviewer: "",
      category_evidence: "",
    },
  ],
};

const additionalDemoTitles = [
  "ကြယ်ရောင်လမ်းက နမူနာ",
  "တိမ်ဖြူလေး၏ ခရီး",
  "မြစ်ကမ်းဘေးက မှတ်စု",
  "နံနက်ခင်း ရောင်ခြည်",
  "လေညင်းနှင့် စာမျက်နှာ",
  "သစ်ရွက်ပေါ်က မိုးစက်",
  "တောင်တန်းနောက်က နေဝင်ချိန်",
  "စမ်းချောင်းလေး၏ အသံ",
  "ပန်းရိုင်းလမ်းက အိမ်ကလေး",
];
const additionalDemoStatuses = [
  "HUMAN_EDITING", "DRAFT_READY", "QUEUED", "FAILED", "CONTENT_APPROVED",
  "NOT_QUEUED", "DRAFT_READY", "REJECTED", "GENERATING",
];
demoOverview.stories.push(...additionalDemoTitles.map((title, index) => ({
  story_id: `demo-story-${String(index + 4).padStart(3, "0")}`,
  title,
  category: "UNCLASSIFIED",
  license_status: index % 3 === 0 ? "REVIEWING" : "NEEDS_REVIEW",
  review_status: "PENDING_REVIEW",
  processing_status: additionalDemoStatuses[index],
  processing_error: additionalDemoStatuses[index] === "FAILED" ? "DEMO · simulated provider timeout" : "",
  audio_status: index === 4 ? "WAITING_PROVIDER_VERIFICATION" : "NOT_READY",
  published: false,
  source_name: "နမူနာရင်းမြစ်",
  source_url: "",
  license_evidence: "",
  rights_jurisdiction: "",
  rights_cleared: "NO",
  human_reviewer: "",
  category_evidence: "Demo fixture; audience remains unclassified",
})));

export const demoJobs: JobStatus = {
  active: [
    {
      story_id: "demo-story-003",
      status: "QUEUED",
      error: "",
      updated_at: "DEMO",
    },
  ],
  history: [],
  publishing_history: [],
  dispatch_configured: false,
};

export const demoStoryDetail = {
  story: {
    story_id: "demo-story-002",
    original_title: "Demo fixture — original theme only",
    author: "",
    source_name: "Demo fixture",
    source_url: "",
    source_text: "",
    category: "UNCLASSIFIED",
    category_evidence: "Demo data; no audience classification assigned",
    license_status: "NEEDS_REVIEW",
    license_name: "",
    license_url: "",
    license_evidence: "",
    rights_cleared: "NO",
    rights_jurisdiction: "",
    permission_for_translation: "NO",
    permission_for_ai_processing: "NO",
    permission_for_publication: "NO",
    permission_for_audio: "NO",
    human_reviewer: "",
    review_status: "PENDING_REVIEW",
    rights_mode: "UNKNOWN",
  },
  production: {
    myanmar_title: "နမူနာ မူကြမ်း — သရုပ်ပြရန်သာ",
    myanmar_story: "ဤစာသားသည် ဒီဇိုင်းသရုပ်ပြရန်အတွက် ဖန်တီးထားသော နမူနာသာ ဖြစ်သည်။ ထုတ်ဝေထားသော ပုံပြင်မဟုတ်ပါ။",
    audio_url: "",
    audio_status: "NOT_READY",
    audio_required: "YES",
    processing_status: "DRAFT_READY",
    processing_error: "",
    content_review_status: "PENDING",
    approval_status: "",
    draft_mode: "ORIGINAL_THEME",
  },
  episodes: [{
    episode_number: 1,
    title: "နမူနာအပိုင်း",
    content: "ဤစာသားသည် ဒီဇိုင်းသရုပ်ပြရန်အတွက် ဖန်တီးထားသော နမူနာသာ ဖြစ်သည်။ ထုတ်ဝေထားသော ပုံပြင်မဟုတ်ပါ။",
  }],
  quiz: [{ question: "သရုပ်ပြမေးခွန်း", answer: "နမူနာအဖြေ" }],
  reflection: "ဤနေရာတွင် စဉ်းစားရန် မေးခွန်းကို ရေးပါ။",
};

export function isDemoMode(): boolean {
  // Dev တွင် default demo ဖြစ်သည်။ တကယ့် backend သုံးရန် VITE_DEMO_MODE=false သတ်မှတ်ရသည်။
  return import.meta.env.VITE_DEMO_MODE === "true"
    || (!import.meta.env.VITE_DEMO_MODE && import.meta.env.DEV);
}

export function asDemoStory(story: AdminStory): AdminStory {
  return { ...story, published: false };
}

export function loadDemoStoryDetail(storyId: string): AdminStoryDetail {
  // Demo ပြင်ဆင်မှုကို ဤ browser ၏ localStorage မှသာ ဖတ်သည်။ Sheets မှ ဖတ်ခြင်းမဟုတ်ပါ။
  const saved = window.localStorage.getItem(`pyonpyin-demo-detail:${storyId}`);
  if (saved) return JSON.parse(saved) as AdminStoryDetail;
  return {
    ...demoStoryDetail,
    story: { ...demoStoryDetail.story, story_id: storyId },
  };
}

export function saveDemoStoryDetail(storyId: string, detail: AdminStoryDetail) {
  // Demo data ကို browser ထဲမှာပဲ သိမ်းပြီး server သို့ မပို့ပါ။
  window.localStorage.setItem(`pyonpyin-demo-detail:${storyId}`, JSON.stringify(detail));
}
