import type { Artifact, ArtifactVersion } from "./api"

export type VersionedArtifact = Artifact & { version: ArtifactVersion }

/** One document in Studio's list: its newest version, and every version it
 *  has, oldest first. An artifact without versions is a line of one. */
export type ArtifactLine = {
  key: string
  newest: Artifact
  versions: Artifact[]
}

// By number; the id only makes the order total.
function byVersion(a: Artifact, b: Artifact) {
  return (a.version?.number ?? 0) - (b.version?.number ?? 0) || a.id - b.id
}

/** The list's rows, each document once, in the order its first artifact in
 *  `artifacts` takes. */
export function artifactLines(artifacts: Artifact[]): ArtifactLine[] {
  const lines = new Map<string, Artifact[]>()
  for (const artifact of artifacts) {
    const key = artifact.version
      ? `root:${artifact.version.root_id}`
      : `artifact:${artifact.id}`
    const members = lines.get(key)
    if (members) members.push(artifact)
    else lines.set(key, [artifact])
  }
  return [...lines].map(([key, members]) => {
    const versions = members.toSorted(byVersion)
    return { key, newest: versions[versions.length - 1], versions }
  })
}

/** Every version of the document `artifactId` belongs to, oldest first;
 *  empty for an artifact with no versions or one not in `artifacts`. */
export function versionsOf(
  artifacts: Artifact[],
  artifactId: number
): VersionedArtifact[] {
  const rootId = artifacts.find((artifact) => artifact.id === artifactId)
    ?.version?.root_id
  if (rootId === undefined) return []
  return artifacts
    .filter(
      (artifact): artifact is VersionedArtifact =>
        artifact.version?.root_id === rootId
    )
    .sort(byVersion)
}

/** The newest version that can be opened, if any has finished. */
export function newestReady<T extends Artifact>(versions: T[]): T | null {
  return versions.findLast((version) => version.status === "ready") ?? null
}
