"use client";

import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ExpandedGifOverlay, useExpandedGif } from "@/components/ui/expanded-gif-overlay";

const carouselItems = [
	{
		title: "Connect & Sync",
		description:
			"Connect data sources like Notion, Drive and Gmail. Automatically sync to keep them updated.",
		src: "/homepage/hero_tutorial/ConnectorFlowGif.gif",
	},
	{
		title: "Upload Documents",
		description: "Upload documents directly, from images to massive PDFs.",
		src: "/homepage/hero_tutorial/DocUploadGif.gif",
	},
	{
		title: "Search & Citation",
		description: "Ask questions and get cited responses from your knowledge base.",
		src: "/homepage/hero_tutorial/BSNCGif.gif",
	},
	{
		title: "Targeted Document Q&A",
		description: "Mention specific documents in chat for targeted answers.",
		src: "/homepage/hero_tutorial/BQnaGif_compressed.gif",
	},
	{
		title: "Produce Reports Instantly",
		description: "Generate reports from your sources in many formats.",
		src: "/homepage/hero_tutorial/ReportGenGif_compressed.gif",
	},
	{
		title: "Create Podcasts",
		description: "Turn anything into a podcast in under 20 seconds.",
		src: "/homepage/hero_tutorial/PodcastGenGif.gif",
	},
	{
		title: "Image Generation",
		description: "Generate high-quality images easily from your conversations.",
		src: "/homepage/hero_tutorial/ImageGenGif.gif",
	},
	{
		title: "Collaborative AI Chat",
		description: "Collaborate on AI-powered conversations in realtime with your team.",
		src: "/homepage/hero_realtime/RealTimeChatGif.gif",
	},
	{
		title: "Realtime Comments",
		description: "Add comments and tag teammates on any message.",
		src: "/homepage/hero_realtime/RealTimeCommentsFlow.gif",
	},
];

function HeroCarouselCard({
	index,
	title,
	description,
	src,
	isActive,
	onExpandedChange,
}: {
	index: number;
	title: string;
	description: string;
	src: string;
	isActive: boolean;
	onExpandedChange?: (expanded: boolean) => void;
}) {
	const { expanded, open, close } = useExpandedGif();

	useEffect(() => {
		onExpandedChange?.(expanded);
	}, [expanded, onExpandedChange]);
	const imgRef = useRef<HTMLImageElement>(null);
	const [frozenFrame, setFrozenFrame] = useState<string | null>(null);
	const [playKey, setPlayKey] = useState(0);

	const captureFrame = useCallback((img: HTMLImageElement) => {
		try {
			const canvas = document.createElement("canvas");
			canvas.width = img.naturalWidth;
			canvas.height = img.naturalHeight;
			canvas.getContext("2d")?.drawImage(img, 0, 0);
			setFrozenFrame(canvas.toDataURL());
		} catch {
			/* cross-origin or other issue */
		}
	}, []);

	useEffect(() => {
		if (isActive) {
			setPlayKey((k) => k + 1);
			setFrozenFrame(null);
		} else {
			const img = imgRef.current;
			if (img && img.complete && img.naturalWidth > 0) {
				captureFrame(img);
			}
		}
	}, [isActive, captureFrame]);

	useEffect(() => {
		if (!isActive && !frozenFrame) {
			const img = new Image();
			img.onload = () => captureFrame(img);
			img.src = src;
		}
	}, [isActive, frozenFrame, src, captureFrame]);

	return (
		<>
			<div className="rounded-2xl border border-neutral-200/60 bg-white shadow-xl sm:rounded-3xl dark:border-neutral-700/60 dark:bg-neutral-900">
				<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
					{/* <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-900 text-xs font-semibold text-white sm:h-8 sm:w-8 sm:text-sm dark:bg-white dark:text-neutral-900">
						{index + 1}
					</span> */}
					<div className="min-w-0">
						<h3 className="truncate text-base font-semibold text-neutral-900 sm:text-xl dark:text-white">
							{title}
						</h3>
						<p className="text-sm text-neutral-500 dark:text-neutral-400">{description}</p>
					</div>
				</div>
				<div
					className={`bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950 ${
						isActive ? "cursor-pointer" : "pointer-events-none"
					}`}
					onClick={isActive ? open : undefined}
				>
					{isActive ? (
						<img
							ref={imgRef}
							key={`gif_${index}_${playKey}`}
							src={src}
							alt={title}
							className="w-full rounded-lg sm:rounded-xl"
						/>
					) : frozenFrame ? (
						<img src={frozenFrame} alt={title} className="w-full rounded-lg sm:rounded-xl" />
					) : (
						<div className="aspect-video w-full rounded-lg bg-neutral-100 sm:rounded-xl dark:bg-neutral-800" />
					)}
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
	const [isPaused, setIsPaused] = useState(false);
	const [isGifExpanded, setIsGifExpanded] = useState(false);
	const [containerWidth, setContainerWidth] = useState(0);
	const [cardHeight, setCardHeight] = useState(420);
	const containerRef = useRef<HTMLDivElement>(null);
	const activeCardRef = useRef<HTMLDivElement>(null);
	const directionRef = useRef<"forward" | "backward">("forward");

	const goTo = useCallback(
		(newIndex: number) => {
			directionRef.current = newIndex >= activeIndex ? "forward" : "backward";
			setActiveIndex(newIndex);
		},
		[activeIndex]
	);

	useEffect(() => {
		const el = containerRef.current;
		if (!el) return;
		const update = () => setContainerWidth(el.offsetWidth);
		update();
		const observer = new ResizeObserver(update);
		observer.observe(el);
		return () => observer.disconnect();
	}, []);

	useEffect(() => {
		const el = activeCardRef.current;
		if (!el) return;
		const update = () => setCardHeight(el.offsetHeight);
		update();
		const observer = new ResizeObserver(update);
		observer.observe(el);
		return () => observer.disconnect();
	}, [activeIndex, containerWidth]);

	useEffect(() => {
		if (isPaused || isGifExpanded) return;
		const timer = setTimeout(() => {
			directionRef.current = "forward";
			setActiveIndex((prev) => (prev >= carouselItems.length - 1 ? 0 : prev + 1));
		}, 8000);
		return () => clearTimeout(timer);
	}, [activeIndex, isPaused, isGifExpanded]);

	const cardWidth =
		containerWidth < 640
			? containerWidth * 0.85
			: containerWidth < 1024
				? Math.min(containerWidth * 0.7, 680)
				: Math.min(containerWidth * 0.55, 900);

	const baseOffset =
		containerWidth < 640
			? containerWidth * 0.2
			: containerWidth < 1024
				? containerWidth * 0.15
				: 150;

	const stackGap = containerWidth < 640 ? 35 : containerWidth < 1024 ? 45 : 55;
	const perspective = containerWidth < 640 ? 800 : containerWidth < 1024 ? 1000 : 1200;

	const getCardStyle = useCallback(
		(index: number) => {
			const diff = index - activeIndex;

			if (diff === 0) {
				const originX = directionRef.current === "forward" ? 1 : 0;
				return { x: -cardWidth / 2, rotateY: 0, zIndex: 20, originX, overlayOpacity: 0, blur: 0 };
			}

			const dist = Math.abs(diff);
			const isLeft = diff < 0;
			const offset = baseOffset + (dist - 1) * stackGap;
			const t = Math.min(1, dist / 3);

			return {
				x: -cardWidth / 2 + (isLeft ? -offset : offset),
				rotateY: isLeft ? 90 : -90,
				zIndex: 20 - dist,
				originX: isLeft ? 0 : 1,
				overlayOpacity: t,
				blur: t * 6,
			};
		},
		[activeIndex, cardWidth, baseOffset, stackGap]
	);

	return (
		<div className="w-full py-4 sm:py-8">
			<div
				ref={containerRef}
				className="relative mx-auto w-full"
				onMouseEnter={() => setIsPaused(true)}
				onMouseLeave={() => setIsPaused(false)}
				onTouchStart={() => setIsPaused(true)}
				onTouchEnd={() => setIsPaused(false)}
			>
				<div
					className="relative z-6 transition-[height] duration-700"
					style={{ perspective: `${perspective}px`, height: cardHeight }}
				>
					{containerWidth > 0 &&
						carouselItems.map((item, i) => {
							const style = getCardStyle(i);
							return (
								<motion.div
									key={`carousel_${i}`}
									ref={i === activeIndex ? activeCardRef : undefined}
									className="absolute top-0"
									style={{
										left: "50%",
										width: cardWidth,
										transformStyle: "preserve-3d",
										zIndex: style.zIndex,
										transformOrigin: `${style.originX * 100}% 50%`,
										cursor: i !== activeIndex ? "pointer" : undefined,
									}}
									onClick={i !== activeIndex && !isGifExpanded ? () => goTo(i) : undefined}
									animate={{
										x: style.x,
										rotateY: style.rotateY,
									}}
									transition={{ duration: 0.7, ease: [0.32, 0.72, 0, 1] }}
								>
									<motion.div
										animate={{ filter: `blur(${style.blur}px)` }}
										transition={{ duration: 0.7, ease: [0.32, 0.72, 0, 1] }}
									>
										<HeroCarouselCard
											index={i}
											title={item.title}
											description={item.description}
											src={item.src}
											isActive={i === activeIndex}
											onExpandedChange={setIsGifExpanded}
										/>
									</motion.div>
									<motion.div
										className="pointer-events-none absolute inset-0 rounded-2xl bg-black sm:rounded-3xl"
										animate={{ opacity: style.overlayOpacity }}
										transition={{ duration: 0.7, ease: [0.32, 0.72, 0, 1] }}
									/>
								</motion.div>
							);
						})}
				</div>
			</div>

			<div className="relative z-5 mt-6 flex justify-center gap-2">
				{carouselItems.map((_, i) => (
					<button
						key={`dot_${i}`}
						type="button"
						onClick={() => !isGifExpanded && goTo(i)}
						className={`h-2 rounded-full transition-all duration-300 ${
							i === activeIndex
								? "w-6 bg-neutral-900 dark:bg-white"
								: "w-2 bg-neutral-300 hover:bg-neutral-400 dark:bg-neutral-600 dark:hover:bg-neutral-500"
						}`}
						aria-label={`Go to slide ${i + 1}`}
					/>
				))}
			</div>
		</div>
	);
}

export { HeroCarousel, HeroCarouselCard };
