/** Deliverable kinds the agent can produce and surface in the artifacts sidebar. */
export type ArtifactKind = "report" | "resume" | "podcast" | "video" | "image";

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
	status: ArtifactStatus;
	/** Anchors the scroll-to-card jump back into the conversation. */
	toolCallId: string;
	/** Backing entity id for report/resume/podcast/video; null for images. */
	entityId: number | null;
	/** Report panel content type — "typst" for resumes, "markdown" otherwise. */
	contentType: "markdown" | "typst";
}

/** Maps deliverable tool names to artifact kinds. Mirrors the body tools in assistant-message. */
export const ARTIFACT_TOOL_KINDS: Record<string, ArtifactKind> = {
	generate_report: "report",
	generate_resume: "resume",
	generate_podcast: "podcast",
	generate_video_presentation: "video",
	generate_image: "image",
	display_image: "image",
};
