/** Data attribute stamped on each deliverable card wrapper by `ArtifactAnchor`. */
export const ARTIFACT_ANCHOR_ATTR = "data-artifact-tool-call-id";

const HIGHLIGHT_CLASSES = ["ring-2", "ring-primary/60"];
const HIGHLIGHT_DURATION_MS = 1600;
const RETRY_INTERVAL_MS = 120;
const MAX_WAIT_MS = 1500;

function isInView(el: HTMLElement): boolean {
	const { top, bottom } = el.getBoundingClientRect();
	return bottom > window.innerHeight * 0.2 && top < window.innerHeight * 0.8;
}

/**
 * Scroll the inline card for `toolCallId` into view and pulse a ring. Retries
 * because the thread viewport's initialize auto-scroll can fire after the first
 * jump and snap back to the bottom; scrolling off-bottom disengages it.
 */
export function scrollToArtifact(toolCallId: string): void {
	if (typeof document === "undefined") return;

	const selector = `[${ARTIFACT_ANCHOR_ATTR}="${CSS.escape(toolCallId)}"]`;
	const deadline = Date.now() + MAX_WAIT_MS;
	let highlighted = false;

	const attempt = () => {
		const anchor = document.querySelector<HTMLElement>(selector);
		if (anchor) {
			anchor.scrollIntoView({ behavior: "smooth", block: "center" });
			if (!highlighted) {
				highlighted = true;
				const card = (anchor.firstElementChild as HTMLElement | null) ?? anchor;
				card.classList.add(...HIGHLIGHT_CLASSES);
				window.setTimeout(() => card.classList.remove(...HIGHLIGHT_CLASSES), HIGHLIGHT_DURATION_MS);
			}
			if (isInView(anchor)) return;
		}
		if (Date.now() < deadline) window.setTimeout(attempt, RETRY_INTERVAL_MS);
	};

	attempt();
}
