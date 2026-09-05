import { beforeEach, describe, expect, it, vi } from "vitest"

import { createWorkspace, listWorkspaces } from "./api"
import { bootstrapWorkspaces } from "./bootstrap"

vi.mock("./api", () => ({
  listWorkspaces: vi.fn(),
  createWorkspace: vi.fn(),
}))

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

beforeEach(() => {
  vi.mocked(listWorkspaces).mockReset()
  vi.mocked(createWorkspace).mockReset()
})

describe("bootstrapWorkspaces", () => {
  it("deduplicates an empty-list bootstrap", async () => {
    let releaseList: ((value: []) => void) | undefined
    vi.mocked(listWorkspaces).mockReturnValue(
      new Promise<[]>((resolve) => {
        releaseList = resolve
      })
    )
    vi.mocked(createWorkspace).mockResolvedValue(workspace)

    const first = bootstrapWorkspaces()
    const second = bootstrapWorkspaces()
    releaseList?.([])

    await expect(Promise.all([first, second])).resolves.toEqual([
      [workspace],
      [workspace],
    ])
    expect(listWorkspaces).toHaveBeenCalledTimes(1)
    expect(createWorkspace).toHaveBeenCalledTimes(1)
    expect(createWorkspace).toHaveBeenCalledWith("My Workspace")
  })
})
