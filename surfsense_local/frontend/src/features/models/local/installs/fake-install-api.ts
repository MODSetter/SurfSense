import type { ModelType } from "../../model-type"
import type { InstallEvent } from "../chat/api"
import type { InstallJob } from "./api"

const JOB_PATH = /^\/llm\/installs\/([^/]+)$/

/**
 * Stands in for the API's install jobs, so a test can drive a download the way
 * the server would: start it, move it along, end it. Shared by every surface
 * that downloads.
 */
export function fakeInstallApi({
  labels = {},
  modelTypes = {},
  running = [],
}: {
  /** What the server calls each catalog id's build. */
  labels?: Record<string, string>
  /** The slots each catalog id's model fills; `text_gen` when absent. */
  modelTypes?: Record<string, ModelType[]>
  /** Jobs already going when the screen opens, started elsewhere. */
  running?: InstallJob[]
} = {}) {
  const jobs: InstallJob[] = [...running]
  const started: Record<string, unknown>[] = []
  const feeds = new Set<ReadableStreamDefaultController<Uint8Array>>()
  const encoder = new TextEncoder()

  const frame = () => encoder.encode(`${JSON.stringify({ jobs })}\n`)
  const send = () => {
    for (const feed of feeds) feed.enqueue(frame())
  }

  const move = (event: InstallEvent, jobId = jobs.at(-1)?.id) => {
    const job = jobs.find((known) => known.id === jobId)
    if (!job) throw new Error("no install to move")
    job.event = event
    send()
  }

  const handle = (path: string, init?: RequestInit): Response | null => {
    if (path === "/llm/installs" && init?.method === "POST") {
      const body = JSON.parse(String(init.body)) as {
        catalog_id: string
        select: boolean
        model_type?: ModelType
      }
      started.push(body)
      const job: InstallJob = {
        id: `job-${jobs.length + 1}`,
        catalog_id: body.catalog_id,
        label: labels[body.catalog_id] ?? body.catalog_id,
        model_types: modelTypes[body.catalog_id] ?? ["text_gen"],
        select: body.select,
        model_type: body.model_type ?? null,
        event: { type: "starting", message: "Checking the model" },
      }
      jobs.push(job)
      queueMicrotask(send)
      return Response.json(job, { status: 202 })
    }
    if (path === "/llm/installs/events") {
      return new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            feeds.add(controller)
            controller.enqueue(frame())
            init?.signal?.addEventListener("abort", () => {
              feeds.delete(controller)
              controller.close()
            })
          },
        })
      )
    }
    const cancelled = JOB_PATH.exec(path)
    if (cancelled && init?.method === "DELETE") {
      move(
        { type: "cancelled", message: "Installation cancelled" },
        cancelled[1]
      )
      return new Response(null, { status: 204 })
    }
    return null
  }

  return {
    handle,
    /** Each POST body, in order. */
    started,
    /** The latest job's next event, or `jobId`'s. */
    move,
    complete: (jobId?: string) =>
      move(
        { type: "complete", message: "Model is ready", selection: null },
        jobId
      ),
  }
}
