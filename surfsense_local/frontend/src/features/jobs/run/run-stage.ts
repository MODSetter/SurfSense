import type { DocumentStatus } from "@/features/sources/api"

import type { RunProgress } from "../api"

export const isRunning = (
  status: DocumentStatus
): status is "pending" | "processing" =>
  status === "pending" || status === "processing"

/** How far a run has got. Until the first answer, it is reading: its file, then
 *  the documents it reads, which takes minutes and answers nothing. */
export type RunStage =
  | { name: "waiting" }
  | { name: "reading_file" }
  | { name: "reading"; total: number }
  | { name: "answering"; done: number; total: number }
  | { name: "writing" }
  | { name: "ready" }
  | { name: "failed" }
  | { name: "cancelled" }

export function runStage(
  status: DocumentStatus,
  progress: RunProgress | null
): RunStage {
  if (status === "pending") return { name: "waiting" }
  if (status !== "processing") return { name: status }
  if (progress === null) return { name: "reading_file" }
  if (progress.done === 0) return { name: "reading", total: progress.total }
  if (progress.done < progress.total)
    return { name: "answering", done: progress.done, total: progress.total }
  return { name: "writing" }
}
