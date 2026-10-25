import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type LocalJob, type Overview } from "./api";
import { LiveFinder } from "./MvpWorkflow";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const queued: LocalJob = { job_id: "discovery-1", story_id: "discovery", kind: "DISCOVER", status: "QUEUED", error: "", updated_at: "" };
const completed = { ...queued, status: "SUCCEEDED" };

describe("live discovery progress", () => {
  it("polls an enqueued job to completion without submitting it twice", async () => {
    let requested = false;
    let reads = 0;
    vi.spyOn(api, "localJobs").mockImplementation(async () => {
      if (!requested) return [];
      return ++reads === 1 ? [queued] : [completed];
    });
    const discover = vi.spyOn(api, "discover").mockImplementation(async () => { requested = true; return queued; });
    vi.spyOn(api, "overview").mockResolvedValue({ counts: { stories: 15 } } as Overview);
    const updated = vi.fn();
    render(<MemoryRouter><LiveFinder csrf="csrf" onUpdated={updated} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Discovery job စတင်ရန်" }));
    expect(await screen.findByText("ရှာဖွေရန် တန်းစီနေပါသည်…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ရှာဖွေနေသည်…" })).toBeDisabled();
    await waitFor(() => expect(screen.getByText("ရှာဖွေခြင်း ပြီးပါပြီ")).toBeInTheDocument(), { timeout: 4_000 });
    expect(await screen.findByText(/စုစုပေါင်း — 15 ခု/)).toBeInTheDocument();
    expect(discover).toHaveBeenCalledTimes(1);
    expect(updated).toHaveBeenCalledTimes(1);
  });

  it("restores the latest completed discovery when revisiting the page", async () => {
    vi.spyOn(api, "localJobs").mockResolvedValue([completed]);
    vi.spyOn(api, "overview").mockResolvedValue({ counts: { stories: 15 } } as Overview);
    const discover = vi.spyOn(api, "discover");
    render(<MemoryRouter><LiveFinder csrf="csrf" /></MemoryRouter>);
    expect(await screen.findByText("ရှာဖွေခြင်း ပြီးပါပြီ")).toBeInTheDocument();
    expect(await screen.findByText(/စုစုပေါင်း — 15 ခု/)).toBeInTheDocument();
    expect(discover).not.toHaveBeenCalled();
  });
});
