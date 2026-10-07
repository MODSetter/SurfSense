export const studioKeys = {
  all: ["studio"] as const,
  formats: (workspaceId: number, selectionToken: string) =>
    [...studioKeys.all, "formats", workspaceId, selectionToken] as const,
  artifacts: (workspaceId: number) =>
    [...studioKeys.all, "artifacts", workspaceId] as const,
  // Everything read for open artifacts, so one event refreshes them all.
  openArtifacts: () => [...studioKeys.all, "artifact"] as const,
  artifact: (artifactId: number) =>
    [...studioKeys.openArtifacts(), artifactId] as const,
}
