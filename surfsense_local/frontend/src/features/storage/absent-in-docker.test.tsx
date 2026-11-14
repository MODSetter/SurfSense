import { afterEach, describe, expect, it } from "vitest"
import { cleanup } from "@testing-library/react"

import { render } from "@/test-utils"

import { MoveProgressDialog } from "./move-progress-dialog"
import { followMoveProgress } from "./move-progress-state"
import {
  canOpenStorageSettings,
  onStorageSettingsRequested,
} from "./open-storage-settings"

afterEach(cleanup)

// The image's folder is the volume it mounts, and it has no Electron to move anything.
describe("moving folders in the Docker image", { tags: ["docker"] }, () => {
  it("has no bridge to offer it through", () => {
    expect(window.surfsense?.storage).toBeUndefined()
  })

  it("never offers to change the folder from a full-disk message", () => {
    const stop = onStorageSettingsRequested(() => undefined)
    expect(canOpenStorageSettings()).toBe(false)
    stop()
  })

  it("starts up with no progress dialog and nothing to follow", () => {
    const stop = followMoveProgress()
    const { container } = render(<MoveProgressDialog />)
    expect(container.textContent).toBe("")
    stop()
  })
})
