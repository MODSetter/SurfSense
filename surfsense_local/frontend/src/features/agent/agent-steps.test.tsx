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

  it("opens the revised copy a revise made, named by its version", async () => {
    const openArtifact = vi.fn()
    const user = userEvent.setup()
    render(
      <OpenArtifactContext.Provider value={openArtifact}>
        <AgentSteps
          steps={[
            rendered({
              tool: "surfsense_revise_document",
              input: { artifact_id: 70, operations: [] },
              artifact: { id: 71, title: "MSA_Acme (revised)", version: 2 },
            }),
          ]}
        />
      </OpenArtifactContext.Provider>
    )

    await user.click(
      screen.getByRole("button", { name: "Revised MSA_Acme (revised) v2" })
    )
    expect(openArtifact).toHaveBeenCalledExactlyOnceWith(71)
  })

  it("names a revise that made nothing yet as an edit of a copy", () => {
    render(
      <AgentSteps
        steps={[
          rendered({
            tool: "surfsense_revise_document",
            status: "running",
            input: { document_id: 42, operations: [] },
            output: undefined,
            artifact: null,
          }),
        ]}
      />
    )

    expect(screen.getByRole("listitem").textContent).toBe(
      "Edited a copy of a source file"
    )
  })

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

  it("names an analysis by its title, and one still being written without", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_7",
            tool: "surfsense_analyze_data",
            status: "completed",
            title: null,
            input: {
              title: "Revenue by region",
              document_ids: [3],
              script: "...",
            },
          },
          {
            id: "prt_8",
            tool: "surfsense_analyze_data",
            status: "running",
            title: null,
            input: {},
          },
        ]}
      />
    )

    expect(
      screen.getAllByRole("listitem").map((item) => item.textContent)
    ).toEqual(["Ran the analysis Revenue by region", "Analysed data"])
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

  it("opens the PDF a conversion made, named by its document", async () => {
    const openArtifact = vi.fn()
    const user = userEvent.setup()
    render(
      <OpenArtifactContext.Provider value={openArtifact}>
        <AgentSteps
          steps={[
            {
              id: "prt_7",
              tool: "surfsense_convert_document",
              status: "completed",
              title: null,
              input: { artifact_id: 40, format: "pdf" },
              artifact: { id: 52, title: "Client proposal", version: 1 },
            },
          ]}
        />
      </OpenArtifactContext.Provider>
    )

    await user.click(
      screen.getByRole("button", { name: "Converted Client proposal to PDF" })
    )
    expect(openArtifact).toHaveBeenCalledExactlyOnceWith(52)
  })

  it("names a conversion still running without a document", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_8",
            tool: "surfsense_convert_document",
            status: "running",
            title: null,
            input: { document_id: 8, format: "pdf" },
          },
        ]}
      />
    )

    expect(screen.getByRole("listitem").textContent).toBe(
      "Converted a document to PDF"
    )
  })

  it("names each PDF tool's step by what it did, and one still being written", () => {
    const step = (
      id: string,
      tool: string,
      input: Record<string, unknown>
    ): AgentStep => ({ id, tool, status: "completed", title: null, input })
    render(
      <AgentSteps
        steps={[
          step("prt_9", "surfsense_pdf_pages", { operation: "merge" }),
          step("prt_10", "surfsense_pdf_pages", { operation: "split" }),
          step("prt_11", "surfsense_pdf_stamp", { kind: "page_numbers" }),
          step("prt_12", "surfsense_pdf_stamp", { kind: "watermark" }),
          step("prt_13", "surfsense_pdf_form", { action: "list" }),
          step("prt_14", "surfsense_pdf_form", { action: "fill" }),
          step("prt_15", "surfsense_pdf_pages", {}),
        ]}
      />
    )

    expect(
      screen.getAllByRole("listitem").map((item) => item.textContent)
    ).toEqual([
      "Merged PDFs",
      "Split a PDF",
      "Numbered a PDF’s pages",
      "Added a watermark to a PDF",
      "Read a PDF form’s fields",
      "Filled in a PDF form",
      "Worked on PDF pages",
    ])
  })
})
