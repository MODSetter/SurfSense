import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { OpenArtifactContext } from "@/features/studio/open-artifact"

import { AgentSteps } from "./agent-steps"
import type { AgentStep } from "./api"
import { stepLabel } from "./step-label"

// Counts how often a step's line is drawn.
vi.mock("./step-label", async (original) => {
  const actual = await original<typeof import("./step-label")>()
  return { stepLabel: vi.fn(actual.stepLabel) }
})

function rendered(extra: Partial<AgentStep> = {}): AgentStep {
  return {
    id: "prt_1",
    tool: "surfsense_render_document",
    status: "completed",
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

  it("opens the version a saved web page made in Studio", async () => {
    const openArtifact = vi.fn()
    const user = userEvent.setup()
    render(
      <OpenArtifactContext.Provider value={openArtifact}>
        <AgentSteps
          steps={[
            rendered({
              tool: "surfsense_save_page",
              input: { path: "outputs/q3.html", title: "Q3 revenue" },
              artifact: { id: 52, title: "Q3 revenue", version: 1 },
            }),
          ]}
        />
      </OpenArtifactContext.Provider>
    )

    await user.click(
      screen.getByRole("button", { name: "Created Q3 revenue v1" })
    )
    expect(openArtifact).toHaveBeenCalledExactlyOnceWith(52)
  })

  it("names a page save that made nothing by the page it was for", () => {
    render(
      <AgentSteps
        steps={[
          rendered({
            tool: "surfsense_save_page",
            status: "error",
            input: { path: "outputs/q3.html", title: "Q3 revenue" },
            artifact: undefined,
            output: "The page is not UTF-8 text: save it as UTF-8.",
          }),
        ]}
      />
    )

    expect(screen.getByText(/Saved the web page/).textContent).toBe(
      "Saved the web page Q3 revenue"
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
            input: { artifact_id: 40 },
          },
          {
            id: "prt_3",
            tool: "surfsense_list_images",
            status: "completed",
            input: { source_ids: [3, 4] },
          },
        ]}
      />
    )

    expect(screen.getByText("Read the script behind a document")).toBeTruthy()
    expect(screen.getByText("Looked for images in 2 sources")).toBeTruthy()
  })

  it("names loading a plugin's tools, asked for or not, and looking for tools", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "call_1",
            tool: "surfsense_loaded_tools",
            status: "completed",
            input: { plugin: "Linear" },
            loaded_plugin: "Linear",
          },
          {
            // Asked for by its @id; the step names the plugin by its name.
            id: "call_2",
            tool: "surfsense_open_plugin",
            status: "completed",
            input: { plugin: "@notion" },
            loaded_plugin: "Notion",
          },
          {
            id: "call_3",
            tool: "surfsense_find_tools",
            status: "completed",
            input: { query: "file a bug" },
            output: "No plugin tool you do not already hold fits that.",
          },
          {
            id: "call_4",
            tool: "surfsense_find_tools",
            status: "completed",
            input: { query: "check the weather" },
            output: "These tools are yours now.",
            loaded_plugin: "Weather",
          },
        ]}
      />
    )

    for (const label of [
      "Loaded Linear’s tools",
      "Loaded Notion’s tools",
      "Looked for tools to file a bug",
      "Loaded Weather’s tools",
    ]) {
      expect(screen.getByText(label)).toBeTruthy()
    }
  })

  it("names a file the same in a thread made on opencode 1.x and on 2.x", () => {
    // 1.x's file tools took `filePath`; 2.x's, and Claude Code's steps, `path`.
    render(
      <AgentSteps
        steps={[
          {
            id: "call_1",
            tool: "write",
            status: "completed",
            input: { filePath: "/w/agent/threads/7/outputs/old.md" },
          },
          {
            id: "call_2",
            tool: "write",
            status: "completed",
            input: { path: "outputs/new.md" },
          },
        ]}
      />
    )

    expect(screen.getByText("old.md")).toBeTruthy()
    expect(screen.getByText("new.md")).toBeTruthy()
  })

  it("names reading a workbook's cells by the workbook", () => {
    render(
      <AgentSteps
        steps={[
          {
            id: "prt_20",
            tool: "surfsense_read_document",
            status: "completed",
            input: { document_id: 8 },
          },
          {
            id: "prt_21",
            tool: "surfsense_read_document",
            status: "completed",
            input: { artifact_id: 61 },
            output:
              'Artifact 61, version 2 of the revised copy of "Pricing.xlsx", is a workbook. Each cell below …',
          },
          {
            id: "prt_22",
            tool: "surfsense_read_document",
            status: "running",
            input: { document_id: 9 },
          },
        ]}
        scope={{ document_ids: [8], titles: ["Budget.xlsx"] }}
      />
    )

    // A finished step folds its result under its label.
    expect(
      screen
        .getAllByRole("listitem")
        .map((item) => (item.querySelector("summary") ?? item).textContent)
    ).toEqual([
      "Read the cells of Budget.xlsx",
      "Read the cells of Pricing.xlsx",
      "Read the cells of a workbook",
    ])
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
            input: { document_id: 8, format: "pdf" },
          },
        ]}
      />
    )

    expect(screen.getByRole("listitem").textContent).toBe(
      "Converted a document to PDF"
    )
  })

  it("redraws only the steps that changed as a reply streams", () => {
    const pages = (id: string, documentId: number): AgentStep => ({
      id,
      tool: "surfsense_source_pages",
      status: "completed",
      input: { document_id: documentId },
    })
    const scope = { document_ids: [7, 8], titles: ["Notes.md", "Brief.pdf"] }
    const first = pages("prt_30", 7)
    const second = pages("prt_31", 8)
    const { rerender } = render(
      <AgentSteps steps={[first, second]} scope={scope} />
    )
    vi.mocked(stepLabel).mockClear()

    rerender(
      <AgentSteps steps={[first, second, pages("prt_32", 8)]} scope={scope} />
    )

    expect(vi.mocked(stepLabel).mock.calls.map(([step]) => step.id)).toEqual([
      "prt_32",
    ])

    rerender(
      <AgentSteps
        steps={[first, second]}
        scope={{ document_ids: [7, 8], titles: ["Notes v2.md", "Brief.pdf"] }}
      />
    )

    expect(screen.getAllByRole("listitem")[0].textContent).toBe(
      "Looked at pages of Notes v2.md"
    )
  })

  it("names each PDF tool's step by what it did, and one still being written", () => {
    const step = (
      id: string,
      tool: string,
      input: Record<string, unknown>
    ): AgentStep => ({ id, tool, status: "completed", input })
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
