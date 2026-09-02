import type { ComponentType } from "react";
import type { ArtifactManifest } from "./artifact";

export interface ArtifactRendererProps {
	workspaceId: number;
	manifest: ArtifactManifest;
	zoomControlsContainer: HTMLElement | null;
}

export interface ArtifactRendererActionsProps {
	workspaceId: number;
	manifest: ArtifactManifest;
}

export interface ArtifactRenderer {
	Viewer: ComponentType<ArtifactRendererProps>;
	Actions?: ComponentType<ArtifactRendererActionsProps>;
	downloadable: boolean;
}
