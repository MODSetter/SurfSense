import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { WorkspaceDocument } from "@/features/sources/api"

import { renderJobsDialog } from "../render-jobs-dialog"
import {
  dialogRoutes,
  jobSettings,
  refusal,
  runRead,
  source,
  stubJobsApi,
  workbook,
  type StubRequest,
} from "../stub-jobs-api"

const DOCUMENTS: WorkspaceDocument[] = [
  workbook(2, "Old questionnaire.xlsx"),
  source(3, "Security policy.pdf"),
  workbook(7, "Vendor questionnaire.xlsx"),
  source(9, "Backups.pdf"),
]

const reads = (calls: StubRequest[], path: string) =>
  calls.filter((call) => call.method === "GET" && call.path === path).length

const ticked = (name: string) =>
  screen.getByRole("checkbox", { name }).getAttribute("aria-checked")

async function openRunForm(
  ...args: Parameters<typeof renderJobsDialog>
): Promise<ReturnType<typeof renderJobsDialog>> {
  const user = userEvent.setup()
  const rendered = renderJobsDialog(...args)
  await user.click(
    await screen.findByRole("button", { name: "Run Security questionnaire" })
  )
  await screen.findByRole("heading", { name: "Run Security questionnaire" })
  return rendered
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("job run form", () => {
  it("starts on the newest workbook and the ticked documents, never the workbook itself", async () => {
    stubJobsApi(dialogRoutes())
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [2, 3, 7] })

    const workbooks = screen.getByRole("radiogroup", {
      name: "Workbook to fill in",
    })
    expect(
      within(workbooks)
        .getByRole("radio", { name: "Vendor questionnaire.xlsx" })
        .getAttribute("aria-checked")
    ).toBe("true")
    const documents = screen.getByRole("group", {
      name: "Your firm’s documents to answer from",
    })
    expect(within(documents).getAllByRole("checkbox")).toHaveLength(3)
    expect(
      within(documents).queryByRole("checkbox", {
        name: "Vendor questionnaire.xlsx",
      })
    ).toBeNull()
    expect(ticked("Security policy.pdf")).toBe("true")
    // Another questionnaire is rarely the evidence for this one.
    expect(ticked("Old questionnaire.xlsx")).toBe("false")
    expect(ticked("Backups.pdf")).toBe("false")
    expect(screen.getByText("1 document chosen")).toBeTruthy()
  })

  it("keeps a workbook switch from carrying the old one’s place among the documents", async () => {
    stubJobsApi(dialogRoutes())
    const user = userEvent.setup()
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [3, 7] })

    await user.click(
      screen.getByRole("radio", { name: "Old questionnaire.xlsx" })
    )

    expect(
      screen.queryByRole("checkbox", { name: "Old questionnaire.xlsx" })
    ).toBeNull()
    expect(ticked("Vendor questionnaire.xlsx")).toBe("false")
    await user.click(screen.getByRole("button", { name: "Select all" }))
    expect(screen.getByText("3 documents chosen")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Deselect all" }))
    expect(
      screen.getByText("Choose at least one document to answer from.")
    ).toBeTruthy()
    expect(
      (screen.getByRole("button", { name: "Start" }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
  })

  it("names the model that will answer as the model picker does, and says a local one leaves more to a person", async () => {
    stubJobsApi(dialogRoutes())
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [3] })

    expect(await screen.findByText("Answered by Qwen3 4B")).toBeTruthy()
    expect(
      screen.getByText(
        "Models that run on this computer are usually smaller, and leave more questions for a person to answer."
      )
    ).toBeTruthy()
    expect(screen.queryByText(/don’t run on this computer/)).toBeNull()
  })

  it("names the job’s second check, and says a remote model receives the questions", async () => {
    stubJobsApi({
      ...dialogRoutes(),
      "GET /job-packs/jobs/test-questionnaire/settings": jobSettings({
        checker: { provider: "openai_compatible", connection_id: 9, name: "m" },
      }),
    })
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [3] })

    expect(await screen.findByText("Checked again by m")).toBeTruthy()
    expect(
      screen.getByText(
        "Models that don’t run on this computer receive the questions and passages from your documents."
      )
    ).toBeTruthy()
  })

  it("says to choose a chat model when none is selected, and closes Jobs to open Settings", async () => {
    stubJobsApi(dialogRoutes())
    const user = userEvent.setup()
    const { props } = await openRunForm({
      documents: DOCUMENTS,
      includedDocumentIds: [3],
      selection: null,
    })

    expect(
      screen.getByText("Choose a chat model first. It answers the questions.")
    ).toBeTruthy()
    expect(
      (screen.getByRole("button", { name: "Start" }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
    await user.click(screen.getByRole("button", { name: "Choose a model" }))

    expect(props.onOpenChange).toHaveBeenCalledWith(false)
    expect(props.onOpenModelSettings).toHaveBeenCalledWith("chat-models")
  })

  it("says a selected model that cannot be reached can’t answer", async () => {
    stubJobsApi(dialogRoutes())
    await openRunForm({
      documents: DOCUMENTS,
      includedDocumentIds: [3],
      providerAvailable: false,
    })

    expect(
      await screen.findByText(
        "Qwen3 4B can’t be reached right now. Check it in Settings, or choose another."
      )
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Choose a model" })).toBeTruthy()
  })

  it("says what to add when no source is a workbook, and adds one", async () => {
    stubJobsApi(dialogRoutes())
    const user = userEvent.setup()
    const { props } = await openRunForm({
      documents: [source(3, "Security policy.pdf")],
      includedDocumentIds: [3],
    })
    const file = new File(["xlsx"], "Vendor questionnaire.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    })

    expect(
      screen.getByText(
        "None of this workspace’s sources is an Excel workbook (.xlsx). Add the questionnaire you received. Save a Word or older Excel file as .xlsx first."
      )
    ).toBeTruthy()
    await user.upload(screen.getByLabelText("Choose a workbook to add"), file)

    expect(props.onUploadSources).toHaveBeenCalledWith([file])
  })

  it("says a workbook and a document are still being read", async () => {
    stubJobsApi(dialogRoutes())
    await openRunForm({
      documents: [
        ...DOCUMENTS,
        workbook(10, "New.xlsx", { status: "processing" }),
        source(11, "Policy two.pdf", { status: "pending" }),
        source(12, "Policy three.pdf", { status: "processing" }),
      ],
      includedDocumentIds: [3],
    })

    expect(screen.getByText("1 workbook is still being read.")).toBeTruthy()
    expect(
      screen.getByText(
        "2 sources are still being read, and can be chosen once ready."
      )
    ).toBeTruthy()
  })

  it("adds the documents the user picks to answer from", async () => {
    stubJobsApi(dialogRoutes())
    const user = userEvent.setup()
    const { props } = await openRunForm({
      documents: [workbook(7, "Vendor questionnaire.xlsx")],
    })
    const files = [
      new File(["%PDF"], "Access policy.pdf", { type: "application/pdf" }),
      new File(["# Plan"], "Incident plan.md", { type: "text/markdown" }),
    ]

    expect(
      screen.getByText(
        "No other source is ready to answer from. Add your firm’s policies first."
      )
    ).toBeTruthy()
    await user.upload(screen.getByLabelText("Choose documents to add"), files)

    expect(props.onUploadSources).toHaveBeenCalledWith(files)
  })

  it("sends the run and shows it waiting to start", async () => {
    const calls = stubJobsApi({
      ...dialogRoutes(),
      "POST /workspaces/1/job-runs": () =>
        Response.json({ artifact_id: 41 }, { status: 201 }),
      "GET /workspaces/1/job-runs/41": runRead({
        status: "pending",
        progress: null,
        tally: null,
        report: null,
        open_suggestions: [],
        open_suggestion_count: 0,
        newest_ready_version_id: null,
        running: true,
      }),
    })
    const user = userEvent.setup()
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [3, 7] })
    await waitFor(() => expect(reads(calls, "/workspaces/1/artifacts")).toBe(1))

    await user.click(screen.getByRole("button", { name: "Start" }))

    expect(await screen.findByText("Waiting to start…")).toBeTruthy()
    const [sent] = calls.filter(
      (call) => call.method === "POST" && call.path === "/workspaces/1/job-runs"
    )
    expect(JSON.parse(String(sent.body))).toEqual({
      job: "test-questionnaire",
      document_id: 7,
      source_ids: [3],
    })
    // The copy shows in Studio at once, with its spinner.
    await waitFor(() => expect(reads(calls, "/workspaces/1/artifacts")).toBe(2))
  })

  it("shows why the run was refused", async () => {
    stubJobsApi({
      ...dialogRoutes(),
      "POST /workspaces/1/job-runs": refusal(
        409,
        "JOB_RUN_REFUSED",
        "Choose an embedding model in Settings first."
      ),
    })
    const user = userEvent.setup()
    await openRunForm({ documents: DOCUMENTS, includedDocumentIds: [3] })

    await user.click(screen.getByRole("button", { name: "Start" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Choose an embedding model in Settings first."
    )
    expect(
      screen.getByRole("heading", { name: "Run Security questionnaire" })
    ).toBeTruthy()
  })
})
