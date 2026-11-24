import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { WorkspaceDocument } from "@/features/sources/api"

import { renderJobsDialog } from "../render-jobs-dialog"
import {
  TEST_PACK,
  TEST_REDLINE_PACK,
  contract,
  dialogRoutes,
  jobSettings,
  redlineRunRead,
  source,
  stubJobsApi,
} from "../stub-jobs-api"

import { DOCX_MIME } from "./contract-sources"

const PACKS = [TEST_PACK, TEST_REDLINE_PACK]

const DOCUMENTS: WorkspaceDocument[] = [
  contract(2, "Old NDA.docx"),
  source(3, "Positions.pdf"),
  contract(7, "Acme NDA.docx"),
  source(9, "Standard NDA.pdf"),
]

const ticked = (name: string) =>
  screen.getByRole("checkbox", { name }).getAttribute("aria-checked")

const startButton = () =>
  screen.getByRole("button", { name: "Start" }) as HTMLButtonElement

async function openContractForm(
  ...args: Parameters<typeof renderJobsDialog>
): Promise<ReturnType<typeof renderJobsDialog>> {
  const user = userEvent.setup()
  const rendered = renderJobsDialog(...args)
  await user.click(
    await screen.findByRole("button", { name: "Run Contract redline" })
  )
  await screen.findByRole("heading", { name: "Run Contract redline" })
  return rendered
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("contract run form", () => {
  it("starts on the newest contract ticked in the sidebar, and the other ticked sources as the playbook", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    await openContractForm({
      documents: DOCUMENTS,
      includedDocumentIds: [2, 3, 7],
    })

    const contracts = screen.getByRole("radiogroup", {
      name: "Contract to review",
    })
    expect(
      within(contracts)
        .getByRole("radio", { name: "Acme NDA.docx" })
        .getAttribute("aria-checked")
    ).toBe("true")
    const playbook = screen.getByRole("group", {
      name: "Your firm’s playbook",
    })
    expect(within(playbook).getAllByRole("checkbox")).toHaveLength(3)
    expect(
      within(playbook).queryByRole("checkbox", { name: "Acme NDA.docx" })
    ).toBeNull()
    // Another Word file may be the firm’s own standard agreement.
    expect(ticked("Old NDA.docx")).toBe("true")
    expect(ticked("Positions.pdf")).toBe("true")
    expect(ticked("Standard NDA.pdf")).toBe("false")
    expect(screen.getByText("2 documents chosen")).toBeTruthy()
  })

  it("shows a lone contract as the one the run reviews, and sends it with the playbook", async () => {
    const calls = stubJobsApi({
      ...dialogRoutes({ packs: PACKS }),
      "POST /workspaces/1/job-runs": () =>
        Response.json({ artifact_id: 51 }, { status: 201 }),
      "GET /workspaces/1/job-runs/51": redlineRunRead({
        status: "pending",
        progress: null,
        tally: null,
        report: null,
        newest_ready_version_id: null,
        running: true,
      }),
    })
    const user = userEvent.setup()
    await openContractForm({
      documents: [contract(7, "Acme NDA.docx"), source(3, "Positions.pdf")],
      includedDocumentIds: [3],
    })

    expect(
      screen.getByText(
        "The contract you received, as a Word file (.docx). Each run reviews one contract: SurfSense marks up a copy and leaves your file as it is."
      )
    ).toBeTruthy()
    const reviewed = screen.getByRole("group", { name: "Contract to review" })
    expect(within(reviewed).getByText("Acme NDA.docx")).toBeTruthy()
    expect(screen.queryByRole("radio")).toBeNull()

    await user.click(startButton())

    expect(await screen.findByText("Waiting to start…")).toBeTruthy()
    const [sent] = calls.filter(
      (call) => call.method === "POST" && call.path === "/workspaces/1/job-runs"
    )
    expect(JSON.parse(String(sent.body))).toEqual({
      job: "test-redline",
      document_id: 7,
      source_ids: [3],
    })
  })

  it("adds another contract beside the one there is", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    const user = userEvent.setup()
    const { props } = await openContractForm({
      documents: [contract(7, "Acme NDA.docx"), source(3, "Positions.pdf")],
      includedDocumentIds: [3],
    })
    const file = new File(["docx"], "Beta NDA.docx", { type: DOCX_MIME })
    const input = screen.getByLabelText("Choose a contract to add")
    // jsdom opens no file chooser: the button's click on the input stands for it.
    const chooser = vi.spyOn(input, "click")

    await user.click(screen.getByRole("button", { name: "Add a contract" }))
    expect(chooser).toHaveBeenCalledOnce()
    await user.upload(input, file)

    expect(input.getAttribute("accept")).toBe(".docx")
    expect(props.onUploadSources).toHaveBeenCalledWith([file])
  })

  it("says what to add when no source is a Word file, and adds one", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    const user = userEvent.setup()
    const { props } = await openContractForm({
      documents: [source(3, "Positions.pdf")],
      includedDocumentIds: [3],
    })
    const file = new File(["docx"], "Acme NDA.docx", { type: DOCX_MIME })

    expect(
      screen.getByText(
        "None of this workspace’s sources is a Word file (.docx). Add the contract you received. Save an older Word file (.doc) as .docx first."
      )
    ).toBeTruthy()
    await user.upload(screen.getByLabelText("Choose a contract to add"), file)

    expect(props.onUploadSources).toHaveBeenCalledWith([file])
  })

  it("holds Start until a playbook document is chosen", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    const user = userEvent.setup()
    await openContractForm({ documents: DOCUMENTS, includedDocumentIds: [7] })

    expect(
      screen.getByText("Choose at least one playbook document.")
    ).toBeTruthy()
    expect(startButton().disabled).toBe(true)
    await user.click(screen.getByRole("button", { name: "Select all" }))

    expect(screen.getByText("3 documents chosen")).toBeTruthy()
    expect(startButton().disabled).toBe(false)
  })

  it("names the model that reviews the contract, its second check, and what a model elsewhere receives", async () => {
    stubJobsApi({
      ...dialogRoutes({ packs: PACKS }),
      "GET /job-packs/jobs/test-redline/settings": jobSettings({
        job: "test-redline",
        settings: [],
        checker: { provider: "openai_compatible", connection_id: 9, name: "m" },
      }),
    })
    await openContractForm({ documents: DOCUMENTS, includedDocumentIds: [3] })

    expect(await screen.findByText("Reviewed by Qwen3 4B")).toBeTruthy()
    expect(await screen.findByText("Checked again by m")).toBeTruthy()
    expect(
      screen.getByText(
        "Models that run on this computer are usually smaller, and leave more points for a person to check."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "Models that don’t run on this computer receive the contract and passages from your playbook."
      )
    ).toBeTruthy()
  })

  it("says to choose a chat model when none is selected", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    await openContractForm({
      documents: DOCUMENTS,
      includedDocumentIds: [3],
      selection: null,
    })

    expect(
      screen.getByText("Choose a chat model first. It reviews the contract.")
    ).toBeTruthy()
    expect(startButton().disabled).toBe(true)
    expect(screen.getByRole("button", { name: "Choose a model" })).toBeTruthy()
  })

  it("says a Word file and a source are still being read, and adds playbook documents", async () => {
    stubJobsApi(dialogRoutes({ packs: PACKS }))
    const user = userEvent.setup()
    const { props } = await openContractForm({
      documents: [
        contract(7, "Acme NDA.docx"),
        contract(10, "Beta NDA.docx", { status: "processing" }),
        source(11, "Fallbacks.pdf", { status: "pending" }),
      ],
    })
    const files = [
      new File(["%PDF"], "Positions.pdf", { type: "application/pdf" }),
    ]

    expect(screen.getByText("1 Word file is still being read.")).toBeTruthy()
    expect(
      screen.getByText(
        "1 source is still being read, and can be chosen once ready."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "No other source is ready to review against. Add your firm’s playbook first."
      )
    ).toBeTruthy()
    await user.upload(
      screen.getByLabelText("Choose playbook documents to add"),
      files
    )

    expect(props.onUploadSources).toHaveBeenCalledWith(files)
  })
})
