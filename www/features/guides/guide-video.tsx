import guideVideos from "./guide-videos.json";

type GuideVideoEntry = { src: string; seconds: number };

const VIDEOS: Record<string, GuideVideoEntry> = guideVideos.videos;

/**
 * In `next dev`, a guide whose video isn't uploaded yet plays the take that
 * scripts/guides/preview-videos.mjs copied into public/guide-videos-local/,
 * which git ignores. A build never does.
 */
function localTake(slug: string): GuideVideoEntry | undefined {
	if (process.env.NODE_ENV !== "development") return undefined;
	return { src: `/guide-videos-local/${slug}.mp4`, seconds: 0 };
}

/** "about 40 seconds" or "about 2 minutes": the videos are short, so a rough length is enough. */
function roughLength(seconds: number): string {
	if (seconds < 90) return `about ${Math.max(10, Math.round(seconds / 10) * 10)} seconds`;
	const minutes = Math.round(seconds / 60);
	return `about ${minutes} minute${minutes === 1 ? "" : "s"}`;
}

/**
 * A guide's video, above its steps. Nothing loads until the reader presses play
 * (`preload="none"`), so a page of screenshots stays light. The videos have no
 * sound: the caption says so, and the steps below are their text.
 */
export function GuideVideo({
	slug,
	poster,
	title,
}: {
	slug: string;
	poster: string;
	title: string;
}) {
	const video = VIDEOS[slug] ?? localTake(slug);
	if (!video) return null;
	return (
		<figure className="not-prose my-6">
			{/* biome-ignore lint/a11y/useMediaCaption: the videos have no sound to caption; the steps under each one are its text. */}
			<video
				className="aspect-[16/10] w-full rounded-xl border bg-fd-muted"
				controls
				playsInline
				preload="none"
				poster={poster}
				aria-label={title}
			>
				<source src={video.src} type="video/mp4" />
			</video>
			<figcaption className="mt-2 text-sm text-fd-muted-foreground">
				Video{video.seconds ? `, ${roughLength(video.seconds)}` : ""}, no sound. The steps below
				show the same.
			</figcaption>
		</figure>
	);
}
