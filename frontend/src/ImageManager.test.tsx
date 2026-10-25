import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { ImageManager } from "./ImageManager";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("uploads and replaces an optional cover without requiring publication", async () => {
  const upload = vi.spyOn(api, "uploadImage").mockResolvedValue({ image_url: "/media/images/new.webp" });
  const changed = vi.fn();
  render(<ImageManager storyId="story-1" csrf="csrf" imageUrl="/media/images/old.webp" onChanged={changed} />);
  const file = new File(["image"], "new.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("ပုံအသစ် အစားထိုးရွေးရန်"), { target: { files: [file] } });
  await waitFor(() => expect(changed).toHaveBeenCalledWith("/media/images/new.webp"));
  expect(upload).toHaveBeenCalledWith("/api/admin/story/story-1/cover-image", file, "csrf");
  expect(screen.getByAltText("လက်ရှိပုံပြင် မျက်နှာဖုံးပုံ")).toHaveAttribute("src", "/media/images/new.webp");
});

it("restores default homepage artwork when the custom image is removed", async () => {
  vi.spyOn(api, "site").mockResolvedValue({ hero_image_url: "/media/images/home.webp" });
  const remove = vi.spyOn(api, "removeImage").mockResolvedValue({ image_url: "" });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<ImageManager csrf="csrf" />);
  fireEvent.click(await screen.findByRole("button", { name: "ပုံဖယ်ရန်" }));
  await waitFor(() => expect(screen.queryByAltText("လက်ရှိပင်မစာမျက်နှာပုံ")).not.toBeInTheDocument());
  expect(remove).toHaveBeenCalledWith("/api/admin/site/hero-image", "csrf");
  expect(screen.getByText("ပုံမထည့်ရသေးပါ · မူလဒီဇိုင်းကို သုံးနေသည်")).toBeInTheDocument();
});
