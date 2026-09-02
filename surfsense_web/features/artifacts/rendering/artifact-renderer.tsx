"use client";

import { resolveArtifactRenderer } from "@/features/artifacts/lib/artifact-resolution";
import { selectPrimaryArtifactFile } from "@/features/artifacts/lib/artifact-selectors";
import type { ArtifactManifest } from "@/features/artifacts/model/artifact";
import {
	getArtifactRenderer,
	SEMANTIC_RENDERER_FORMATS,
} from "@/features/artifacts/rendering/artifact-renderer-registry";
import { MIME_VIEWER_TYPES } from "./mime-viewer-registry";

export function resolveArtifactPresentation(manifest: ArtifactManifest) {
	const primary = selectPrimaryArtifactFile(manifest);
	const resolution = resolveArtifactRenderer({
		format: manifest.format,
		primaryMimeType: primary?.mime_type,
		hasPrimary: primary !== undefined,
		hasMarkdown: manifest.markdown_representation.trim().length > 0,
		semanticFormats: SEMANTIC_RENDERER_FORMATS,
		mimeTypes: MIME_VIEWER_TYPES,
	});
	return { primary, resolution, renderer: getArtifactRenderer(resolution) };
}

export function ArtifactRenderer({
	manifest,
	workspaceId,
	zoomControlsContainer,
	presentation = resolveArtifactPresentation(manifest),
}: {
	manifest: ArtifactManifest;
	workspaceId: number;
	zoomControlsContainer: HTMLElement | null;
	presentation?: ReturnType<typeof resolveArtifactPresentation>;
}) {
	const { renderer } = presentation;
	const Viewer = renderer.Viewer;
	return (
		<Viewer
			workspaceId={workspaceId}
			manifest={manifest}
			zoomControlsContainer={zoomControlsContainer}
		/>
	);
}
