/** Transient tool-result categories used only to reconcile legacy media IDs. */
export type ArtifactToolKind = "file" | "podcast" | "video" | "image";

/** A successful message artifact, optionally enriched from the persisted thread list. */
export interface ChatArtifact {
	/** Stable identity for list keys + dedupe — entity id when known, else the tool call id. */
	key: string;
	title: string;
	/** Message-derived fallback or canonical persisted format. */
	format: string;
	/** Anchors the scroll-to-card jump back into the conversation. */
	toolCallId: string;
	/** Canonical persisted Artifact id, absent for unresolved legacy media jobs. */
	artifactId?: number;
	/** Podcast / video row id, when distinct from the Artifact. */
	legacyEntityId?: number;
	metadataStatus: "pending" | "ready";
}

/** Maps deliverable tool names to artifact kinds. Mirrors the body tools in assistant-message. */
export const ARTIFACT_TOOL_KINDS: Record<string, ArtifactToolKind> = {
	save_artifact: "file",
	generate_podcast: "podcast",
	generate_video_presentation: "video",
	generate_image: "image",
	display_image: "image",
};
