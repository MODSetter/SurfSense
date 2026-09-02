"use client";

import type { ComponentType } from "react";
import { selectPrimaryArtifactFile } from "@/features/artifacts/lib/artifact-selectors";
import type { ArtifactRenderer, ArtifactRendererProps } from "@/features/artifacts/model/renderer";
import type { FileViewerProps } from "@/features/file-viewers/model";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";

export function createMimeArtifactRenderer(
	FileViewer: ComponentType<FileViewerProps>
): ArtifactRenderer {
	function MimeArtifactRenderer({ manifest, zoomControlsContainer }: ArtifactRendererProps) {
		const primary = selectPrimaryArtifactFile(manifest);
		return primary ? (
			<FileViewer
				primary={primary}
				files={manifest.files}
				zoomControlsContainer={zoomControlsContainer}
			/>
		) : (
			<UnviewableFile message="This artifact has no primary file." />
		);
	}

	return { Viewer: MimeArtifactRenderer, downloadable: true };
}
