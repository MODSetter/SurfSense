import { useQuery } from "@tanstack/react-query"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster, toast } from "sonner"

import { listArtifacts } from "@/features/studio/api"
import { studioKeys } from "@/features/studio/query-keys"
import { render } from "@/test-utils"

import { listJobRuns } from "../api"
import { jobsKeys } from "../query-keys"
import {
  refusal,
  runRead,
  stubJobsApi,
  type Answer,
  type StubRequest,
} from "../stub-jobs-api"

import { ConfirmSuggestionsButton } from "./confirm-suggestions-button"

const CONFIRM = "POST /workspaces/1/job-runs/41/confirm"
const SUGGESTIONS = runRead().open_suggestions

/** Studio's list and the Jobs screen's runs, as they stay mounted beside the button. */
function Readers() {
  useQuery({
    queryKey: studioKeys.artifacts(1),
    queryFn: ({ signal }) => listArtifacts(1, signal),
  })
  useQuery({
    queryKey: jobsKeys.runs(1),
    queryFn: ({ signal }) => listJobRuns(1, 11, signal),
  })
  return null
}

function stubConfirm(answer: Answer) {
  return stubJobsApi({
    "GET /workspaces/1/artifacts": [],
    "GET /workspaces/1/job-runs?limit=11": [],
    [CONFIRM]: answer,
  })
}

const reads = (calls: StubRequest[], path: string) =>
  calls.filter((call) => call.method === "GET" && call.path === path).length

function renderButton(disabled = false) {
  render(
    <>
      <Readers />
      <Toaster />
      <ConfirmSuggestionsButton
        workspaceId={1}
        rootId={41}
        suggestions={SUGGESTIONS}
        disabled={disabled}
        size="sm"
      />
    </>
  )
}

afterEach(() => {
  toast.dismiss()
  cleanup()
  vi.unstubAllGlobals()
})

describe("confirm suggestions button", () => {
  it("lists each suggestion, then confirms them all as a new version", async () => {
    const calls = stubConfirm(() =>
      Response.json({ artifact_id: 45 }, { status: 202 })
    )
    const user = userEvent.setup()
    renderButton()
    await waitFor(() => expect(reads(calls, "/workspaces/1/artifacts")).toBe(1))

    await user.click(
      screen.getByRole("button", { name: "Confirm 2 suggested answers" })
    )
    const question = await screen.findByRole("alertdialog", {
      name: "Confirm 2 suggested answers?",
    })
    expect(
      within(question).getByText(
        "Each one is written into its cell in a new version of this copy, and the exceptions sheet notes that a person confirmed it. Confirm them only once you have checked them."
      )
    ).toBeTruthy()
    const list = within(question).getByRole("list", {
      name: "Suggested answers",
    })
    // What the cell will hold, in its own spelling.
    expect(within(list).getByText("Suggested: Not applicable")).toBeTruthy()
    expect(within(list).getByText("Questions, cell B7")).toBeTruthy()
    await user.click(within(question).getByRole("button", { name: "Confirm" }))

    expect(
      await screen.findByText(
        "Writing the confirmed answers into a new version"
      )
    ).toBeTruthy()
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
    expect(
      calls.filter((call) => `${call.method} ${call.path}` === CONFIRM)
    ).toEqual([expect.objectContaining({ body: "{}" })])
    await waitFor(() => {
      expect(reads(calls, "/workspaces/1/artifacts")).toBe(2)
      expect(reads(calls, "/workspaces/1/job-runs?limit=11")).toBe(2)
    })
  })

  it("confirms nothing on Cancel", async () => {
    const calls = stubConfirm({ artifact_id: 45 })
    const user = userEvent.setup()
    renderButton()

    await user.click(
      screen.getByRole("button", { name: "Confirm 2 suggested answers" })
    )
    const question = await screen.findByRole("alertdialog")
    await user.click(within(question).getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
    expect(calls.some((call) => call.method === "POST")).toBe(false)
  })

  it("shows why the confirmation was refused, and stays open", async () => {
    stubConfirm(
      refusal(
        409,
        "JOB_RUN_REFUSED",
        "Version 2 of this revised copy is still being made."
      )
    )
    const user = userEvent.setup()
    renderButton()

    await user.click(
      screen.getByRole("button", { name: "Confirm 2 suggested answers" })
    )
    const question = await screen.findByRole("alertdialog")
    await user.click(within(question).getByRole("button", { name: "Confirm" }))

    expect((await within(question).findByRole("alert")).textContent).toBe(
      "Version 2 of this revised copy is still being made."
    )
    expect(screen.getByRole("alertdialog")).toBeTruthy()
  })

  it("is held while a version of the copy is being made", () => {
    stubConfirm({ artifact_id: 45 })
    renderButton(true)

    expect(
      (
        screen.getByRole("button", {
          name: "Confirm 2 suggested answers",
        }) as HTMLButtonElement
      ).disabled
    ).toBe(true)
  })
})
