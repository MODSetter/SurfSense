import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider } from "@/components/theme-provider"
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
}

const ACTIVE: LicenseStatus = {
  state: "active",
  plan: "individual",
  email: "ada@example.com",
  expiry: "2027-09-10T00:00:00Z",
  max_users: null,
}

const CERTIFICATE =
  "-----BEGIN LICENSE FILE-----\neyJlbmMiOiJ4In0=\n-----END LICENSE FILE-----\n"

function stubApi(initial: LicenseStatus, onPut: () => Response) {
  let current = initial
  const calls: { method: string; body: unknown }[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = init?.method ?? "GET"
      if (path === "/license/status") return Response.json(current)
      if (path === "/license" && method === "PUT") {
        calls.push({ method, body: JSON.parse(String(init?.body)) })
        const response = onPut()
        if (response.ok)
          current = (await response.clone().json()) as LicenseStatus
        return response
      }
      if (path === "/license" && method === "DELETE") {
        calls.push({ method, body: null })
        current = NONE
        return new Response(null, { status: 204 })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return calls
}

async function openAddDialog(
  user: ReturnType<typeof userEvent.setup>
) {
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
      screen.getByText(/Renews 10 Sept 2027|Renews Sep 10, 2027/)
    ).toBeTruthy()
    expect(calls).toEqual([
      { method: "PUT", body: { certificate: CERTIFICATE } },
    ])
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

    expect(
      screen.getByRole("dialog", { name: /Replace license/ })
    ).toBeTruthy()
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
