import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api, type AdminStory } from "./api";
import { PublicationArchive, StoryCatalogue } from "./StoryCatalogue";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it("keeps generated audio, published stories, text drafts, and untouched sources in separate lists", () => {
  const stories = [
    { story_id: "new", title: "Untouched", has_story: false },
    { story_id: "draft", title: "Draft only", has_story: true },
    { story_id: "audio", title: "Audio only", audio_url: "/media/audio/one.wav", has_story: true },
    { story_id: "published", title: "Published story", published: true, audio_url: "/media/audio/two.wav", has_story: true },
  ] as AdminStory[];
  render(<MemoryRouter><StoryCatalogue stories={stories} /></MemoryRouter>);
  expect(screen.getByText("Audio only")).toBeInTheDocument();
  expect(screen.queryByText("Untouched")).not.toBeInTheDocument();
  expect(screen.queryByText("Published story")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /ထုတ်ဝေပြီး/ }));
  expect(screen.getByText("Published story")).toBeInTheDocument();
  expect(screen.queryByText("Audio only")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Public ပုံပြင်ဖွင့်ရန်/ })).toHaveAttribute("href", "/app/#/stories/published");
  fireEvent.click(screen.getByRole("button", { name: /မလုပ်ရသေး/ }));
  expect(screen.getByText("Untouched")).toBeInTheDocument();
  expect(screen.queryByText("Draft only")).not.toBeInTheDocument();
});

it("loads the recorded publication text rather than the current draft", async () => {
  vi.spyOn(api, "publications").mockResolvedValue([{ publication_id: "record-1", story_id: "story-1", published_title: "Archived title", published_at: "2026-10-25T13:00:00Z", publication_status: "PUBLISHED", approved_by: "Reviewer", audio_url: "/media/audio/old.wav", snapshot_available: true, website_url: "" }]);
  const load = vi.spyOn(api, "publication").mockResolvedValue({ title: "Archived title", story: "Recorded version", audio_url: "/media/audio/old.wav", episodes: [], category: "CHILDREN" });
  render(<MemoryRouter><PublicationArchive /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "ထုတ်ဝေချိန်က စာသားဖတ်ရန်" }));
  expect(await screen.findByText("Recorded version")).toBeInTheDocument();
  expect(load).toHaveBeenCalledWith("record-1");
  expect(screen.getByLabelText("ထုတ်ဝေချိန်က အသံ")).toHaveAttribute("src", "/media/audio/old.wav");
});
