/** Transient tool-result categories used only to reconcile legacy media IDs. */
export type ArtifactToolKind = "file" | "podcast" | "video" | "image";

/**
 * A successfully persisted chat artifact. In-flight and failed tool calls stay
 * in the conversation and never enter the artifacts panel.
 */
export interface ChatArtifact {
	/** Stable identity for list keys + dedupe — entity id when known, else the tool call id. */
	key: string;
	title: string;
	/** Canonical persisted format, used for the row subtitle. */
	format: string;
	/** Anchors the scroll-to-card jump back into the conversation. */
	toolCallId: string;
	/** Canonical persisted Artifact id. */
	artifactId: number;
	/** Podcast / video row id, when distinct from the Artifact. */
	legacyEntityId?: number;
}

/** Maps deliverable tool names to artifact kinds. Mirrors the body tools in assistant-message. */
export const ARTIFACT_TOOL_KINDS: Record<string, ArtifactToolKind> = {
	save_artifact: "file",
	generate_podcast: "podcast",
	generate_video_presentation: "video",
	generate_image: "image",
	display_image: "image",
};
