import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { OpenArtifactContext } from "@/features/studio/open-artifact"

import { AgentSteps } from "./agent-steps"
import type { AgentStep } from "./api"

function rendered(extra: Partial<AgentStep> = {}): AgentStep {
  return {
    id: "prt_1",
    tool: "surfsense_render_document",
    status: "completed",
    title: null,
    input: { title: "Client proposal", format: "docx", script: "..." },
    output: "Rendered artifact 40, version 1.",
    artifact: { id: 40, title: "Client proposal", version: 1 },
    ...extra,
  }
}

afterEach(cleanup)

describe("agent steps", () => {
  it("opens the version a render made in Studio", async () => {
    const openArtifact = vi.fn()
    const user = userEvent.setup()
    render(
      <OpenArtifactContext.Provider value={openArtifact}>
        <AgentSteps
          steps={[
            rendered({
              artifact: { id: 41, title: "Client proposal", version: 2 },
            }),
          ]}
        />
      </OpenArtifactContext.Provider>
    )

    await user.click(
      screen.getByRole("button", { name: "Updated Client proposal to v2" })
    )
    expect(openArtifact).toHaveBeenCalledExactlyOnceWith(41)
  })

  it("names a render without a link where there is no Studio to open", () => {
    render(<AgentSteps steps={[rendered()]} />)

    expect(screen.queryByRole("button")).toBeNull()
    expect(screen.getByRole("listitem").textContent).toBe(
      "Created Client proposal v1"
    )
  })

  it("names a render that made nothing by the document it was for", () => {
    render(
      <OpenArtifactContext.Provider value={vi.fn()}>
        <AgentSteps
          steps={[
            rendered({ status: "running", artifact: undefined, output: "" }),
          ]}
        />
      </OpenArtifactContext.Provider>
    )

    expect(screen.queryByRole("button")).toBeNull()
    expect(screen.getByText(/Ran the document script for/).textContent).toBe(
      "Ran the document script for Client proposal"
    )
  })

  it("names reading a document’s script and listing source images", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_2",
            tool: "surfsense_read_document",
            status: "completed",
            title: null,
            input: { artifact_id: 40 },
          },
          {
            id: "prt_3",
            tool: "surfsense_list_images",
            status: "completed",
            title: null,
            input: { source_ids: [3, 4] },
          },
        ]}
      />
    )

    expect(screen.getByText("Read the script behind a document")).toBeTruthy()
    expect(screen.getByText("Looked for images in 2 sources")).toBeTruthy()
  })
})
