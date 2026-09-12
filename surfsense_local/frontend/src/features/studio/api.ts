import { apiUrl, requestJson, requestVoid } from "@/lib/api"
import type { DocumentStatus } from "@/features/sources/api"

export type StudioFormat = {
  key: string
  label: string
  requires_role: "generation" | "image_generation" | null
  available: boolean
  unavailable_reason: string | null
}

export type Artifact = {
  id: number
  document_id: number
  format: string
  generation: number
  title: string
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export type ArtifactFile = {
  role: "primary" | "preview"
  mime_type: string
  size_bytes: number
  original_filename: string
}

export type ArtifactDetail = Artifact & {
  content: string | null
  files: ArtifactFile[]
}

export type StudioJobCreate = {
  format: string
  document_ids: number[]
  prompt?: string
}

export function listFormats(
  workspaceId: number,
  signal?: AbortSignal
): Promise<StudioFormat[]> {
  return requestJson<StudioFormat[]>(
    `/workspaces/${workspaceId}/studio/formats`,
    { signal }
  )
}

export function listArtifacts(
  workspaceId: number,
  signal?: AbortSignal
): Promise<Artifact[]> {
  return requestJson<Artifact[]>(`/workspaces/${workspaceId}/artifacts`, {
    signal,
  })
}

export function createJob(
  workspaceId: number,
  body: StudioJobCreate,
  signal?: AbortSignal
): Promise<Artifact> {
  return requestJson<Artifact>(`/workspaces/${workspaceId}/studio/jobs`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal,
  })
}

export function readArtifact(
  artifactId: number,
  signal?: AbortSignal
): Promise<ArtifactDetail> {
  return requestJson<ArtifactDetail>(`/artifacts/${artifactId}`, { signal })
}

export function deleteArtifact(
  artifactId: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/artifacts/${artifactId}`, { method: "DELETE", signal })
}

// A plain URL for <a>/<img>/<audio>, which need the absolute sidecar address the
// fetch helper injects itself.
export function fileUrl(
  artifactId: number,
  role: ArtifactFile["role"]
): string {
  return apiUrl(`/artifacts/${artifactId}/files/${role}`)
}
