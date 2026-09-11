import { requestJson } from "@/lib/api"

export type ImportedWorkspace = {
  id: number
  cloud_id: number
  name: string
}

export type ImportAccepted = {
  workspaces: ImportedWorkspace[]
}

export function importBundle(
  file: File,
  signal?: AbortSignal
): Promise<ImportAccepted> {
  const body = new FormData()
  body.append("file", file)
  return requestJson<ImportAccepted>("/migration/import", {
    method: "POST",
    body,
    signal,
  })
}
