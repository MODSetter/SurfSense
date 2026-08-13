/** Deliverable kinds surfaced in the workspace-wide artifacts library. */
export type LibraryArtifactKind = "file" | "report" | "resume" | "podcast" | "video" | "image";

export type LibraryArtifactStatus = "ready" | "running" | "error";

/**
 * A deliverable aggregated for the library.
 *
 * ``artifactId`` is canonical. ``legacyEntityId`` is the podcast/video row id,
 * still required for Remotion and transcript fallbacks. ``entityId`` is the
 * open id for reports and media without an Artifact.
 */
export interface LibraryArtifact {
	/** Stable list key — `${kind}-${artifactId ?? entityId}`. */
	key: string;
	kind: LibraryArtifactKind;
	/** Legacy or report id used when ``artifactId`` is absent. */
	entityId: number;
	/** Canonical Artifact id when listed from the Artifact API. */
	artifactId?: number;
	/** Podcast / video row id. */
	legacyEntityId?: number;
	title: string;
	status: LibraryArtifactStatus;
	createdAt: string;
	/** Report panel content type — "typst" for resumes, "markdown" otherwise. */
	contentType: "file" | "markdown" | "typst";
	/** Chat thread that produced this artifact, when the source recorded one. */
	sourceThreadId?: number | null;
}
