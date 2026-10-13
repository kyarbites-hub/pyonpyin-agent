import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("admin API CSRF integration", () => {
  it("sends the in-memory Flask CSRF token with draft and review mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const csrfToken = "session-csrf-token";

    await api.saveDraft("story-1", csrfToken, {
      myanmar_title: "ခေါင်းစဉ်",
      myanmar_story: "ပုံပြင်",
      episodes: [{ episode_number: 1, title: "အပိုင်း ၁", content: "ပုံပြင်" }],
      quiz: [{ question: "မေးခွန်း", answer: "အဖြေ" }],
      reflection: "စဉ်းစားရန်",
      audio_url: "",
      audio_status: "NOT_READY",
    });
    await api.reviewContent("story-1", "approve", csrfToken);
    await api.dispatchJob("story-1", csrfToken);
    await api.reviewRights("story-1", csrfToken, {
      category: "CHILDREN",
      category_evidence: "Human-verified age category",
      license_status: "APPROVED",
      rights_cleared: "YES",
      human_reviewer: "Reviewer",
      license_evidence: "Work-specific license evidence",
      rights_jurisdiction: "Myanmar",
      permission_for_translation: "YES",
      permission_for_ai_processing: "YES",
      permission_for_publication: "NO",
      permission_for_audio: "NO",
      permission_for_commercial_use: "NO",
    });

    expect(fetchMock).toHaveBeenCalledTimes(4);
    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe(csrfToken);
    }
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "PUT" });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[2][1]).toMatchObject({ method: "POST" });
    expect(fetchMock.mock.calls[3][1]).toMatchObject({ method: "PUT" });
  });
});
