"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/components/ui/cn";
import { browserMayAutoplay } from "./autoplay";
import { trackUseCaseVideo } from "./use-case-events";

/**
 * A use-case video on a marketing page. Nothing loads until it plays
 * (`preload="none"`). It plays muted once most of it is on screen and pauses when it
 * scrolls away; after the visitor pauses it, or once it ends on its result, it stays put.
 * The controls are always there to pause, scrub or replay it.
 */
export function UseCaseVideo({
	slug,
	src,
	poster,
	title,
	placement,
	className,
}: {
	slug: string;
	src: string;
	poster: string;
	title: string;
	placement: string;
	className?: string;
}) {
	const ref = useRef<HTMLVideoElement>(null);
	const started = useRef(false);
	const playingByItself = useRef(false);

	useEffect(() => {
		const video = ref.current;
		if (!video || !browserMayAutoplay()) return;
		let pausingByItself = false;
		let stopped = false;
		const onPause = () => {
			if (!pausingByItself && !video.ended) stopped = true;
			pausingByItself = false;
		};
		const onEnded = () => {
			stopped = true;
		};
		video.addEventListener("pause", onPause);
		video.addEventListener("ended", onEnded);
		const observer = new IntersectionObserver(
			([entry]) => {
				if (stopped) return;
				if (entry.isIntersecting) {
					video.muted = true;
					playingByItself.current = true;
					video.play().catch(() => {
						playingByItself.current = false;
					});
				} else if (!video.paused) {
					pausingByItself = true;
					video.pause();
				}
			},
			{ threshold: 0.6 }
		);
		observer.observe(video);
		return () => {
			observer.disconnect();
			video.removeEventListener("pause", onPause);
			video.removeEventListener("ended", onEnded);
		};
	}, []);

	return (
		<video
			ref={ref}
			className={cn(
				"aspect-[16/10] w-full rounded-2xl border border-border bg-muted shadow-xs",
				className
			)}
			controls
			muted
			playsInline
			preload="none"
			poster={poster}
			aria-label={title}
			onPlay={() => {
				if (started.current) return;
				started.current = true;
				trackUseCaseVideo("started", { slug, placement, autoplay: playingByItself.current });
			}}
			onEnded={() => trackUseCaseVideo("finished", { slug, placement })}
		>
			<source src={src} type="video/mp4" />
		</video>
	);
}
