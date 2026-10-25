import { cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { PublicStory } from "./api";
import { StoryWorld } from "./StoryWorld";

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });
const stories: PublicStory[] = [
  { story_id: "kids", title: "Child story", category: "CHILDREN", story: "A kind friend in the forest.", episodes: [], audio_url: "/media/audio/child.wav", cover_image_url: "/media/images/child.webp" },
  { story_id: "adult", title: "Adult story", category: "ADULT", story: "Another world awaits.", episodes: [], audio_url: "/media/audio/adult.wav" },
];
const reload = vi.fn(async () => {});

it("selects a real story preview and its audio, and keeps favorites in this browser", async () => {
  render(<MemoryRouter initialEntries={["/stories"]}><StoryWorld stories={stories} error="" reload={reload} mode="library" /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Adult story အကြိုကြည့်ရန်" }));
  expect(screen.getByLabelText("ရွေးထားသော ပုံပြင်အသံ")).toHaveAttribute("src", "/media/audio/adult.wav");
  fireEvent.click(screen.getAllByRole("button", { name: "Adult story သိမ်းထားရန်" })[0]);
  expect(JSON.parse(localStorage.getItem("pyonpyin-reader-favorites") || "[]")).toEqual(["adult"]);
  fireEvent.click(screen.getByRole("link", { name: /^Favorites/ }));
  const main = screen.getByRole("main");
  expect(within(main).getByRole("heading", { name: "Adult story" })).toBeInTheDocument();
  expect(within(main).queryByRole("heading", { name: "Child story" })).not.toBeInTheDocument();
});

it("shows uploaded artwork and keeps category filtering connected to real stories", () => {
  render(<MemoryRouter initialEntries={["/stories"]}><StoryWorld stories={stories} error="" reload={reload} mode="library" /></MemoryRouter>);
  expect(document.querySelector('img[src="/media/images/child.webp"]')).toBeInTheDocument();
  fireEvent.click(within(screen.getByLabelText("အမျိုးအစား စစ်ထုတ်ရန်")).getByRole("button", { name: "ကလေးများ" }));
  expect(within(screen.getByRole("main")).queryByRole("heading", { name: "Adult story" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("ရွေးထားသော ပုံပြင်အသံ")).toHaveAttribute("src", "/media/audio/child.wav");
});

it("records a reading visit and renders the full story with the existing audio file", async () => {
  render(<MemoryRouter initialEntries={["/stories/kids"]}><StoryWorld stories={stories} error="" reload={reload} mode="story" storyId="kids" /></MemoryRouter>);
  await waitFor(() => expect(JSON.parse(localStorage.getItem("pyonpyin-reader-history") || "[]")).toEqual(["kids"]));
  expect(screen.getByLabelText("ပုံပြင်အသံဖိုင်")).toHaveAttribute("src", "/media/audio/child.wav");
  expect(within(screen.getByRole("main")).getByText(stories[0].story)).toBeInTheDocument();
});
