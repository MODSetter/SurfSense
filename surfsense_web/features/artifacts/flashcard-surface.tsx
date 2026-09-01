"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FlashcardSurfaceProps {
	front: ReactNode;
	back: ReactNode;
	revealed: boolean;
	onFlip: () => void;
	reducedMotion: boolean;
}

function Face({
	children,
	hidden,
	className,
}: {
	children: ReactNode;
	hidden: boolean;
	className?: string;
}) {
	return (
		<div
			aria-hidden={hidden}
			inert={hidden}
			style={{
				backfaceVisibility: "hidden",
				WebkitBackfaceVisibility: "hidden",
			}}
			className={cn(
				"absolute inset-0 overflow-y-auto rounded-2xl bg-white px-6 py-8 text-black sm:px-10 sm:py-12",
				className
			)}
		>
			{children}
		</div>
	);
}

export function FlashcardSurface({
	front,
	back,
	revealed,
	onFlip,
	reducedMotion,
}: FlashcardSurfaceProps) {
	if (reducedMotion) {
		return (
			<div className="relative h-full overflow-hidden rounded-2xl bg-white text-black shadow-[0_0_2.5rem_0_rgb(0_0_0/0.16)]">
				<div className="h-full overflow-y-auto px-6 py-8 sm:px-10 sm:py-12">
					{revealed ? back : front}
				</div>
				<button
					type="button"
					onClick={onFlip}
					className="absolute inset-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
					aria-label={revealed ? "Show question" : "Reveal answer"}
				/>
			</div>
		);
	}

	return (
		<div className="relative h-full [perspective:9000px]">
			<motion.div
				className="relative h-full rounded-2xl bg-transparent shadow-[0_0_2.5rem_0_rgb(0_0_0/0.16)] [transform-style:preserve-3d]"
				animate={{ rotateY: revealed ? 180 : 0 }}
				transition={{ duration: 0.45, ease: "easeInOut" }}
			>
				<Face hidden={revealed}>{front}</Face>
				<Face hidden={!revealed} className="[transform:rotateY(180deg)]">
					{back}
				</Face>
			</motion.div>
			<button
				type="button"
				onClick={onFlip}
				className="absolute inset-0 cursor-pointer rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
				aria-label={revealed ? "Show question" : "Reveal answer"}
			/>
		</div>
	);
}
