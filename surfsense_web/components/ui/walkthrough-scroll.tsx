"use client";

import { AnimatePresence, motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { ExpandedGifOverlay, useExpandedGif } from "@/components/ui/expanded-gif-overlay";

const walkthroughSteps = [
	{
		step: 1,
		title: "Login",
		description: "Login to get started.",
		src: "/homepage/hero_tutorial/LoginFlowGif.gif",
	},
	{
		step: 2,
		title: "Connect & Sync",
		description: "Connect your connectors and sync. Enable periodic syncing to keep them updated.",
		src: "/homepage/hero_tutorial/ConnectorFlowGif.gif",
	},
	{
		step: 3,
		title: "Upload Documents",
		description: "While connectors index, upload your documents directly.",
		src: "/homepage/hero_tutorial/DocUploadGif.gif",
	},
];

function WalkthroughCard({
	i,
	step,
	title,
	description,
	src,
	progress,
	range,
	targetScale,
}: {
	i: number;
	step: number;
	title: string;
	description: string;
	src: string;
	progress: ReturnType<typeof useScroll>["scrollYProgress"];
	range: [number, number];
	targetScale: number;
}) {
	const container = useRef<HTMLDivElement>(null);
	const scale = useTransform(progress, range, [1, targetScale]);
	const { expanded, open, close } = useExpandedGif();

	return (
		<>
			<div
				ref={container}
				className="sticky top-0 flex items-center justify-center px-4 sm:px-6 lg:px-8"
			>
				<motion.div
					style={{
						scale,
						top: `calc(10vh + ${i * 30}px)`,
					}}
					className="relative flex origin-top flex-col overflow-hidden rounded-2xl border border-neutral-200/60 bg-white shadow-xl sm:rounded-3xl dark:border-neutral-700/60 dark:bg-neutral-900
						w-full max-w-[340px] sm:max-w-[520px] md:max-w-[680px] lg:max-w-[900px]"
				>
					<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
						<span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-900 text-xs font-semibold text-white sm:h-8 sm:w-8 sm:text-sm dark:bg-white dark:text-neutral-900">
							{step}
						</span>
						<div className="min-w-0">
							<h3 className="truncate text-sm font-semibold text-neutral-900 sm:text-base dark:text-white">
								{title}
							</h3>
							<p className="hidden text-xs text-neutral-500 sm:block dark:text-neutral-400">
								{description}
							</p>
						</div>
					</div>
					<div
						className="cursor-pointer bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950"
						onClick={open}
					>
						<img src={src} alt={title} className="w-full rounded-lg object-cover sm:rounded-xl" />
					</div>
				</motion.div>
			</div>

			<AnimatePresence>
				{expanded && <ExpandedGifOverlay src={src} alt={title} onClose={close} />}
			</AnimatePresence>
		</>
	);
}

function WalkthroughScroll() {
	const container = useRef<HTMLDivElement>(null);
	const { scrollYProgress } = useScroll({
		target: container,
		offset: ["start start", "end end"],
	});

	return (
		<div
			ref={container}
			className="relative flex w-full flex-col items-center justify-center pb-[15vh] pt-[1vh] sm:pb-[18vh] sm:pt-[2vh]"
		>
			{walkthroughSteps.map((project, i) => {
				const targetScale = Math.max(0.6, 1 - (walkthroughSteps.length - i - 1) * 0.05);
				return (
					<WalkthroughCard
						key={`walkthrough_${i}`}
						i={i}
						{...project}
						progress={scrollYProgress}
						range={[i * (1 / walkthroughSteps.length), 1]}
						targetScale={targetScale}
					/>
				);
			})}
		</div>
	);
}

export { WalkthroughScroll, WalkthroughCard };
