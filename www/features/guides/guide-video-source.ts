import guideVideos from "./guide-videos.json";

/**
 * Where a guide's video plays from and how long it runs. The guide pages and the
 * marketing pages' use-case videos share it.
 */

export type GuideVideoEntry = { src: string; seconds: number };

const VIDEOS: Record<string, GuideVideoEntry> = guideVideos.videos;

/**
 * The Blob store's copy, once scripts/guides/upload-videos.mjs has put it there. In
 * `next dev`, a video not uploaded yet plays the take that
 * scripts/guides/preview-videos.mjs copied into public/guide-videos-local/, which git
 * ignores. A build never does, so a page shows no video until it is hosted.
 */
export function guideVideoSource(slug: string): GuideVideoEntry | undefined {
	const hosted = VIDEOS[slug];
	if (hosted) return hosted;
	if (process.env.NODE_ENV !== "development") return undefined;
	return { src: `/guide-videos-local/${slug}.mp4`, seconds: 0 };
}

/** Each guide's poster sits beside its screenshots. */
export function guidePoster(slug: string): string {
	return `/guides/${slug}/poster.webp`;
}

/** "about 40 seconds" or "about 2 minutes": the videos are short, so a rough length is enough. */
export function roughLength(seconds: number): string {
	if (seconds < 90) return `about ${Math.max(10, Math.round(seconds / 10) * 10)} seconds`;
	const minutes = Math.round(seconds / 60);
	return `about ${minutes} minute${minutes === 1 ? "" : "s"}`;
}
