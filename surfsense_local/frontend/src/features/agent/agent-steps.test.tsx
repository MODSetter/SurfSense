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

  it.each([
    { format: "pptx", title: "Board deck" },
    { format: "xlsx", title: "Budget workbook" },
  ])(
    "opens a $format the agent made as it does a Word document",
    async ({ format, title }) => {
      const openArtifact = vi.fn()
      const user = userEvent.setup()
      render(
        <OpenArtifactContext.Provider value={openArtifact}>
          <AgentSteps
            steps={[
              rendered({
                input: { title, format, script: "..." },
                artifact: { id: 60, title, version: 1, created: true },
              }),
              rendered({
                id: "prt_4",
                input: { title, format, script: "...", artifact_id: 60 },
                artifact: { id: 61, title, version: 2, created: false },
              }),
            ]}
          />
        </OpenArtifactContext.Provider>
      )

      await user.click(
        screen.getByRole("button", { name: `Created ${title} v1` })
      )
      await user.click(
        screen.getByRole("button", { name: `Updated ${title} to v2` })
      )
      expect(openArtifact.mock.calls).toEqual([[60], [61]])
    }
  )

  it("names looking at a source's pages by the source's title", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_5",
            tool: "surfsense_source_pages",
            status: "completed",
            title: null,
            input: { document_id: 8, pages: [1, 2] },
          },
        ]}
        scope={{
          document_ids: [7, 8],
          titles: ["Notes.md", "Brand guide.pdf"],
        }}
      />
    )

    expect(screen.getByRole("listitem").textContent).toBe(
      "Looked at pages of Brand guide.pdf"
    )
  })

  it("names looking at a source's pages when the turn named no sources", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_6",
            tool: "surfsense_source_pages",
            status: "running",
            title: null,
            input: { document_id: 8 },
          },
        ]}
        scope={null}
      />
    )

    expect(screen.getByRole("listitem").textContent).toBe(
      "Looked at pages of a source"
    )
  })
})
