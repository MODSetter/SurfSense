import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"

import type { LocalRow } from "@/features/models/local/chat/api"
import { render } from "@/test-utils"

import { LocalModelList } from "./local-model-list"

function row(name: string, origin: LocalRow["origin"]): LocalRow {
  return {
    id: name,
    origin,
    name,
    recommended: false,
    runnable: true,
    support: { reads_images: false },
    lead: null,
    builds: [
      {
        catalog_id: `opaque-${name}`,
        quantization: "Q4_K_M",
        footprint_bytes: 200_000_000,
        files: [],
        fit: null,
        badge: null,
        can_install: true,
        installed_as: name,
        selected: false,
        recommended: false,
        reads_images: false,
        projector_checked: true,
        bundled: false,
      },
    ],
  } as unknown as LocalRow
}

afterEach(cleanup)

describe("LocalModelList", () => {
  it("marks a model fetched from Hugging Face apart from the curated ones", () => {
    render(
      <LocalModelList
        rows={[row("gemma-3-270m", "downloaded"), row("Qwen3 4B", "curated")]}
        installs={[]}
        disabled={false}
        onDownload={vi.fn()}
        onUse={vi.fn()}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    const [huggingFace, curated] = screen.getAllByRole("listitem")
    expect(within(huggingFace).getByText("From Hugging Face")).toBeTruthy()
    expect(within(huggingFace).queryByText("Downloaded")).toBeNull()
    expect(within(curated).getByText("Downloaded")).toBeTruthy()
    expect(within(curated).queryByText("From Hugging Face")).toBeNull()
  })
})
