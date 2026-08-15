"use client";

import { PdfViewer } from "@/components/shared/pdf-viewer";
import { buildBackendUrl } from "@/lib/env-config";
import type { ArtifactFileViewerProps } from "./viewer-registry";

export default function PdfFileViewer({ primary, zoomControlsContainer }: ArtifactFileViewerProps) {
	return (
		<PdfViewer
			pdfUrl={buildBackendUrl(primary.content_url)}
			zoomControlsContainer={zoomControlsContainer}
		/>
	);
}
