export function artifactDownloadPath(workspaceId: number, artifactId: number): string {
	return `/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/download`;
}
