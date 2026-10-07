import { request, requestJson } from "@/lib/api"
import { parseNdjson } from "@/features/models/local/read-ndjson"

export type OfficeState =
  | "not_installed"
  | "downloading"
  | "unpacking"
  | "checking"
  | "installed"
  | "using_installed"
  | "error"

/** What turning Office support on downloads on this machine. */
export type OfficeOffer = {
  version: string
  /** Bytes. */
  size: number
  host: string
  /** The egress row the download needs allowed. */
  destination: string
}

/** A LibreOffice at a fixed install path; `refusal` says why it cannot be used. */
export type OfficeDetected = {
  path: string
  branch: string | null
  usable: boolean
  refusal: string | null
}

export type OfficeStatus = {
  state: OfficeState
  version: string | null
  path: string | null
  progress: { completed: number; total: number } | null
  /** `code` keys the message shown; `message` is English, for logs. */
  error: { code: string; message: string } | null
  offer: OfficeOffer | null
  detected: OfficeDetected | null
  /** Turned on once, or the thread's offer dismissed: never offered there again. */
  offer_dismissed: boolean
}

export const officeQueryKey = ["runtime-packs", "office"] as const

const OFFICE = "/runtime-packs/office"

export function getOfficeStatus(signal?: AbortSignal): Promise<OfficeStatus> {
  return requestJson<OfficeStatus>(OFFICE, { signal })
}

export function installOffice(): Promise<OfficeStatus> {
  return requestJson<OfficeStatus>(`${OFFICE}/install`, { method: "POST" })
}

export function confirmInstalledOffice(): Promise<OfficeStatus> {
  return requestJson<OfficeStatus>(`${OFFICE}/use-installed`, {
    method: "POST",
  })
}

/** Stops the agent thread offering Office support on this install. */
export function dismissOfficeOffer(): Promise<OfficeStatus> {
  return requestJson<OfficeStatus>(`${OFFICE}/offer/dismiss`, {
    method: "POST",
  })
}

/** Cancels an install that is running, or removes Office support. */
export function removeOffice(): Promise<OfficeStatus> {
  return requestJson<OfficeStatus>(OFFICE, { method: "DELETE" })
}

/** The state now, then again on each change, until `signal` aborts. */
export async function* followOffice(
  signal: AbortSignal
): AsyncGenerator<OfficeStatus> {
  const response = await request(`${OFFICE}/events`, { signal })
  if (!response.body) return
  yield* parseNdjson<OfficeStatus>(response.body)
}
