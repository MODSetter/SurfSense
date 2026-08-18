"use client";

import { PdfViewer } from "@/components/shared/pdf-viewer";
import { buildBackendUrl } from "@/lib/env-config";
import type { FileViewerProps } from "./model";

export default function PdfFileViewer({ primary, zoomControlsContainer }: FileViewerProps) {
	return (
		<PdfViewer
			pdfUrl={buildBackendUrl(primary.content_url)}
			zoomControlsContainer={zoomControlsContainer}
		/>
	);
}
