import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
import { AppDialogs } from "@/components/ui/app-dialog-slot"
import { EgressPrompt } from "@/features/egress/egress-prompt"
import type { PackDownload, PackInfo } from "@/features/jobs/api"
import { JobList } from "@/features/jobs/job-list"
import { TEST_PACK, showWindowAgainLater } from "@/features/jobs/stub-jobs-api"
import { useJobPacks } from "@/features/jobs/use-job-packs"
import {
  SettingsDialog,
  type SettingsSectionId,
} from "@/features/settings/settings-dialog"
import { render } from "@/test-utils"

import type { LicenseStatus } from "./api"

const NONE: LicenseStatus = {
  state: "none",
  plan: null,
  email: null,
  expiry: null,
  max_users: null,
  firm: null,
  jobs: [],
}

const ACTIVE: LicenseStatus = {
  state: "active",
  plan: "individual",
  email: "ada@example.com",
  expiry: "2027-09-10T00:00:00Z",
  max_users: null,
  firm: null,
  jobs: [],
}

// As docs/contracts/license-sample/business.lic reads.
const BUSINESS: LicenseStatus = {
  state: "active",
  plan: "business",
  email: "partner@example.com",
  expiry: "2027-10-10T00:00:00Z",
  max_users: 5,
  firm: "Example Accounting LLP",
  jobs: ["JOB_QUESTIONNAIRE"],
}

const CERTIFICATE =
  "-----BEGIN LICENSE FILE-----\neyJlbmMiOiJ4In0=\n-----END LICENSE FILE-----\n"

/** Each time the paid plugins' license verdict was asked for, by its URL. */
let licenseChecks: string[] = []

/** Each read of the jobs on this computer, and each download of them, in order. */
let packRequests: string[] = []

/** The license the backend has stored, which its own daily check may change
 *  with no request from the app. */
let storedLicense: LicenseStatus = NONE

const downloads = () =>
  packRequests.filter((request) => request === "POST /job-packs/download")
    .length

function stubApi(
  initial: LicenseStatus,
  onPut: () => Response,
  onRefresh?: () => Response | Promise<Response>,
  // The jobs on this computer, and the download's answer, which by default
  // installs nothing.
  {
    packs = [],
    onDownload,
  }: {
    packs?: PackInfo[]
    onDownload?: () => Response | Promise<Response>
  } = {}
) {
  storedLicense = initial
  let installed = packs
  licenseChecks = []
  packRequests = []
  const calls: { method: string; body: unknown }[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (path === "/license/status") return Response.json(storedLicense)
      if (path.startsWith("/plugins/license/check") && method === "POST") {
        licenseChecks.push(path)
        return new Response(null, { status: 204 })
      }
      if (path === "/job-packs" && method === "GET") {
        packRequests.push("GET /job-packs")
        return Response.json(installed)
      }
      if (path === "/job-packs/download" && method === "POST") {
        packRequests.push("POST /job-packs/download")
        const response =
          (await onDownload?.()) ??
          Response.json({ outcomes: [], packs: installed })
        if (response.ok)
          installed = ((await response.clone().json()) as PackDownload).packs
        return response
      }
      if (path === "/license/refresh" && method === "POST" && onRefresh) {
        calls.push({ method, body: init?.body ?? null })
        const response = await onRefresh()
        if (response.ok)
          storedLicense = (await response.clone().json()) as LicenseStatus
        return response
      }
      if (path === "/license" && method === "PUT") {
        calls.push({ method, body: JSON.parse(String(init?.body)) })
        const response = onPut()
        if (response.ok)
          storedLicense = (await response.clone().json()) as LicenseStatus
        return response
      }
      if (path === "/license" && method === "DELETE") {
        calls.push({ method, body: null })
        storedLicense = NONE
        return new Response(null, { status: 204 })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return calls
}

function stubBridge() {
  const openExternal = vi.fn<(url: string) => Promise<void>>(
    async () => undefined
  )
  window.surfsense = { ...window.surfsense!, openExternal }
  return { openExternal }
}

/** The backend's answer while the license server is off in Settings › Network. */
const LICENSE_SERVER_OFF = {
  detail: {
    code: "refresh_egress_blocked",
    message: "The backend’s own words",
    destination: "host:api.surfsense.com",
    host: "api.surfsense.com",
    hosts: ["api.surfsense.com"],
    purpose: "license_refresh",
  },
}

/** Answers Allow's switch in Settings › Network; each list it switched on, in order. */
function stubEgressSwitch() {
  const switched: string[][] = []
  const answer = globalThis.fetch
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/egress" && init?.method === "PUT") {
        switched.push(JSON.parse(String(init.body)).destinations)
        return Response.json([])
      }
      return answer(input, init)
    })
  )
  return switched
}

/** Settings as the app shell mounts it, with the consent question beside it. */
function WithConsent() {
  return (
    <AppDialogs dialogs={[EgressPrompt]}>
      <Harness />
    </AppDialogs>
  )
}

/** A refusal as the backend sends one: its own English, which the app replaces. */
function refusal(status: number, code: string) {
  return () =>
    Response.json(
      { detail: { code, message: "The backend’s own words" } },
      { status }
    )
}

async function openAddDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Add license" }))
  return screen.getByRole("dialog", { name: /Add license/ })
}

function Harness() {
  const [section, setSection] = useState<SettingsSectionId>("license")
  return (
    <ThemeProvider>
      <SettingsDialog
        open
        section={section}
        onOpenChange={() => undefined}
        onSectionChange={setSection}
        onModelSelected={() => undefined}
      />
    </ThemeProvider>
  )
}

beforeEach(() => {
  vi.useFakeTimers({
    shouldAdvanceTime: true,
    now: new Date("2026-09-11T12:00:00Z"),
  })
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

afterEach(() => {
  cleanup()
  delete window.surfsense
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe("License settings", () => {
  it("imports a picked .lic file and shows whose plan it is", async () => {
    const calls = stubApi(NONE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    expect(await screen.findByText("No license on this device")).toBeTruthy()
    const dialog = await openAddDialog(user)
    await user.upload(
      within(dialog).getByLabelText("Choose license file"),
      new File([CERTIFICATE], "individual.lic", { type: "text/plain" })
    )

    expect(await screen.findByText("Individual plan")).toBeTruthy()
    expect(screen.getByText("Active")).toBeTruthy()
    expect(screen.getByText("ada@example.com")).toBeTruthy()
    expect(
      screen.getByText(/Expires 10 Sept 2027|Expires Sep 10, 2027/)
    ).toBeTruthy()
    expect(calls).toEqual([
      { method: "PUT", body: { certificate: CERTIFICATE } },
    ])
  })

  it("asks at once whether the new license unlocks the paid plugins", async () => {
    stubApi(NONE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    const dialog = await openAddDialog(user)
    await user.upload(
      within(dialog).getByLabelText("Choose license file"),
      new File([CERTIFICATE], "individual.lic", { type: "text/plain" })
    )

    await waitFor(() =>
      expect(licenseChecks).toEqual(["/plugins/license/check"])
    )
  })

  it("accepts a pasted certificate", async () => {
    const calls = stubApi(NONE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    const dialog = await openAddDialog(user)
    await user.type(
      within(dialog).getByLabelText("Paste license file"),
      "-----BEGIN LICENSE FILE-----"
    )
    await user.click(within(dialog).getByRole("button", { name: "Add" }))

    expect(await screen.findByText("Individual plan")).toBeTruthy()
    expect(calls[0]?.body).toEqual({
      certificate: "-----BEGIN LICENSE FILE-----",
    })
  })

  it("explains a refused file and keeps the device unlicensed", async () => {
    stubApi(NONE, () =>
      Response.json(
        {
          detail: {
            code: "bad_signature",
            message:
              "This license file was not issued by SurfSense, or it was altered.",
          },
        },
        { status: 422 }
      )
    )
    const user = userEvent.setup()
    render(<Harness />)

    const dialog = await openAddDialog(user)
    await user.upload(
      within(dialog).getByLabelText("Choose license file"),
      new File(["nope"], "fake.lic", { type: "text/plain" })
    )

    expect((await screen.findByRole("alert")).textContent).toContain(
      "not issued by SurfSense"
    )
    expect(screen.getByText("No license on this device")).toBeTruthy()
  })

  it("warns when the license runs out within two weeks", async () => {
    stubApi({ ...ACTIVE, plan: "trial", expiry: "2026-09-20T00:00:00Z" }, () =>
      Response.json(ACTIVE)
    )
    render(<Harness />)

    expect(await screen.findByText("Trial plan")).toBeTruthy()
    expect(screen.getByRole("status").textContent).toContain("Expiring soon")
    expect(screen.getByRole("status").textContent).toContain("9 days")
  })

  it("offers the trial and the pricing page when there is no license", async () => {
    stubApi(NONE, () => Response.json(ACTIVE))
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<Harness />)

    await screen.findByText("No license on this device")
    await user.click(screen.getByRole("link", { name: "Start a free trial" }))
    await user.click(screen.getByRole("link", { name: "See pricing" }))

    // Each says which place in the app it came from; no version is read here.
    expect(bridge.openExternal.mock.calls).toEqual([
      [
        "https://www.surfsense.com/pricing?utm_source=desktop&utm_medium=app&utm_content=license_trial",
      ],
      [
        "https://www.surfsense.com/pricing?utm_source=desktop&utm_medium=app&utm_content=license_pricing",
      ],
    ])
  })

  it("sends an expired license to pricing, not to an account", async () => {
    stubApi({ ...ACTIVE, state: "license_expired" }, () =>
      Response.json(ACTIVE)
    )
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<Harness />)

    const status = await screen.findByRole("status")
    expect(status.textContent).not.toContain("account")
    await user.click(
      within(status).getByRole("link", { name: "Renew license" })
    )

    expect(bridge.openExternal).toHaveBeenCalledExactlyOnceWith(
      "https://www.surfsense.com/pricing?utm_source=desktop&utm_medium=app&utm_content=license_renew"
    )
  })

  it("tells an expired license from an untrusted clock", async () => {
    stubApi({ ...ACTIVE, state: "license_expired" }, () =>
      Response.json(ACTIVE)
    )
    render(<Harness />)

    expect((await screen.findByRole("status")).textContent).toContain("expired")
  })

  it("opens replace from an active license", async () => {
    stubApi(ACTIVE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(
      await screen.findByRole("button", { name: "Replace license" })
    )

    expect(screen.getByRole("dialog", { name: /Replace license/ })).toBeTruthy()
  })

  it("removes the license from this device", async () => {
    const calls = stubApi(ACTIVE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(
      await screen.findByRole("button", { name: "Remove license" })
    )

    await waitFor(() =>
      expect(screen.getByText("No license on this device")).toBeTruthy()
    )
    expect(calls).toEqual([{ method: "DELETE", body: null }])
  })
})

describe("Business license", () => {
  it("shows the firm, the people and the jobs it unlocks", async () => {
    stubApi(BUSINESS, () => Response.json(BUSINESS))
    render(<Harness />)

    expect(await screen.findByText("Business plan")).toBeTruthy()
    expect(screen.getByText("Licensed to Example Accounting LLP")).toBeTruthy()
    expect(screen.getByText("5 people")).toBeTruthy()
    expect(screen.getByText("Jobs: Security questionnaire")).toBeTruthy()
    expect(screen.queryByText(/seat/)).toBeNull()
  })

  it("names a one-person license Solo and counts its one person", async () => {
    stubApi({ ...BUSINESS, max_users: 1, firm: null }, () =>
      Response.json(BUSINESS)
    )
    render(<Harness />)

    expect(await screen.findByText("Solo plan")).toBeTruthy()
    expect(screen.getByText("1 person")).toBeTruthy()
    expect(screen.queryByText(/seat/)).toBeNull()
    expect(screen.queryByText(/Licensed to/)).toBeNull()
  })

  it("points a lapsed Business license to the renewal check, not to a new file", async () => {
    stubApi(
      { ...BUSINESS, state: "license_expired", expiry: "2026-09-01T00:00:00Z" },
      () => Response.json(BUSINESS)
    )
    const bridge = stubBridge()
    const user = userEvent.setup()
    render(<Harness />)

    const status = await screen.findByRole("status")
    expect(status.textContent).toContain(
      "This license has ended. If it was renewed, Check for renewal fetches the new file."
    )
    expect(status.textContent).not.toContain("new file to add here")
    expect(
      screen.getByRole("button", { name: "Check for renewal" })
    ).toBeTruthy()
    await user.click(within(status).getByRole("link", { name: "See pricing" }))

    expect(bridge.openExternal).toHaveBeenCalledExactlyOnceWith(
      "https://www.surfsense.com/pricing?utm_source=desktop&utm_medium=app&utm_content=license_renew"
    )
  })

  it("shows a job this version cannot name by its code", async () => {
    stubApi({ ...BUSINESS, jobs: ["JOB_QUESTIONNAIRE", "JOB_RFP"] }, () =>
      Response.json(BUSINESS)
    )
    render(<Harness />)

    expect(
      await screen.findByText("Jobs: Security questionnaire and JOB_RFP")
    ).toBeTruthy()
  })

  it("leaves a team license its seats and no renewal check", async () => {
    stubApi({ ...ACTIVE, plan: "team", max_users: 12 }, () =>
      Response.json(ACTIVE)
    )
    render(<Harness />)

    expect(await screen.findByText("Team plan")).toBeTruthy()
    expect(screen.getByText("12 seats")).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Check for renewal" })
    ).toBeNull()
  })

  it("offers the renewal check on a trial that carries jobs", async () => {
    stubApi({ ...ACTIVE, plan: "trial", jobs: ["JOB_QUESTIONNAIRE"] }, () =>
      Response.json(ACTIVE)
    )
    render(<Harness />)

    expect(await screen.findByText("Trial plan")).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Check for renewal" })
    ).toBeTruthy()
  })

  it("fetches the renewed file and shows how long it now runs", async () => {
    const calls = stubApi(
      { ...BUSINESS, expiry: "2026-09-20T00:00:00Z" },
      () => Response.json(BUSINESS),
      () => Response.json({ ...BUSINESS, expiry: "2027-10-10T00:00:00Z" })
    )
    const user = userEvent.setup()
    render(<Harness />)

    expect((await screen.findByRole("status")).textContent).toContain(
      "Expiring soon"
    )
    await user.click(screen.getByRole("button", { name: "Check for renewal" }))

    expect(
      await screen.findByText(/Renewed until (10 Oct 2027|Oct 10, 2027)/)
    ).toBeTruthy()
    expect(screen.getByText(/Expires (10 Oct 2027|Oct 10, 2027)/)).toBeTruthy()
    expect(screen.queryByText("Expiring soon")).toBeNull()
    // The key stays with the backend: the app sends no body.
    expect(calls).toEqual([{ method: "POST", body: null }])
    await waitFor(() =>
      expect(licenseChecks).toEqual(["/plugins/license/check"])
    )
  })

  it("shows a renewal the app’s own daily check stored once the window is shown again", async () => {
    stubApi({ ...BUSINESS, expiry: "2026-09-20T00:00:00Z" }, () =>
      Response.json(BUSINESS)
    )
    render(<Harness />)

    expect((await screen.findByRole("status")).textContent).toContain(
      "Expiring soon"
    )
    // The backend stored the renewed file on its own, with no request from here.
    storedLicense = BUSINESS
    showWindowAgainLater()

    expect(
      await screen.findByText(/Expires (10 Oct 2027|Oct 10, 2027)/)
    ).toBeTruthy()
    expect(screen.queryByText("Expiring soon")).toBeNull()
  })

  it("says when no renewal has come yet", async () => {
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => Response.json(BUSINESS)
    )
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(
      await screen.findByRole("button", { name: "Check for renewal" })
    )

    expect(await screen.findByText("No renewal yet")).toBeTruthy()
  })

  it("holds Replace and Remove until the check answers", async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => new Promise<Response>((resolve) => (answer = resolve))
    )
    const user = userEvent.setup()
    render(<Harness />)
    const held = (name: string) =>
      (screen.getByRole("button", { name }) as HTMLButtonElement).disabled

    await user.click(
      await screen.findByRole("button", { name: "Check for renewal" })
    )

    await waitFor(() => expect(held("Remove license")).toBe(true))
    expect(held("Replace license")).toBe(true)
    answer(Response.json(BUSINESS))
    expect(await screen.findByText("No renewal yet")).toBeTruthy()
    expect(held("Remove license")).toBe(false)
    expect(held("Replace license")).toBe(false)
  })

  it.each([
    ["license_none", 409, "No license is added, so there is none to renew."],
    [
      "refresh_not_found",
      404,
      "SurfSense’s license server has no license with this key.",
    ],
    [
      "refresh_refused",
      403,
      "SurfSense’s license server will not renew this license. Contact support.",
    ],
    [
      "refresh_rate_limited",
      429,
      "This license was checked too often; try again in an hour.",
    ],
    [
      "refresh_unavailable",
      503,
      "SurfSense’s license server could not send a renewed file; try again later.",
    ],
    [
      "refresh_egress_blocked",
      403,
      "Allow SurfSense’s license server, api.surfsense.com, in Settings › Network, then try again.",
    ],
    [
      "bad_signature",
      422,
      "This license file was not issued by SurfSense, or it was altered.",
    ],
  ])(
    "explains %s in the app’s words and keeps the license",
    async (code, status, message) => {
      stubApi(BUSINESS, () => Response.json(BUSINESS), refusal(status, code))
      const user = userEvent.setup()
      render(<Harness />)

      await user.click(
        await screen.findByRole("button", { name: "Check for renewal" })
      )

      expect((await screen.findByRole("alert")).textContent).toBe(message)
      expect(screen.getByText("Business plan")).toBeTruthy()
    }
  )

  it("names the host the backend was refused, such as a firm’s mirror", async () => {
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () =>
        Response.json(
          {
            detail: {
              code: "refresh_egress_blocked",
              message: "The backend’s own words",
              host: "licenses.example.com",
            },
          },
          { status: 403 }
        )
    )
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(
      await screen.findByRole("button", { name: "Check for renewal" })
    )

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Allow SurfSense’s license server, licenses.example.com, in Settings › Network, then try again."
    )
  })
})

describe("Checking for a renewal with the license server off", () => {
  it("asks first, then checks again on Allow", async () => {
    let switched: string[][] = []
    const calls = stubApi(
      { ...BUSINESS, expiry: "2026-09-20T00:00:00Z" },
      () => Response.json(BUSINESS),
      () =>
        switched.length
          ? Response.json(BUSINESS)
          : Response.json(LICENSE_SERVER_OFF, { status: 403 })
    )
    switched = stubEgressSwitch()
    const user = userEvent.setup()
    render(<WithConsent />)

    await user.click(
      await screen.findByRole("button", { name: "Check for renewal" })
    )
    const question = await screen.findByRole("alertdialog", {
      name: "Allow checking for license renewals?",
    })
    // What the host gets, and that Allow also starts the app's own daily check.
    expect(question.textContent).toContain(
      "api.surfsense.com, its license server"
    )
    expect(question.textContent).toContain(
      "sending your license key and your IP address"
    )
    expect(question.textContent).toContain("once a day")
    await user.click(within(question).getByRole("button", { name: "Allow" }))

    expect(
      await screen.findByText(/Renewed until (10 Oct 2027|Oct 10, 2027)/)
    ).toBeTruthy()
    expect(switched).toEqual([["host:api.surfsense.com"]])
    expect(calls).toEqual([
      { method: "POST", body: null },
      { method: "POST", body: null },
    ])
  })

  it("keeps it off on Cancel and says where to allow it", async () => {
    const calls = stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => Response.json(LICENSE_SERVER_OFF, { status: 403 })
    )
    const switched = stubEgressSwitch()
    const user = userEvent.setup()
    render(<WithConsent />)

    await user.click(
      await screen.findByRole("button", { name: "Check for renewal" })
    )
    const question = await screen.findByRole("alertdialog", {
      name: "Allow checking for license renewals?",
    })
    await user.click(within(question).getByRole("button", { name: "Cancel" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Allow SurfSense’s license server, api.surfsense.com, in Settings › Network, then try again."
    )
    expect(switched).toEqual([])
    expect(calls).toEqual([{ method: "POST", body: null }])
  })
})

const INSTALLED: PackDownload = {
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

/** What Settings › License and a Jobs row say for a download a run held back. */
const HELD_BACK = {
  license:
    "A run of Security questionnaire was under way, so any newer version waits until the run ends.",
  row: "A run of Security questionnaire was under way, so any newer version waits. SurfSense checks again once the run ends.",
}

/** The same, for a job whose pack waits on a run of another of its jobs. */
const HELD_BACK_WITH_ITS_PACK = {
  license:
    "Security questionnaire comes in the same pack as a job whose run was under way, so it waits until the run ends.",
  row: "Security questionnaire comes in the same pack as a job whose run was under way, so it waits. SurfSense tries again once the run ends.",
}

/** The download's answer while the license server is off in Settings › Network. */
const JOBS_SERVER_OFF = {
  detail: {
    code: "egress_disabled",
    message: "The backend’s own words",
    destination: "host:api.surfsense.com",
    host: "api.surfsense.com",
    hosts: ["api.surfsense.com"],
    purpose: "job_packs",
  },
}

describe("Jobs on this computer", () => {
  it("lists each job of the license with the version this computer has", async () => {
    stubApi(
      { ...BUSINESS, jobs: ["JOB_QUESTIONNAIRE", "JOB_RFP"] },
      () => Response.json(BUSINESS),
      undefined,
      { packs: [TEST_PACK] }
    )
    render(<Harness />)

    expect(
      await screen.findByRole("heading", { name: "Jobs on this computer" })
    ).toBeTruthy()
    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(screen.getByText("Security questionnaire")).toBeTruthy()
    expect(screen.getByText("JOB_RFP")).toBeTruthy()
    expect(screen.getByText("Not downloaded yet")).toBeTruthy()
    // A job is missing, so the one button downloads.
    expect(screen.getByRole("button", { name: "Download" })).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Import pack file" })
    ).toBeTruthy()
    expect(screen.getByRole("link", { name: "Contact support" })).toBeTruthy()
  })

  it("checks for updates once every job of the license is on this computer", async () => {
    stubApi(BUSINESS, () => Response.json(BUSINESS), undefined, {
      packs: [TEST_PACK],
    })
    render(<Harness />)

    expect(
      await screen.findByRole("button", { name: "Check for updates" })
    ).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull()
  })

  it("downloads the jobs of a license once it is added, asking about the license server first", async () => {
    let switched: string[][] = []
    stubApi(NONE, () => Response.json(BUSINESS), undefined, {
      onDownload: () =>
        switched.length
          ? Response.json(INSTALLED)
          : Response.json(JOBS_SERVER_OFF, { status: 403 }),
    })
    switched = stubEgressSwitch()
    const user = userEvent.setup()
    render(<WithConsent />)

    const dialog = await openAddDialog(user)
    await user.upload(
      within(dialog).getByLabelText("Choose license file"),
      new File([CERTIFICATE], "business.lic", { type: "text/plain" })
    )
    const question = await screen.findByRole("alertdialog", {
      name: "Allow downloading your jobs?",
    })
    await user.click(within(question).getByRole("button", { name: "Allow" }))

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(switched).toEqual([["host:api.surfsense.com"]])
    expect(downloads()).toBe(2)
  })

  it("downloads the license’s jobs again after a renewal check", async () => {
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => Response.json(BUSINESS),
      {
        packs: [TEST_PACK],
        onDownload: () =>
          Response.json({
            outcomes: [{ ...INSTALLED.outcomes[0], version: "0.5.0" }],
            packs: [{ ...TEST_PACK, version: "0.5.0" }],
          }),
      }
    )
    const user = userEvent.setup()
    render(<Harness />)

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Check for renewal" }))

    expect(await screen.findByText("Version 0.5.0")).toBeTruthy()
    expect(downloads()).toBe(1)
  })

  it("holds Replace, Remove and Import while the license’s jobs download", async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi(BUSINESS, () => Response.json(BUSINESS), undefined, {
      onDownload: () => new Promise<Response>((resolve) => (answer = resolve)),
    })
    const user = userEvent.setup()
    render(<Harness />)
    const held = (name: string) =>
      (screen.getByRole("button", { name }) as HTMLButtonElement).disabled

    await user.click(await screen.findByRole("button", { name: "Download" }))

    // A license put in this one's place now would get no download of its own.
    await waitFor(() => expect(held("Replace license")).toBe(true))
    expect(held("Remove license")).toBe(true)
    expect(held("Import pack file")).toBe(true)
    answer(Response.json(INSTALLED))
    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(held("Replace license")).toBe(false)
    expect(held("Remove license")).toBe(false)
    expect(held("Import pack file")).toBe(false)
  })

  it("keeps a download’s line and holds when a renewal check answers during it", async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => Response.json(BUSINESS),
      {
        onDownload: () =>
          new Promise<Response>((resolve) => (answer = resolve)),
      }
    )
    const user = userEvent.setup()
    render(<Harness />)
    const held = (name: string) =>
      (screen.getByRole("button", { name }) as HTMLButtonElement).disabled

    await user.click(await screen.findByRole("button", { name: "Download" }))
    expect(await screen.findByText("Downloading…")).toBeTruthy()
    // The check keeps the same key, so it stays open during a download.
    await user.click(screen.getByRole("button", { name: "Check for renewal" }))

    expect(await screen.findByText("No renewal yet")).toBeTruthy()
    // Publishing the file it fetched forgets finished downloads, not this one,
    // and sends no second download while it is out.
    expect(screen.getByText("Downloading…")).toBeTruthy()
    expect(held("Replace license")).toBe(true)
    expect(held("Remove license")).toBe(true)
    expect(held("Import pack file")).toBe(true)
    expect(downloads()).toBe(1)
    answer(Response.json(INSTALLED))

    expect(await screen.findByText("Version 0.4.3")).toBeTruthy()
    expect(screen.queryByText("Downloading…")).toBeNull()
    expect(held("Replace license")).toBe(false)
    expect(held("Remove license")).toBe(false)
    expect(held("Import pack file")).toBe(false)
    expect(downloads()).toBe(1)
  })

  it("forgets the last download once a renewal check leaves the license ended", async () => {
    const ended: LicenseStatus = {
      ...BUSINESS,
      state: "license_expired",
      expiry: "2026-09-01T00:00:00Z",
    }
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => Response.json(ended),
      {
        onDownload: () =>
          Response.json({
            outcomes: [
              {
                ...INSTALLED.outcomes[0],
                outcome: "license_not_valid",
                message: "The backend’s own words",
                version: null,
                detail: "license_not_valid",
              },
            ],
            packs: [],
          }),
      }
    )
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(await screen.findByRole("button", { name: "Download" }))
    expect((await screen.findByRole("alert")).textContent).toBe(
      "SurfSense’s license server didn’t accept this license, so it sent nothing. Check for renewal in Settings › License, or contact SurfSense support."
    )
    await user.click(screen.getByRole("button", { name: "Check for renewal" }))

    expect(await screen.findByText("No renewal yet")).toBeTruthy()
    // The download's answer was about the license as it stood before the check.
    expect(screen.getByText("Not downloaded yet")).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
    expect(downloads()).toBe(1)
  })

  it("forgets the last download once the license is removed", async () => {
    stubApi(BUSINESS, () => Response.json(BUSINESS), undefined, {
      onDownload: () =>
        Response.json({
          outcomes: [
            {
              ...INSTALLED.outcomes[0],
              outcome: "unavailable",
              message: "The backend’s own words",
              version: null,
            },
          ],
          packs: [],
        }),
    })
    const user = userEvent.setup()
    // The Jobs screen's rows, which say what the same downloads came to.
    render(
      <>
        <Harness />
        <JobList
          workspaceId={1}
          onRun={() => undefined}
          onSettings={() => undefined}
          onOpenRun={() => undefined}
          onOpenLicense={() => undefined}
        />
      </>
    )
    const said =
      "SurfSense’s license server couldn’t send Security questionnaire. Try again later."

    await user.click(await screen.findByRole("button", { name: "Download" }))
    await waitFor(() => expect(screen.getAllByText(said)).toHaveLength(2))
    await user.click(screen.getByRole("button", { name: "Remove license" }))

    expect(await screen.findByText("No license on this device")).toBeTruthy()
    // Every row the catalog sells, the questionnaire's and the redline's, offers a trial.
    expect(
      await screen.findAllByText(
        "Comes with a SurfSense Business license. Try it free for 14 days."
      )
    ).toHaveLength(2)
    expect(screen.queryByText(said)).toBeNull()
  })

  it.each([
    // No version: no pack here has the job. The backend sends this only when
    // the pack that adds the job waits on a run of another of its jobs.
    ["no pack here has the job", null, [], HELD_BACK_WITH_ITS_PACK, HELD_BACK],
    [
      "the version it kept is here",
      "0.4.3",
      [TEST_PACK],
      HELD_BACK,
      HELD_BACK_WITH_ITS_PACK,
    ],
  ])(
    "says why a download waits on a run, here and on the row, when %s",
    async (_, version, packs, said, unsaid) => {
      stubApi(BUSINESS, () => Response.json(BUSINESS), undefined, {
        onDownload: () =>
          Response.json({
            outcomes: [
              { ...INSTALLED.outcomes[0], outcome: "deferred", version },
            ],
            packs,
          }),
      })
      const user = userEvent.setup()
      // The Jobs screen's rows, which say what the same download came to.
      render(
        <>
          <Harness />
          <JobList
            workspaceId={1}
            onRun={() => undefined}
            onSettings={() => undefined}
            onOpenRun={() => undefined}
            onOpenLicense={() => undefined}
          />
        </>
      )

      await user.click(await screen.findByRole("button", { name: "Download" }))

      expect(await screen.findByText(said.license)).toBeTruthy()
      expect(screen.getByText(said.row)).toBeTruthy()
      expect(screen.queryByText(unsaid.license)).toBeNull()
      expect(screen.queryByText(unsaid.row)).toBeNull()
    }
  )

  it("downloads nothing once the license is removed", async () => {
    stubApi(BUSINESS, () => Response.json(BUSINESS), undefined, {
      packs: [TEST_PACK],
    })
    const user = userEvent.setup()
    render(<Harness />)

    await screen.findByText("Version 0.4.3")
    await user.click(screen.getByRole("button", { name: "Remove license" }))

    expect(await screen.findByText("No license on this device")).toBeTruthy()
    expect(
      screen.queryByRole("heading", { name: "Jobs on this computer" })
    ).toBeNull()
    expect(downloads()).toBe(0)
  })

  it("downloads nothing for a license without jobs, and lists none", async () => {
    stubApi(NONE, () => Response.json(ACTIVE))
    const user = userEvent.setup()
    render(<Harness />)

    const dialog = await openAddDialog(user)
    await user.upload(
      within(dialog).getByLabelText("Choose license file"),
      new File([CERTIFICATE], "individual.lic", { type: "text/plain" })
    )

    expect(await screen.findByText("Individual plan")).toBeTruthy()
    expect(
      screen.queryByRole("heading", { name: "Jobs on this computer" })
    ).toBeNull()
    expect(packRequests).toEqual([])
  })

  it.each([
    ["has ended", "license_expired"],
    ["waits for the clock to be set right", "clock_untrusted"],
  ] as const)(
    "offers only the pack file import once the license %s",
    async (_, state) => {
      stubApi({ ...BUSINESS, state }, () => Response.json(BUSINESS))
      render(<Harness />)

      expect(await screen.findByText("Not downloaded yet")).toBeTruthy()
      expect(screen.queryByRole("button", { name: "Download" })).toBeNull()
      expect(
        screen.queryByRole("button", { name: "Check for updates" })
      ).toBeNull()
      expect(
        screen.getByRole("button", { name: "Import pack file" })
      ).toBeTruthy()
    }
  )

  it("holds the jobs’ buttons while the license is being changed", async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi(
      BUSINESS,
      () => Response.json(BUSINESS),
      () => new Promise<Response>((resolve) => (answer = resolve)),
      { packs: [TEST_PACK] }
    )
    const user = userEvent.setup()
    render(<Harness />)
    const held = (name: string) =>
      (screen.getByRole("button", { name }) as HTMLButtonElement).disabled

    await screen.findByRole("button", { name: "Check for updates" })
    await user.click(screen.getByRole("button", { name: "Check for renewal" }))

    await waitFor(() => expect(held("Check for updates")).toBe(true))
    expect(held("Import pack file")).toBe(true)
    answer(Response.json(BUSINESS))
    expect(await screen.findByText("No renewal yet")).toBeTruthy()
    await waitFor(() => expect(held("Import pack file")).toBe(false))
  })

  it("reads again which jobs may run once the license changes", async () => {
    // Whatever shows the jobs on this computer, whose locks follow the license.
    function JobsShown() {
      useJobPacks()
      return null
    }
    stubApi(ACTIVE, () =>
      Response.json({ ...ACTIVE, plan: "team", max_users: 3 })
    )
    const user = userEvent.setup()
    render(
      <>
        <Harness />
        <JobsShown />
      </>
    )

    await waitFor(() => expect(packRequests).toEqual(["GET /job-packs"]))
    await user.click(
      await screen.findByRole("button", { name: "Replace license" })
    )
    await user.upload(
      within(
        screen.getByRole("dialog", { name: /Replace license/ })
      ).getByLabelText("Choose license file"),
      new File([CERTIFICATE], "team.lic", { type: "text/plain" })
    )

    expect(await screen.findByText("Team plan")).toBeTruthy()
    await waitFor(() =>
      expect(packRequests).toEqual(["GET /job-packs", "GET /job-packs"])
    )
  })
})
