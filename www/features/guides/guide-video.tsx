import { guideVideoSource, roughLength } from "./guide-video-source";

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
	const video = guideVideoSource(slug);
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
