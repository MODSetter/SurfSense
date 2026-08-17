"use client";

import { useQuery } from "@tanstack/react-query";
import { documentViewQueryOptions } from "@/features/documents/viewer/document-view-query";
import { DownloadFileButton } from "@/features/file-viewers/download-file-button";

interface DownloadOriginalButtonProps {
	documentId: number;
	workspaceId: number;
}

/** Renders only when the document has a stored ORIGINAL file; downloads it on click. */
export function DownloadOriginalButton({ documentId, workspaceId }: DownloadOriginalButtonProps) {
	const { data: manifest } = useQuery(documentViewQueryOptions(workspaceId, documentId));
	const file = manifest?.file;
	if (!file) return null;

	return (
		<DownloadFileButton
			path={`/api/v1/documents/${documentId}/download-original`}
			filename={file.filename}
			className="size-6"
		/>
	);
}
