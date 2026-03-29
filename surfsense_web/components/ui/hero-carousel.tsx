"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ExpandedGifOverlay, useExpandedGif } from "@/components/ui/expanded-gif-overlay";

const carouselItems = [
	{
		title: "Connect & Sync",
		description:
			"Connect data sources like Notion, Drive and Gmail. Automatically sync to keep them updated.",
		src: "/homepage/hero_tutorial/ConnectorFlowGif.mp4",
	},
	{
		title: "Upload Documents",
		description: "Upload documents directly, from images to massive PDFs.",
		src: "/homepage/hero_tutorial/DocUploadGif.mp4",
	},
	{
		title: "Video Generation",
		description: "Create short videos with AI-generated visuals and narration from your sources.",
		src: "/homepage/hero_tutorial/video_gen_surf.mp4",
	},
	{
		title: "Search & Citation",
		description: "Ask questions and get cited responses from your knowledge base.",
		src: "/homepage/hero_tutorial/BSNCGif.mp4",
	},
	{
		title: "Targeted Document Q&A",
		description: "Mention specific documents in chat for targeted answers.",
		src: "/homepage/hero_tutorial/BQnaGif_compressed.mp4",
	},
	{
		title: "Produce Reports Instantly",
		description: "Generate reports from your sources in many formats.",
		src: "/homepage/hero_tutorial/ReportGenGif_compressed.mp4",
	},
	{
		title: "Create Podcasts",
		description: "Turn anything into a podcast in under 20 seconds.",
		src: "/homepage/hero_tutorial/PodcastGenGif.mp4",
	},
	{
		title: "Image Generation",
		description: "Generate high-quality images easily from your conversations.",
		src: "/homepage/hero_tutorial/ImageGenGif.mp4",
	},
	{
		title: "Collaborative AI Chat",
		description: "Collaborate on AI-powered conversations in realtime with your team.",
		src: "/homepage/hero_realtime/RealTimeChatGif.mp4",
	},
	{
		title: "Realtime Comments",
		description: "Add comments and tag teammates on any message.",
		src: "/homepage/hero_realtime/RealTimeCommentsFlow.mp4",
	},
];

function HeroCarouselCard({
	title,
	description,
	src,
	onExpandedChange,
}: {
	title: string;
	description: string;
	src: string;
	onExpandedChange?: (expanded: boolean) => void;
}) {
	const { expanded, open, close } = useExpandedGif();
	const videoRef = useRef<HTMLVideoElement>(null);
	const [hasLoaded, setHasLoaded] = useState(false);

	useEffect(() => {
		onExpandedChange?.(expanded);
	}, [expanded, onExpandedChange]);

	useEffect(() => {
		const video = videoRef.current;
		if (!video) return;

		setHasLoaded(false);
		video.currentTime = 0;

		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					video.play().catch(() => {});
					observer.disconnect();
				}
			},
			{ threshold: 0.1 }
		);
		observer.observe(video);

		return () => observer.disconnect();
	}, []);

	const handleCanPlay = useCallback(() => {
		setHasLoaded(true);
	}, []);

	return (
		<>
			<div className="overflow-hidden rounded-2xl border border-neutral-200/60 bg-white shadow-xl sm:rounded-3xl dark:border-neutral-700/60 dark:bg-neutral-900">
				<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
					<div className="min-w-0">
						<h3 className="truncate text-base font-semibold text-neutral-900 sm:text-xl dark:text-white">
							{title}
						</h3>
						<p className="text-sm text-neutral-500 dark:text-neutral-400">{description}</p>
					</div>
				</div>
				{/* biome-ignore lint/a11y/useSemanticElements: div wraps video element, button would break layout */}
				<div
					role="button"
					tabIndex={0}
					className="cursor-pointer bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950"
					onClick={open}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							open();
						}
					}}
				>
					<div className="relative">
						<video
							ref={videoRef}
							src={src}
							preload="none"
							loop
							muted
							playsInline
							onCanPlay={handleCanPlay}
							className="w-full rounded-lg sm:rounded-xl"
						/>
						{!hasLoaded && (
							<div className="absolute inset-0 aspect-video w-full animate-pulse rounded-lg bg-neutral-100 sm:rounded-xl dark:bg-neutral-800" />
						)}
					</div>
				</div>
			</div>

			<AnimatePresence>
				{expanded && <ExpandedGifOverlay src={src} alt={title} onClose={close} />}
			</AnimatePresence>
		</>
	);
}

function HeroCarousel() {
	const [activeIndex, setActiveIndex] = useState(0);
	const [isGifExpanded, setIsGifExpanded] = useState(false);
	const directionRef = useRef<"forward" | "backward">("forward");

	const goTo = useCallback((newIndex: number) => {
		setActiveIndex((prev) => {
			directionRef.current = newIndex >= prev ? "forward" : "backward";
			return newIndex;
		});
	}, []);

	const goToPrev = useCallback(() => {
		setActiveIndex((prev) => {
			directionRef.current = "backward";
			return prev <= 0 ? carouselItems.length - 1 : prev - 1;
		});
	}, []);

	const goToNext = useCallback(() => {
		setActiveIndex((prev) => {
			directionRef.current = "forward";
			return prev >= carouselItems.length - 1 ? 0 : prev + 1;
		});
	}, []);

	const item = carouselItems[activeIndex];
	const isForward = directionRef.current === "forward";

	return (
		<div className="w-full py-4 sm:py-8">
			<div className="relative mx-auto w-full max-w-[900px]">
				<AnimatePresence mode="wait" initial={false}>
					<motion.div
						key={activeIndex}
						initial={{ opacity: 0, x: isForward ? 60 : -60 }}
						animate={{ opacity: 1, x: 0 }}
						exit={{ opacity: 0, x: isForward ? -60 : 60 }}
						transition={{ duration: 0.35, ease: [0.32, 0.72, 0, 1] }}
					>
						<HeroCarouselCard
							title={item.title}
							description={item.description}
							src={item.src}
							onExpandedChange={setIsGifExpanded}
						/>
					</motion.div>
				</AnimatePresence>
			</div>

			<div className="relative z-5 mt-4 flex items-center justify-center gap-2">
				<button
					type="button"
					onClick={() => !isGifExpanded && goToPrev()}
					className="flex size-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 shadow-sm transition-colors hover:bg-neutral-100 touch-manipulation dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
					aria-label="Previous slide"
				>
					<ChevronLeft className="size-5" />
				</button>

				<div className="flex items-center">
					{carouselItems.map((_, i) => (
						<button
							key={`dot_${i}`}
							type="button"
							onClick={() => !isGifExpanded && goTo(i)}
							className="flex h-11 min-w-[28px] items-center justify-center touch-manipulation"
							aria-label={`Go to slide ${i + 1}`}
						>
							<span
								className={`block h-2.5 rounded-full transition-all duration-300 ${
									i === activeIndex
										? "w-6 bg-neutral-900 dark:bg-white"
										: "w-2.5 bg-neutral-300 hover:bg-neutral-400 dark:bg-neutral-600 dark:hover:bg-neutral-500"
								}`}
							/>
						</button>
					))}
				</div>

				<button
					type="button"
					onClick={() => !isGifExpanded && goToNext()}
					className="flex size-11 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700 shadow-sm transition-colors hover:bg-neutral-100 touch-manipulation dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:bg-neutral-700"
					aria-label="Next slide"
				>
					<ChevronRight className="size-5" />
				</button>
			</div>
		</div>
	);
}

export { HeroCarousel, HeroCarouselCard };
