import type { ComponentType } from "react";
import type { ArtifactFile } from "./model";

export interface ArtifactFileViewerProps {
	primary: ArtifactFile;
	files: ArtifactFile[];
}

// Format-specific viewers are added lazily by later phases. Unknown MIME types
// deliberately fall through to FileDownloadCard.
export const VIEWERS: Partial<Record<string, ComponentType<ArtifactFileViewerProps>>> = {};
