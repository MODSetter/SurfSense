/** Deliverable kinds the agent can produce and surface in the artifacts sidebar. */
export type ArtifactKind = "file" | "podcast" | "video" | "image";

export type ArtifactStatus = "running" | "ready" | "error";

/**
 * A chat deliverable, aggregated from the assistant message stream. One entry
 * per deliverable tool call; the heavy content stays in the inline card and is
 * fetched lazily by the panel/card on demand.
 */
export interface ChatArtifact {
	/** Stable identity for list keys + dedupe — entity id when known, else the tool call id. */
	key: string;
	kind: ArtifactKind;
	title: string;
	/** Canonical persisted format, used for the row subtitle and file fallback. */
	format: string;
	status: ArtifactStatus;
	/** Anchors the scroll-to-card jump back into the conversation. */
	toolCallId: string;
	/** Open / scroll identity — ``artifactId`` when known, else the media row id. */
	entityId: number | null;
	/** Canonical Artifact id, when the tool returned one. */
	artifactId?: number;
	/** Podcast / video row id, when distinct from the Artifact. */
	legacyEntityId?: number;
}

/** Maps deliverable tool names to artifact kinds. Mirrors the body tools in assistant-message. */
export const ARTIFACT_TOOL_KINDS: Record<string, ArtifactKind> = {
	save_artifact: "file",
	generate_podcast: "podcast",
	generate_video_presentation: "video",
	generate_image: "image",
	display_image: "image",
};
