import { describe, expect, it } from "vitest"

import { installView } from "./install-view"

describe("install progress", () => {
  it("reports a finished download as finished", () => {
    // Not scaled into a share of the whole install: the download really is
    // done, and saying 80% at the moment it completes is a number nobody can
    // reconcile with the byte count beside it.
    const view = installView({
      type: "downloading",
      completed: 1000,
      total: 1000,
    })

    expect(view.percent).toBe(100)
  })

  it("moves while the runtime loads the weights", () => {
    // The second wait is tens of seconds. Before the runtime reported its own
    // progress there was no number for it, and a bar that holds still for that
    // long is indistinguishable from one that has hung.
    const early = installView({ type: "preparing", progress: 0 }).percent
    const late = installView({ type: "preparing", progress: 0.8 }).percent

    expect(late).toBeGreaterThan(early ?? 0)
  })

  it("says it has no figure rather than reporting zero", () => {
    // Absent progress is not no progress. Rendering it as 0% drains the bar,
    // which is the difference between "still working" and "lost your place".
    expect(installView({ type: "preparing" }).percent).toBeNull()
    expect(installView({ type: "verifying" }).percent).toBeNull()
  })

  it("says a download waits its turn rather than looking stuck", () => {
    // One download runs at a time. A model chosen while another downloads
    // queues behind it, and the button says so instead of "Starting…" for as
    // long as the first one takes.
    const view = installView({
      type: "queued",
      message: "Waiting for the download ahead of it",
    })

    expect(view.short).toBe("Waiting…")
    expect(view.label).toBe("Waiting for the download ahead of it")
    expect(view.percent).toBeNull()
  })

  it("names the phase in one word, for somewhere with no room", () => {
    // The button carries this. A percentage there would resize it, and the row
    // with it, on every frame. A phase still under way trails an ellipsis; a
    // finished one does not.
    expect(installView({ type: "starting" }).short).toBe("Starting…")
    expect(
      installView({ type: "downloading", completed: 1, total: 2 }).short
    ).toBe("Downloading…")
    expect(installView({ type: "preparing", progress: 0.2 }).short).toBe(
      "Preparing…"
    )
    expect(installView({ type: "verifying" }).short).toBe("Verifying…")
    expect(installView({ type: "selecting" }).short).toBe("Selecting…")
    expect(
      installView({
        type: "complete",
        selection: {
          model_type: "text_gen",
          provider: "llamacpp",
          connection_id: null,
          name: "m",
          updated_at: "",
        },
      }).short
    ).toBe("Done")
    expect(installView({ type: "error", message: "x" }).short).toBe("Failed")
  })

  it("prefers the server's own wording for the line under it", () => {
    // The server names the stage being loaded, including ones this build has
    // never seen, so the copy is not duplicated here.
    const view = installView({
      type: "preparing",
      message: "Loading image support",
      progress: 0.4,
    })

    expect(view.label).toBe("Loading image support")
  })
})
