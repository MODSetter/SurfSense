"use client";

import { PdfViewer } from "@/components/shared/pdf-viewer";
import { cannotPreviewMessage } from "@/features/file-viewers/file-format";
import type { FileViewerProps } from "@/features/file-viewers/model";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { buildBackendUrl } from "@/lib/env-config";

export default function PdfPreviewViewer({
	primary,
	files,
	zoomControlsContainer,
}: FileViewerProps) {
	const preview = files.find((file) => file.role === "preview");
	if (!preview) {
		return <UnviewableFile message={cannotPreviewMessage(primary.filename)} />;
	}
	return (
		<PdfViewer
			pdfUrl={buildBackendUrl(preview.content_url)}
			zoomControlsContainer={zoomControlsContainer}
		/>
	);
}
