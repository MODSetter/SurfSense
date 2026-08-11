import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

export function artifactFilePath(workspaceId: number, documentId: number, fileId: number): string {
	return `/api/v1/workspaces/${workspaceId}/documents/${documentId}/files/${fileId}/content`;
}

export function artifactMarkdownPath(workspaceId: number, documentId: number): string {
	return `/api/v1/workspaces/${workspaceId}/documents/${documentId}/download-markdown`;
}

// These endpoints require auth headers, so a plain <a href> would 401: the bytes
// have to come through the app's fetch and be handed to the browser as a blob.
export async function downloadArtifactFile(path: string, filename: string): Promise<void> {
	try {
		const response = await authenticatedFetch(buildBackendUrl(path));
		if (!response.ok) throw new Error("Download failed");
		const url = URL.createObjectURL(await response.blob());
		const anchor = document.createElement("a");
		anchor.href = url;
		anchor.download = filename;
		document.body.appendChild(anchor);
		anchor.click();
		anchor.remove();
		URL.revokeObjectURL(url);
	} catch {
		toast.error("Could not download this artifact");
	}
}
