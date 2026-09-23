import { request, requestJson, requestVoid } from "@/lib/api"

import { parseNdjson } from "../read-ndjson"

export type LocalImageModel = {
  name: string
  label: string
  detail: string
  size_bytes: number
  installed: boolean
  selected: boolean
}

/** `offered` is false where no sd-server shipped for the platform. */
export type LocalImageCatalog = {
  provider: string
  offered: boolean
  ready: boolean
  models: LocalImageModel[]
}

export type DownloadStep = {
  status: string
  completed: number
  total: number
}

export function getLocalImageCatalog(
  signal?: AbortSignal
): Promise<LocalImageCatalog> {
  return requestJson<LocalImageCatalog>("/llm/image/local", { signal })
}

export function deleteLocalImageModel(
  name: string,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/llm/image/local/${encodeURIComponent(name)}`, {
    method: "DELETE",
    signal,
  })
}

export async function installLocalImageModel(
  name: string,
  onStep: (step: DownloadStep) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await request(
    `/llm/image/local/${encodeURIComponent(name)}/install`,
    { method: "POST", signal }
  )
  if (!response.body) throw new Error("The download returned no progress")
  for await (const step of parseNdjson<DownloadStep>(response.body)) {
    onStep(step)
  }
}
