import { describe, expect, it } from "vitest"

import type { Badge, Fit } from "./api"
import { fitReason, fitVerdict } from "./fit-text"

const fit: Fit = {
  state: "too_big",
  need_bytes: 21_000_000_000,
  budget_bytes: 13_600_000_000,
  offload_fraction: 1,
  approximate: false,
}

function badge(copy: Partial<Badge>): Badge {
  return {
    level: "notice",
    verdict: "backend verdict",
    reason: "backend reason",
    ...copy,
  }
}

describe("what a fit badge says", () => {
  it("words a tier it knows itself", () => {
    // The backend's sentences are English in every language.
    expect(fitVerdict(badge({ code: "too_big" }))).toBe("Won’t fit")
    expect(fitVerdict(badge({ code: "heavy_spill" }))).toBe("Reduced speed")
    expect(fitVerdict(badge({ code: "moderate_spill" }))).toBe("Reduced speed")
    expect(fitReason(badge({ code: "moderate_spill", uma: false }), fit)).toBe(
      "Too big for the graphics card, so part runs on the processor."
    )
  })

  it("picks its words by whether memory is unified", () => {
    // Apple Silicon has no second pool to spill into, and no graphics card.
    expect(fitReason(badge({ code: "heavy_spill", uma: true }), fit)).toBe(
      "Well over the GPU’s memory. Expect it to be slow."
    )
    expect(fitReason(badge({ code: "heavy_spill", uma: false }), fit)).toBe(
      "Well over the graphics card’s memory. Expect it to be slow."
    )
    expect(fitReason(badge({ code: "moderate_spill", uma: true }), fit)).toBe(
      "Too big for the GPU, so part runs on the CPU."
    )
    expect(fitReason(badge({ code: "light_spill", uma: true }), fit)).toBe(
      "Most of it runs on the GPU."
    )
    expect(fitReason(badge({ code: "light_spill", uma: false }), fit)).toBe(
      "Most of it runs on the graphics card."
    )
  })

  it("formats a refusal's two sizes itself", () => {
    // The backend's sentence carries "13.6 GB", which no other language can
    // re-space or re-punctuate.
    expect(fitReason(badge({ code: "too_big", uma: true }), fit)).toBe(
      "Needs about 21 GB. This Mac has 13.6 GB"
    )
    expect(fitReason(badge({ code: "too_big", uma: false }), fit)).toBe(
      "Needs about 21 GB. This PC has 13.6 GB"
    )
  })

  it("says nothing for a light spill's verdict, as the backend does", () => {
    expect(
      fitVerdict(badge({ level: "none", verdict: "", code: "light_spill" }))
    ).toBe("")
  })

  it("falls back to the backend's words for a tier it does not know", () => {
    const unknown = badge({ code: "thermal_limit" })
    expect(fitVerdict(unknown)).toBe("backend verdict")
    expect(fitReason(unknown, fit)).toBe("backend reason")

    const uncoded = badge({})
    expect(fitVerdict(uncoded)).toBe("backend verdict")
    expect(fitReason(uncoded, fit)).toBe("backend reason")
    expect(fitReason(badge({ code: null }), fit)).toBe("backend reason")
  })

  it("keeps the backend's refusal when there are no sizes to format", () => {
    expect(fitReason(badge({ code: "too_big", uma: true }), null)).toBe(
      "backend reason"
    )
  })
})
