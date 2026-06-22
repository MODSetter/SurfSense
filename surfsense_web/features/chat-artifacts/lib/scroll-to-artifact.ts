/** Data attribute stamped on each deliverable card wrapper by `ArtifactAnchor`. */
export const ARTIFACT_ANCHOR_ATTR = "data-artifact-tool-call-id";

const HIGHLIGHT_CLASSES = ["ring-2", "ring-primary/60"];
const HIGHLIGHT_DURATION_MS = 1600;

/**
 * Scroll the inline card for `toolCallId` into view and pulse a ring so the
 * user can spot it after jumping from the artifacts sidebar. Returns false when
 * the card isn't mounted (e.g. outside the loaded message window).
 */
export function scrollToArtifact(toolCallId: string): boolean {
	if (typeof document === "undefined") return false;

	const anchor = document.querySelector<HTMLElement>(
		`[${ARTIFACT_ANCHOR_ATTR}="${CSS.escape(toolCallId)}"]`
	);
	if (!anchor) return false;

	anchor.scrollIntoView({ behavior: "smooth", block: "start" });

	// The wrapper is full-width; highlight the card itself so the ring hugs its corners.
	const card = (anchor.firstElementChild as HTMLElement | null) ?? anchor;
	card.classList.add(...HIGHLIGHT_CLASSES);
	window.setTimeout(() => card.classList.remove(...HIGHLIGHT_CLASSES), HIGHLIGHT_DURATION_MS);

	return true;
}
