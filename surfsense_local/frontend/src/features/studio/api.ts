import { apiUrl, requestJson, requestVoid } from "@/lib/api"
import type { DocumentStatus } from "@/features/sources/api"

export type StudioFormat = {
  key: string
  label: string
  requires_roles: ("generation" | "image_generation")[]
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
  options?: PodcastBrief
}

export const PODCAST_STYLES = [
  "conversational",
  "interview",
  "debate",
  "monologue",
  "narrative",
] as const
export const PODCAST_ROLES = [
  "host",
  "cohost",
  "guest",
  "expert",
  "narrator",
] as const
export const PODCAST_DURATIONS = ["short", "standard", "long"] as const
export const MAX_SPEAKERS = 6

export type PodcastSpeaker = {
  name: string
  role: (typeof PODCAST_ROLES)[number]
  voice: string
}

export type PodcastBrief = {
  language: string
  style: (typeof PODCAST_STYLES)[number]
  duration: (typeof PODCAST_DURATIONS)[number]
  speakers: PodcastSpeaker[]
}

export type Voice = { id: string; label: string; language: string }

export function readPodcastBrief(
  workspaceId: number,
  signal?: AbortSignal
): Promise<{ brief: PodcastBrief; voices: Voice[] }> {
  return requestJson(`/workspaces/${workspaceId}/studio/podcast/brief`, {
    signal,
  })
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

export function regenerateArtifact(
  artifactId: number,
  signal?: AbortSignal
): Promise<Artifact> {
  return requestJson<Artifact>(`/artifacts/${artifactId}/regenerate`, {
    method: "POST",
    signal,
  })
}

export function deleteArtifact(
  artifactId: number,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/artifacts/${artifactId}`, { method: "DELETE", signal })
}

// The parsed body of a JSON primary (a flashcard deck, a quiz).
export function readArtifactFile<T>(
  artifactId: number,
  signal?: AbortSignal
): Promise<T> {
  return requestJson<T>(`/artifacts/${artifactId}/files/primary`, { signal })
}

// A plain URL for <a>/<img>/<audio>, which need the absolute sidecar address the
// fetch helper injects itself.
export function fileUrl(
  artifactId: number,
  role: ArtifactFile["role"]
): string {
  return apiUrl(`/artifacts/${artifactId}/files/${role}`)
}
