import posthog from "posthog-js";

/**
 * Two events per use-case video, so a page's downloads can be split by who watched:
 * `use_case_video_started`, with whether it played by itself or the visitor pressed play,
 * and `use_case_video_finished`. PostHog adds the page. `placement` names the section:
 * `home`, `for-page` or `how-it-works`.
 */
export function trackUseCaseVideo(
	step: "started" | "finished",
	properties: { slug: string; placement: string; autoplay?: boolean }
): void {
	try {
		if (!posthog.__loaded) return;
		posthog.capture(`use_case_video_${step}`, properties);
	} catch {
		// Blocked or broken analytics must never stop a video.
	}
}
