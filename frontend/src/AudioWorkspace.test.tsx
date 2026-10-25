import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type AudioStory } from "./api";
import { LiveAudioStudio, StoryAudioPanel } from "./AudioWorkspace";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const story: AudioStory = { story_id: "story-1", title: "ပုံပြင်တစ်ပုဒ်", audio_url: "", audio_status: "NOT_READY",
  content_review_status: "APPROVED", narration_permitted: true, updated_at: "", job: null };

describe("listening workspace", () => {
  it("reuses the story reviewer and updates publication readiness after listening approval", async () => {
    vi.spyOn(api, "audio").mockResolvedValue([{ ...story, audio_url: "/media/audio/preview.wav", audio_status: "PENDING_REVIEW" }]);
    const action = vi.spyOn(api, "storyAction").mockResolvedValue({ ok: true } as never);
    const reviewed = vi.fn();
    render(<MemoryRouter><StoryAudioPanel storyId="story-1" csrf="csrf" refreshKey="approved" defaultReviewer="kyarbites" onReviewed={reviewed} /></MemoryRouter>);
    expect(await screen.findByLabelText("နားထောင်စစ်သူအမည်")).toHaveValue("kyarbites");
    expect(action).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "နားထောင်ပြီး အသံအတည်ပြုရန်" }));
    await waitFor(() => expect(reviewed).toHaveBeenCalledWith("READY"));
    expect(action).toHaveBeenCalledWith("story-1", "audio/review", { action: "approve", reviewer: "kyarbites" }, "csrf");
  });

  it("shows a direct audio player for an unapproved listening preview in the audio library", async () => {
    vi.spyOn(api, "audio").mockResolvedValue([{ ...story, audio_url: "/media/audio/preview.wav", audio_status: "PENDING_REVIEW" }]);
    render(<MemoryRouter><LiveAudioStudio /></MemoryRouter>);
    const player = await screen.findByLabelText("ပုံပြင်တစ်ပုဒ် အသံနားထောင်ရန်");
    expect(player).toHaveAttribute("src", "/media/audio/preview.wav");
    expect(player).toHaveAttribute("controls");
    expect(screen.getByText("နားထောင်၍ စစ်ဆေးနိုင်ပါပြီ")).toBeInTheDocument();
  });

  it("explains the missing approvals instead of showing a fake ready status or URL field", async () => {
    vi.spyOn(api, "audio").mockResolvedValue([{ ...story, content_review_status: "PENDING", narration_permitted: false, audio_status: "PENDING_REVIEW" }]);
    render(<MemoryRouter><StoryAudioPanel storyId="story-1" csrf="csrf" refreshKey="pending" /></MemoryRouter>);
    expect(await screen.findByText("အသံ မထုတ်ရသေးပါ")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI အသံထုတ်ရန်" })).toBeDisabled();
    expect(screen.getByText("ပုံပြင်စာသားကို ဖတ်စစ်၍ အကြောင်းအရာ အတည်ပြုရန်")).toBeInTheDocument();
    expect(screen.queryByLabelText("ဤပုံပြင်အသံ နားထောင်ရန်")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("အသံဖိုင် URL")).not.toBeInTheDocument();
  });

  it("accepts explicit narration consent next to the generate button for an original story", async () => {
    vi.spyOn(api, "audio").mockResolvedValue([{ ...story, original_workspace: true, narration_permitted: false }]);
    const action = vi.spyOn(api, "storyAction").mockResolvedValue({ ok: true } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<MemoryRouter><StoryAudioPanel storyId="story-1" csrf="csrf" refreshKey="approved" /></MemoryRouter>);
    const generate = await screen.findByRole("button", { name: "AI အသံထုတ်ရန်" });
    expect(generate).toBeDisabled();
    fireEvent.click(screen.getByLabelText("ဤကိုယ်ပိုင်ပုံပြင်ကို AI အသံဖတ်ပြရန် ခွင့်ပြုသည်"));
    fireEvent.click(generate);
    await waitFor(() => expect(action).toHaveBeenCalledWith("story-1", "jobs", { kind: "AUDIO", confirm_original_narration: true }, "csrf"));
  });

  it("automatically reveals the player after a queued AI audio job finishes", async () => {
    let requested = false;
    let reads = 0;
    vi.spyOn(api, "audio").mockImplementation(async () => {
      if (!requested) return [story];
      return ++reads === 1 ? [{ ...story, job: { job_id: "audio-1", status: "QUEUED", error: "" } }]
        : [{ ...story, audio_url: "/media/audio/generated.wav", audio_status: "PENDING_REVIEW", job: { job_id: "audio-1", status: "SUCCEEDED", error: "" } }];
    });
    const action = vi.spyOn(api, "storyAction").mockImplementation(async () => { requested = true; return { ok: true } as never; });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<MemoryRouter><StoryAudioPanel storyId="story-1" csrf="session-csrf" refreshKey="approved" /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "AI အသံထုတ်ရန်" }));
    await waitFor(() => expect(screen.getByLabelText("ဤပုံပြင်အသံ နားထောင်ရန်")).toHaveAttribute("src", "/media/audio/generated.wav"), { timeout: 4_000 });
    expect(action).toHaveBeenCalledWith("story-1", "jobs", { kind: "AUDIO" }, "session-csrf");
    expect(action).toHaveBeenCalledTimes(1);
  });
});
