import { requestJson } from "@/lib/api"

import type { Budget, GpuStatus, LocalRow } from "../chat/api"

/** A model found and not offered, with why: a code and the server's sentence. */
export type Skipped = {
  app: string
  name: string
  path: string
  code: string
  reason: string
}

/**
 * The chat models other apps downloaded on this computer. Every row is priced
 * like any other; using one is an install with its `catalog_id`, which records
 * the file and loads it where it lies, with nothing downloaded.
 */
export type Elsewhere = {
  /** False where nothing outside SurfSense's folders can be read (Docker). */
  available: boolean
  /** Whether other apps' folders are looked in; added folders are either way. */
  look: boolean
  /** The apps whose model folder exists here: what was read. */
  looked_in: string[]
  folders: string[]
  rows: LocalRow[]
  skipped: Skipped[]
  budget: Budget
  gpu_status: GpuStatus
}

const ELSEWHERE = "/llm/catalog/local/elsewhere"

const json = (method: string, body: object): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

export function getElsewhere(signal?: AbortSignal): Promise<Elsewhere> {
  return requestJson<Elsewhere>(ELSEWHERE, { signal })
}

export function setLook(look: boolean): Promise<Elsewhere> {
  return requestJson<Elsewhere>(`${ELSEWHERE}/look`, json("PUT", { look }))
}

/** A file the system's dialog returned, as a row whose Use installs it in place. */
export function offerFile(path: string): Promise<{ row: LocalRow }> {
  return requestJson<{ row: LocalRow }>(
    `${ELSEWHERE}/file`,
    json("POST", { path })
  )
}

export function addFolder(path: string): Promise<Elsewhere> {
  return requestJson<Elsewhere>(`${ELSEWHERE}/folders`, json("POST", { path }))
}

export function removeFolder(path: string): Promise<Elsewhere> {
  return requestJson<Elsewhere>(
    `${ELSEWHERE}/folders`,
    json("DELETE", { path })
  )
}
