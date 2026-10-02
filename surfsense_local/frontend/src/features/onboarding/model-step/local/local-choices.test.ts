import { describe, expect, it } from "vitest"

import type { LocalRow } from "@/features/models/local/chat/api"

import { localChoices } from "./local-choices"

function row(
  id: string,
  origin: LocalRow["origin"],
  { installed = false, recommended = false } = {}
): LocalRow {
  return {
    id,
    origin,
    recommended,
    runnable: true,
    lead: null,
    builds: [{ quantization: "Q4_K_M", installed_as: installed ? id : null }],
  } as unknown as LocalRow
}

describe("localChoices", () => {
  it("lists models downloaded from Hugging Face above the unchanged curated list", () => {
    const rows = [
      row("curated-a", "curated"),
      row("hf-a", "downloaded", { installed: true }),
      row("curated-star", "curated", { recommended: true }),
      row("hf-b", "search", { installed: true }),
      row("hf-not-on-disk", "search"),
      row("curated-b", "curated"),
    ]

    expect(localChoices(rows).map((choice) => choice.id)).toEqual([
      "hf-a",
      "hf-b",
      "curated-star",
      "curated-a",
      "curated-b",
    ])
  })
})
