/** Data attribute stamped on each deliverable card wrapper by `ArtifactAnchor`. */
export const ARTIFACT_ANCHOR_ATTR = "data-artifact-tool-call-id";

const HIGHLIGHT_CLASSES = ["ring-1", "ring-primary/60"];
const HIGHLIGHT_DURATION_MS = 1600;
const RETRY_INTERVAL_MS = 120;
const MAX_WAIT_MS = 1500;

interface ScrollToArtifactOptions {
	behavior?: ScrollBehavior;
	highlight?: boolean;
}

function isInView(el: HTMLElement): boolean {
	const { top, bottom } = el.getBoundingClientRect();
	return bottom > window.innerHeight * 0.2 && top < window.innerHeight * 0.8;
}

/**
 * Position the inline card for `toolCallId` and resolve once it remains in view.
 * Retries because assistant-ui's initialize auto-scroll may snap to the bottom
 * after the first jump; moving off-bottom disengages subsequent auto-scroll.
 */
export function scrollToArtifact(
	toolCallId: string,
	{ behavior = "smooth", highlight = true }: ScrollToArtifactOptions = {}
): Promise<void> {
	if (typeof document === "undefined") return Promise.resolve();

	return new Promise((resolve) => {
		const selector = `[${ARTIFACT_ANCHOR_ATTR}="${CSS.escape(toolCallId)}"]`;
		const deadline = Date.now() + MAX_WAIT_MS;
		let highlighted = false;
		let settled = false;

		const finish = () => {
			if (settled) return;
			settled = true;
			resolve();
		};

		const attempt = () => {
			const anchor = document.querySelector<HTMLElement>(selector);
			if (anchor) {
				anchor.scrollIntoView({ behavior, block: "center" });
				if (highlight && !highlighted) {
					highlighted = true;
					const card = (anchor.firstElementChild as HTMLElement | null) ?? anchor;
					card.classList.add(...HIGHLIGHT_CLASSES);
					window.setTimeout(
						() => card.classList.remove(...HIGHLIGHT_CLASSES),
						HIGHLIGHT_DURATION_MS
					);
				}
				if (isInView(anchor)) {
					window.requestAnimationFrame(() => {
						if (isInView(anchor)) finish();
						else if (Date.now() < deadline) window.setTimeout(attempt, RETRY_INTERVAL_MS);
						else finish();
					});
					return;
				}
			}
			if (Date.now() < deadline) window.setTimeout(attempt, RETRY_INTERVAL_MS);
			else finish();
		};

		attempt();
	});
}
