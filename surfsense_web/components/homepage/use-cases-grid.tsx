"use client";

import { AnimatePresence, motion } from "motion/react";
import { ExpandedGifOverlay, useExpandedGif } from "@/components/ui/expanded-gif-overlay";

const useCases = [
	{
		title: "Search & Citation",
		description: "Ask questions and get Perplexity-style cited responses from your knowledge base.",
		src: "/homepage/hero_tutorial/BSNCGif.gif",
	},
	{
		title: "Document Mention QNA",
		description: "Mention specific documents in your queries for targeted answers.",
		src: "/homepage/hero_tutorial/BQnaGif_compressed.gif",
	},
	{
		title: "Report Generation",
		description: "Generate and export reports in many formats.",
		src: "/homepage/hero_tutorial/ReportGenGif_compressed.gif",
	},
	{
		title: "Podcast Generation",
		description: "Turn your knowledge into podcasts in under 20 seconds.",
		src: "/homepage/hero_tutorial/PodcastGenGif.gif",
	},
	{
		title: "Image Generation",
		description: "Generate images directly from your conversations.",
		src: "/homepage/hero_tutorial/ImageGenGif.gif",
	},
	{
		title: "Realtime Chat",
		description: "Chat together in realtime with your team.",
		src: "/homepage/hero_realtime/RealTimeChatGif.gif",
	},
	{
		title: "Realtime Comments",
		description: "Add comments and tag teammates on any message.",
		src: "/homepage/hero_realtime/RealTimeCommentsFlow.gif",
	},
];

function UseCaseCard({
	title,
	description,
	src,
	className,
}: {
	title: string;
	description: string;
	src: string;
	className?: string;
}) {
	const { expanded, open, close } = useExpandedGif();

	return (
		<>
			<motion.div
				initial={{ opacity: 0, y: 24 }}
				whileInView={{ opacity: 1, y: 0 }}
				viewport={{ once: true, margin: "-60px" }}
				transition={{ duration: 0.5, ease: "easeOut" }}
				className={`group overflow-hidden rounded-2xl border border-neutral-200/60 bg-white shadow-sm transition-shadow duration-300 hover:shadow-xl dark:border-neutral-700/60 dark:bg-neutral-900 ${className ?? ""}`}
			>
				<div
					className="cursor-pointer overflow-hidden bg-neutral-50 p-2 dark:bg-neutral-950"
					onClick={open}
				>
					<img
						src={src}
						alt={title}
						className="w-full rounded-xl object-cover transition-transform duration-500 group-hover:scale-[1.02]"
					/>
				</div>
				<div className="px-5 py-4">
					<h3 className="text-base font-semibold text-neutral-900 dark:text-white">{title}</h3>
					<p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">{description}</p>
				</div>
			</motion.div>

			<AnimatePresence>
				{expanded && <ExpandedGifOverlay src={src} alt={title} onClose={close} />}
			</AnimatePresence>
		</>
	);
}

export function UseCasesGrid() {
	return (
		<section className="relative mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-8 lg:px-8">
			<div className="mb-6 text-center">
				<h2 className="text-3xl font-semibold tracking-tight text-neutral-900 sm:text-4xl dark:text-white">
					What You Can Do
				</h2>
			</div>

			{/* Row 1: 2 larger cards */}
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				{useCases.slice(0, 2).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			{/* Row 2: 3 equal cards */}
			<div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
				{useCases.slice(2, 5).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			{/* Row 3: 2 cards */}
			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
				{useCases.slice(5).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			<p className="mt-8 text-center text-sm text-neutral-500 dark:text-neutral-400">
				And more coming soon.
			</p>
		</section>
	);
}
