export interface Episode {
  episode_number: number;
  title: string;
  content: string;
  audio_url?: string;
  audio_status?: string;
}

export interface PublicStory {
  cover_image_url?: string;
  story_id: string;
  category: "CHILDREN" | "ADULT";
  title: string;
  story: string;
  episodes: Episode[];
  audio_url: string;
  reading_minutes?: number;
  quiz?: Array<{ question: string; answer: string }>;
  reflection?: string;
  demo_sample?: boolean;
}

export interface AdminStory {
  cover_image_url?: string;
  audio_url?: string;
  has_story?: boolean;
  updated_at?: string;
  story_id: string;
  title: string;
  category: string;
  license_status: string;
  review_status: string;
  processing_status: string;
  processing_error: string;
  audio_status: string;
  published: boolean;
  source_name: string;
  source_url: string;
  license_name?: string;
  license_url?: string;
  license_evidence: string;
  rights_jurisdiction: string;
  rights_cleared: string;
  permission_for_translation?: string;
  permission_for_ai_processing?: string;
  permission_for_publication?: string;
  permission_for_audio?: string;
  permission_for_commercial_use?: string;
  human_reviewer: string;
  category_evidence: string;
}

export interface Overview {
  csrf_token: string;
  counts: {
    stories: number;
    pending_review: number;
    rights_review: number;
    content_review: number;
    approved: number;
    drafts: number;
    audio_ready: number;
    published: number;
  };
  stories: AdminStory[];
}

export interface JobHistory {
  processing_id: string;
  story_id: string;
  status: string;
  started_at: string;
  completed_at: string;
  retry_count: string;
  error_details: string;
}

export interface JobStatus {
  active: Array<{
    story_id: string;
    status: string;
    error: string;
    updated_at: string;
  }>;
  history: JobHistory[];
  publishing_history: Array<{
    story_id: string;
    published_title: string;
    website_url: string;
    published_at: string;
    publication_status: string;
    approved_by: string;
  }>;
  dispatch_configured: boolean;
  local_jobs?: boolean;
}

export interface AdminStoryDetail {
  story: Record<string, string>;
  production: Record<string, string>;
  episodes: Episode[];
  quiz: Array<{ question: string; answer: string }>;
  reflection: string | string[];
}

export interface PlatformSettings {
  storage: string;
  local_jobs: boolean;
  gemini_configured: boolean;
  generation_enabled: boolean;
  publishing_enabled: boolean;
  tts_configured: boolean;
  tts_enabled: boolean;
  tts_provider: string;
  voice: string;
  public_base_url_configured: boolean;
}

export interface LocalJob {
  result?: { found: number; duplicates: number; added: number; deferred: number; drafts_queued: number; sources: Array<{ name: string; found: number; errors: string[] }> } | null;
  job_id: string;
  story_id: string;
  kind: string;
  status: string;
  error: string;
  updated_at: string;
}

export interface AudioStory {
  story_id: string;
  title: string;
  audio_url: string;
  audio_status: string;
  content_review_status: string;
  narration_permitted: boolean;
  original_workspace?: boolean;
  updated_at: string;
  job: Pick<LocalJob, "job_id" | "status" | "error"> | null;
}

export interface PublicationRecord {
  publication_id: string; story_id: string; published_title: string; website_url: string;
  published_at: string; publication_status: string; approved_by: string; audio_url: string;
  snapshot_available: boolean;
}
export interface PublicationSnapshot { title: string; story: string; audio_url: string; episodes: Episode[]; category: string; cover_image_url?: string }


const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);

  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...init,
    headers,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: string; blockers?: string[] }
      | null;

    throw new Error([
      payload?.error || `Request failed (${response.status}).`,
      ...(payload?.blockers ?? []),
    ].join(" "));
  }

  return (await response.json()) as T;
}

export const api = {
  site: () => request<{ hero_image_url: string }>("/api/site"),
  uploadImage: (path: string, file: File, csrf: string) => {
    const data = new FormData(); data.append("image", file);
    return request<{ image_url: string }>(path, { method: "POST", headers: { "X-CSRF-Token": csrf }, body: data });
  },
  removeImage: (path: string, csrf: string) => request<{ image_url: string }>(path, { method: "DELETE", headers: { "X-CSRF-Token": csrf } }),
  // Public ဖတ်ရှုမှုနှင့် admin ပြင်ဆင်မှုများအတွက် endpoint စုစည်းရာဖြစ်သည်။ Mutation များတွင် CSRF ပို့သည်။
  stories: () => request<PublicStory[]>("/api/stories"),
  settings: () => request<PlatformSettings>("/api/admin/settings"),
  audio: () => request<AudioStory[]>("/api/admin/audio"),
  publications: () => request<PublicationRecord[]>("/api/admin/publications"),
  publication: (id: string) => request<PublicationSnapshot>(`/api/admin/publications/${encodeURIComponent(id)}`),
  localJobs: () => request<LocalJob[]>("/api/admin/local-jobs"),
  createStory: (data: { title: string; category: string; theme: string; story: string }, csrfToken: string) =>
    request<{ story_id: string }>("/api/admin/stories", { method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: JSON.stringify(data) }),
  storyAction: <T = { ok: boolean }>(storyId: string, action: string, data: unknown, csrfToken: string, method = "POST") =>
    request<T>(`/api/admin/story/${encodeURIComponent(storyId)}/${action}`, {
      method, headers: { "X-CSRF-Token": csrfToken }, body: JSON.stringify(data),
    }),
  discover: (csrfToken: string) => request<LocalJob>("/api/admin/discovery", {
    method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: "{}",
  }),
  retryJob: (jobId: string, csrfToken: string) => request<LocalJob>(`/api/admin/local-jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: JSON.stringify({ confirm: true }),
  }),
  uploadAudio: (storyId: string, file: File, csrfToken: string) => {
    const data = new FormData();
    data.append("audio", file);
    return request<{ ok: boolean }>(`/api/admin/story/${encodeURIComponent(storyId)}/audio/upload`, {
      method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: data,
    });
  },
  overview: () => request<Overview>("/api/admin/overview"),
  jobs: () => request<JobStatus>("/api/admin/jobs"),
  dispatchJob: (storyId: string, csrfToken: string) =>
    request<{ ok: boolean; story_id: string; status: string }>(
      "/api/admin/jobs/dispatch",
      {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ story_id: storyId }),
      },
    ),
  story: (storyId: string) =>
    request<AdminStoryDetail>(`/api/admin/story/${encodeURIComponent(storyId)}`),
  reviewRights: (storyId: string, csrfToken: string, review: {
    category: string;
    category_evidence: string;
    license_status: string;
    rights_cleared: string;
    human_reviewer: string;
    license_evidence: string;
    rights_jurisdiction: string;
    permission_for_translation: string;
    permission_for_ai_processing: string;
    permission_for_publication: string;
    permission_for_audio: string;
    permission_for_commercial_use: string;
  }) => request<{ ok: boolean; category: string; license_status: string; rights_cleared: string; review_status: string }>(
    `/api/admin/story/${encodeURIComponent(storyId)}/rights-review`,
    {
      method: "PUT",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(review),
    },
  ),
  saveDraft: (storyId: string, csrfToken: string, draft: {
    myanmar_title: string;
    myanmar_story: string;
    episodes: Episode[];
    quiz: Array<{ question: string; answer: string }>;
    reflection: string | string[];
    audio_url?: string;
    audio_status?: string;
  }) => request<{ ok: boolean; processing_status: string }>(
    `/api/admin/story/${encodeURIComponent(storyId)}/draft`,
    {
      method: "PUT",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(draft),
    },
  ),
  reviewContent: (storyId: string, action: "approve" | "reject", csrfToken: string) =>
    request<{ ok: boolean; content_review_status: string }>(
      `/api/admin/story/${encodeURIComponent(storyId)}/content-review`,
      {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ action }),
      },
    ),
  login: (password: string) =>
    request<{ csrf_token: string }>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: (csrfToken: string) =>
    request<{ ok: boolean }>("/api/admin/logout", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
    }),
};
