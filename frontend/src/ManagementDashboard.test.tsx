import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api, type AdminStory, type Overview } from "./api";
import { ManagementDashboard } from "./ManagementDashboard";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it("filters real dashboard rows without mixing published stories with generated audio", async () => {
  vi.spyOn(api, "story").mockResolvedValue({ production: { myanmar_story: "Preview text" } } as never);
  const stories = [
    { story_id: "new", title: "Untouched source", has_story: false },
    { story_id: "audio", title: "Generated narration", has_story: true, audio_url: "/media/audio/one.wav", audio_status: "PENDING_REVIEW" },
    { story_id: "live", title: "Published story", has_story: true, published: true, audio_url: "/media/audio/two.wav", audio_status: "READY" },
  ] as AdminStory[];
  render(<MemoryRouter><ManagementDashboard stories={stories} counts={{ published: 1, content_review: 0 } as Overview["counts"]} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: /Audio Library/ }));
  const table = screen.getByRole("table");
  expect(within(table).getByText("Generated narration")).toBeInTheDocument();
  expect(within(table).queryByText("Published story")).not.toBeInTheDocument();
  fireEvent.click(within(table).getByRole("button", { name: "Generated narration" }));
  expect(await screen.findByLabelText("Dashboard ရွေးထားသောပုံပြင်အသံ")).toHaveAttribute("src", "/media/audio/one.wav");
});
