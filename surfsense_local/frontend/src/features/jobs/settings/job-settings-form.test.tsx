import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { JobSettingsWrite } from "../api"
import { renderJobsDialog } from "../render-jobs-dialog"
import {
  dialogRoutes,
  jobSettings,
  refusal,
  stubJobsApi,
  type Answer,
} from "../stub-jobs-api"

const SETTINGS = "GET /job-packs/jobs/test-questionnaire/settings"
const SAVE = "PUT /job-packs/jobs/test-questionnaire/settings"

function stubSettings(routes: Record<string, Answer> = {}) {
  const saved: JobSettingsWrite[] = []
  stubJobsApi({
    ...dialogRoutes(),
    [SAVE]: (request) => {
      const body = JSON.parse(String(request.body)) as JobSettingsWrite
      saved.push(body)
      return Response.json(
        jobSettings({
          settings: jobSettings().settings.map((setting) => ({
            ...setting,
            value: body.settings[setting.key] ?? setting.default,
          })),
          checker: body.checker,
        })
      )
    },
    ...routes,
  })
  return saved
}

async function openSettings() {
  const user = userEvent.setup()
  renderJobsDialog()
  await user.click(
    await screen.findByRole("button", {
      name: "Security questionnaire settings",
    })
  )
  await screen.findByRole("heading", {
    name: "Security questionnaire settings",
  })
  return user
}

const checker = () =>
  screen.getByRole("combobox", { name: "Second check" }) as HTMLSelectElement

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("job settings form", () => {
  it("shows the pack’s own settings and saves them whole with the checker", async () => {
    const saved = stubSettings()
    const user = await openSettings()

    expect(
      await screen.findByText("A Yes needs a quote from your documents.")
    ).toBeTruthy()
    const save = screen.getByRole("button", {
      name: "Save",
    }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    await user.click(screen.getByRole("switch", { name: "Quote every Yes" }))
    await waitFor(() => expect(checker().disabled).toBe(false))
    await user.selectOptions(checker(), "m")
    await user.click(save)

    expect(await screen.findByText("Saved")).toBeTruthy()
    expect(saved).toEqual([
      {
        settings: { quote_every_yes: true },
        checker: { provider: "openai_compatible", connection_id: 9, name: "m" },
      },
    ])
    expect(
      screen
        .getByRole("switch", { name: "Quote every Yes" })
        .getAttribute("aria-checked")
    ).toBe("true")
  })

  it("offers the answering model and every chat model as the checker", async () => {
    stubSettings()
    await openSettings()

    await waitFor(() => expect(checker().disabled).toBe(false))
    expect(checker().value).toBe("same")
    expect(
      [...checker().options].map((option) => [
        option.parentElement instanceof HTMLOptGroupElement
          ? option.parentElement.label
          : null,
        option.textContent,
      ])
    ).toEqual([
      [null, "The answering model"],
      ["On this computer", "Qwen3 4B"],
      ["OpenRouter", "m"],
    ])
  })

  it("keeps a checker that is no longer available, named as such", async () => {
    const saved = stubSettings({
      [SETTINGS]: jobSettings({
        checker: {
          provider: "openai_compatible",
          connection_id: 5,
          name: "retired-model",
        },
      }),
    })
    const user = await openSettings()

    await waitFor(() =>
      expect(checker().selectedOptions[0]?.textContent).toBe(
        "retired-model (not available now)"
      )
    )
    await user.click(screen.getByRole("switch", { name: "Quote every Yes" }))
    await user.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0].checker).toEqual({
      provider: "openai_compatible",
      connection_id: 5,
      name: "retired-model",
    })
  })

  it("shows why the settings were refused", async () => {
    stubSettings({
      [SAVE]: refusal(
        422,
        "BAD_JOB_SETTINGS",
        "quote_every_yes cannot be set here."
      ),
    })
    const user = await openSettings()

    await user.click(
      await screen.findByRole("switch", { name: "Quote every Yes" })
    )
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect((await screen.findByRole("alert")).textContent).toBe(
      "quote_every_yes cannot be set here."
    )
  })

  it("offers no checker for a job that makes no second check", async () => {
    stubSettings({ [SETTINGS]: jobSettings({ checks: false }) })
    await openSettings()

    expect(
      await screen.findByRole("switch", { name: /Quote every Yes/ })
    ).toBeTruthy()
    expect(screen.queryByRole("combobox", { name: "Second check" })).toBeNull()
  })

  it("says the job is no longer on this computer", async () => {
    stubSettings({
      [SETTINGS]: refusal(
        404,
        "NOT_FOUND",
        'No installed pack has a job "test-questionnaire".'
      ),
    })
    await openSettings()

    expect((await screen.findByRole("alert")).textContent).toBe(
      "This job is no longer on this computer."
    )
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull()
  })
})
