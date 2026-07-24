/** Deliverable kinds surfaced in the workspace-wide artifacts library. */
export type LibraryArtifactKind = "report" | "resume" | "podcast" | "video" | "image";

export type LibraryArtifactStatus = "ready" | "running" | "error";

/**
 * A deliverable aggregated from the workspace's list endpoints. The heavy
 * content (report body, audio, video frames, image bytes) is fetched lazily by
 * the viewer when a card is opened.
 */
export interface LibraryArtifact {
	/** Stable list key — `${kind}-${entityId}`. */
	key: string;
	kind: LibraryArtifactKind;
	entityId: number;
	title: string;
	status: LibraryArtifactStatus;
	createdAt: string;
	/** Report panel content type — "typst" for resumes, "markdown" otherwise. */
	contentType: "markdown" | "typst";
	/** Chat thread that produced this artifact, when the source recorded one. */
	sourceThreadId?: number | null;
}
