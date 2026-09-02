import { artifactDownloadPath } from "@/features/artifacts/api/artifact-download-path";

interface DownloadableDoc {
	id: number;
	title: string;
	document_type: string;
}

interface DownloadTarget {
	path: string;
	filename: string;
}

/**
 * Only uploads keep an ORIGINAL file on disk, and artifacts stream from their own
 * endpoint — every other document type is derived text with no file to hand back.
 */
export function isDownloadableDocumentType(documentType: string): boolean {
	return documentType === "FILE" || documentType === "ARTIFACT";
}

/** Resolve where a document's bytes come from, or null while its artifact is still indexing. */
export function documentDownloadTarget(
	doc: DownloadableDoc,
	workspaceId: number,
	artifact?: { artifact_id: number; format: string }
): DownloadTarget | null {
	if (doc.document_type === "ARTIFACT") {
		if (!artifact) return null;
		return {
			path: artifactDownloadPath(workspaceId, artifact.artifact_id),
			filename: `${doc.title}.${artifact.format}`,
		};
	}
	return {
		path: `/api/v1/documents/${doc.id}/download-original`,
		filename: doc.title,
	};
}
