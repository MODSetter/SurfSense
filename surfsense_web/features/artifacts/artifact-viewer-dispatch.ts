export type ArtifactViewerDispatch =
	| { kind: "mindmap" }
	| { kind: "flashcards" }
	| { kind: "mime"; mimeType: string }
	| { kind: "unviewable" };

export function getArtifactViewerDispatch(
	format: string | null | undefined,
	primaryMimeType: string | null | undefined
): ArtifactViewerDispatch {
	if (format?.trim().toLowerCase() === "mindmap") return { kind: "mindmap" };
	if (format?.trim().toLowerCase() === "flashcards") return { kind: "flashcards" };
	if (primaryMimeType) return { kind: "mime", mimeType: primaryMimeType };
	return { kind: "unviewable" };
}
