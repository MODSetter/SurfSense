import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Toaster, toast } from "sonner"

import { render } from "@/test-utils"

import type { PackInfo } from "../api"
import {
  LICENSE_SERVER_OFF,
  TEST_PACK,
  packOutcome,
  showWindowAgainLater,
  stubJobsApi,
  stubOpenExternal,
  type Answer,
} from "../stub-jobs-api"

import { LicenseJobPacks } from "./license-job-packs"

const DOWNLOADED = {
  outcomes: [
    {
      entitlement: "JOB_QUESTIONNAIRE",
      outcome: "installed",
      message: "Test pack 0.4.3 is installed.",
      version: "0.4.3",
      detail: null,
    },
  ],
  packs: [TEST_PACK],
}

function renderBlock(
  routes: Record<string, Answer>,
  { canDownload = true, disabled = false, toasts = false } = {}
) {
  const calls = stubJobsApi(routes)
  render(
    <>
      <LicenseJobPacks
        jobs={["JOB_QUESTIONNAIRE"]}
        canDownload={canDownload}
        disabled={disabled}
      />
      {toasts ? <Toaster /> : null}
    </>
  )
  return calls
}

const zip = () =>
  new File(["PK"], "test-pack-0.4.3.zip", { type: "application/zip" })

const WAITING =
  "A run of Security questionnaire was under way, so any newer version waits until the run ends."

const WAITING_ON_ITS_PACK =
  "Security questionnaire comes in the same pack as a job whose run was under way, so it waits until the run ends."

afterEach(() => {
  // Sonner keeps its toasts across tests; one left over would show in the next Toaster.
  toast.dismiss()
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  delete window.surfsense
})

describe("license job packs", () => {
  it("lists the license’s jobs and the version on this computer", async () => {
    renderBlock({ "GET /job-packs": [TEST_PACK] })

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(screen.getByText("Security questionnaire")).toBeTruthy()
    // Every job is here, so the one button checks for newer versions.
    expect(
      screen.getByRole("button", { name: "Check for updates" })
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Import pack file" })
    ).toBeTruthy()
  })

  it("downloads a job not yet on this computer", async () => {
    const calls = renderBlock({
      "GET /job-packs": [],
      "POST /job-packs/download": DOWNLOADED,
    })
    const user = userEvent.setup()

    expect(await screen.findByText("Not downloaded yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Download" }))

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(
      calls.filter((call) => call.path === "/job-packs/download")
    ).toHaveLength(1)
  })

  it("offers no download once the license has ended, only the import", async () => {
    renderBlock({ "GET /job-packs": [] }, { canDownload: false })

    expect(await screen.findByText("Not downloaded yet")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull()
    expect(
      screen.queryByRole("button", { name: "Check for updates" })
    ).toBeNull()
    expect(
      screen.getByRole("button", { name: "Import pack file" })
    ).toBeTruthy()
  })

  it("says where to allow the license server when it was not asked", async () => {
    // No consent prompt is mounted here, so the refusal stands.
    renderBlock({
      "GET /job-packs": [],
      "POST /job-packs/download": LICENSE_SERVER_OFF,
    })
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: "Download" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "SurfSense didn’t contact its license server, api.surfsense.com. Try again and choose Allow, or allow it in Settings › Network."
    )
  })

  it("forgets a download that sent nothing once the job’s pack file is imported", async () => {
    renderBlock({
      "GET /job-packs": [],
      "POST /job-packs/download": LICENSE_SERVER_OFF,
      "POST /job-packs/import": [TEST_PACK],
    })
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: "Download" }))
    expect((await screen.findByRole("alert")).textContent).toBe(
      "SurfSense didn’t contact its license server, api.surfsense.com. Try again and choose Allow, or allow it in Settings › Network."
    )
    await user.upload(screen.getByLabelText("Choose a job pack file"), zip())

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("says when the pack file imported is the version already installed", async () => {
    renderBlock(
      { "GET /job-packs": [TEST_PACK], "POST /job-packs/import": [TEST_PACK] },
      { toasts: true }
    )
    const user = userEvent.setup()

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    await user.upload(screen.getByLabelText("Choose a job pack file"), zip())

    expect(
      await screen.findByText("That version is already installed")
    ).toBeTruthy()
    expect(
      screen.queryByText("Security questionnaire version 0.4.3 is installed")
    ).toBeNull()
  })

  it("keeps the import’s listing when a read sent before it answers after", async () => {
    let answerRead: (response: Response) => void = () => undefined
    const calls = renderBlock({
      "GET /job-packs": () =>
        new Promise<Response>((resolve) => (answerRead = resolve)),
      "POST /job-packs/import": [TEST_PACK],
    })
    const user = userEvent.setup()

    await user.upload(screen.getByLabelText("Choose a job pack file"), zip())
    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    // The read went out first, so it carries the listing from before the import.
    answerRead(Response.json([]))
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)))

    expect(screen.getByText("Version 0.4.3")).toBeTruthy()
    expect(screen.queryByText("Not downloaded yet")).toBeNull()
    expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      "GET /job-packs",
      "POST /job-packs/import",
    ])
  })

  it("says any newer version waits until a run under way ends", async () => {
    renderBlock({
      "GET /job-packs": [TEST_PACK],
      "POST /job-packs/download": {
        ...DOWNLOADED,
        outcomes: [
          { ...DOWNLOADED.outcomes[0], outcome: "deferred", version: "0.4.3" },
        ],
      },
    })
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )

    expect((await screen.findByText(WAITING)).getAttribute("role")).toBe(
      "status"
    )
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("stops saying a newer version waits once another version is in place", async () => {
    let listed: PackInfo[] = [TEST_PACK]
    renderBlock({
      "GET /job-packs": () => Response.json(listed),
      "POST /job-packs/download": {
        outcomes: [packOutcome("deferred", { version: "0.4.3" })],
        packs: [TEST_PACK],
      },
    })
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    // The version the check was held back from replacing is still the one here.
    expect(await screen.findByText(WAITING)).toBeTruthy()
    // The check made once the run ended put a newer version in place.
    listed = [{ ...TEST_PACK, version: "0.5.0" }]
    showWindowAgainLater()

    expect(await screen.findByText("Version 0.5.0")).toBeTruthy()
    expect(screen.queryByText(WAITING)).toBeNull()
  })

  it("says a newer version waits while two packs have the job and the newer is kept", async () => {
    // A developer's pack, listed first, has the same job at an older version.
    const devPack: PackInfo = {
      ...TEST_PACK,
      id: "a-dev-pack",
      version: "0.1.0",
    }
    let listed: PackInfo[] = [devPack, TEST_PACK]
    renderBlock({
      "GET /job-packs": () => Response.json(listed),
      "POST /job-packs/download": {
        // The backend names the newest installed pack with the job.
        outcomes: [packOutcome("deferred", { version: "0.4.3" })],
        packs: [devPack, TEST_PACK],
      },
    })
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )

    expect(await screen.findByText(WAITING)).toBeTruthy()
    expect(screen.getByText("Version 0.1.0")).toBeTruthy()
    // The check made once the run ended put a newer version of that pack in place.
    listed = [devPack, { ...TEST_PACK, version: "0.5.0" }]
    showWindowAgainLater()

    await waitFor(() => expect(screen.queryByText(WAITING)).toBeNull())
  })

  it("says a job not downloaded yet waits while a run of another job in its pack is under way", async () => {
    let listed: PackInfo[] = []
    renderBlock({
      "GET /job-packs": () => Response.json(listed),
      // No version: no pack here has the job. The backend sends this only
      // when the pack that adds the job waits on a run of another of its jobs.
      "POST /job-packs/download": {
        outcomes: [packOutcome("deferred")],
        packs: [],
      },
    })
    const user = userEvent.setup()

    expect(await screen.findByText("Not downloaded yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Download" }))

    expect(
      (await screen.findByText(WAITING_ON_ITS_PACK)).getAttribute("role")
    ).toBe("status")
    expect(screen.queryByText(WAITING)).toBeNull()
    expect(screen.queryByRole("alert")).toBeNull()
    expect(screen.getByText("Not downloaded yet")).toBeTruthy()
    // The download made once the run ended put the job in place.
    listed = [TEST_PACK]
    showWindowAgainLater()

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(screen.queryByText(WAITING_ON_ITS_PACK)).toBeNull()
  })

  it.each([
    [
      "the job comes only in a pack with a job the license lacks",
      packOutcome("pack_not_covered", { detail: "pack_not_covered" }),
      "Security questionnaire comes only in a pack with a job your license doesn’t include, so SurfSense’s license server sent nothing. Contact SurfSense support.",
    ],
    [
      "the pack sent holds a job this computer’s license file lacks",
      packOutcome("license_outdated", { detail: "PACK_NOT_INCLUDED" }),
      "Your license has changed on SurfSense’s license server. Check for renewal in Settings › License, then download Security questionnaire again.",
    ],
  ])("says what to do under the job when %s", async (_, outcome, said) => {
    renderBlock({
      "GET /job-packs": [],
      "POST /job-packs/download": { outcomes: [outcome], packs: [] },
    })
    const user = userEvent.setup()

    await user.click(await screen.findByRole("button", { name: "Download" }))

    expect((await screen.findByRole("alert")).textContent).toBe(said)
    expect(screen.getByText("Not downloaded yet")).toBeTruthy()
  })

  it("holds both buttons while another change to the license is made", async () => {
    renderBlock({ "GET /job-packs": [] }, { disabled: true })

    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: "Download" }) as HTMLButtonElement)
          .disabled
      ).toBe(true)
    )
    expect(
      (
        screen.getByRole("button", {
          name: "Import pack file",
        }) as HTMLButtonElement
      ).disabled
    ).toBe(true)
  })

  it("asks support for a pack file from Settings › License", async () => {
    renderBlock({ "GET /job-packs": [] })
    const openExternal = stubOpenExternal()
    const user = userEvent.setup()

    await user.click(screen.getByRole("link", { name: "Contact support" }))

    expect(openExternal).toHaveBeenCalledWith(
      "https://www.surfsense.com/contact?utm_source=desktop&utm_medium=app&utm_content=license_jobs_support"
    )
  })

  it("says the jobs on this computer could not be read", async () => {
    renderBlock({
      "GET /job-packs": () =>
        Response.json({ detail: "down" }, { status: 500 }),
    })

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Could not read which jobs are on this computer."
    )
  })
})
