"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FlashcardSurfaceProps {
	front: ReactNode;
	back: ReactNode;
	revealed: boolean;
	onReveal: () => void;
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
			className={cn(
				"absolute inset-0 overflow-y-auto px-6 py-8 sm:px-10 sm:py-12",
				"[backface-visibility:hidden]",
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
	onReveal,
	reducedMotion,
}: FlashcardSurfaceProps) {
	if (reducedMotion) {
		return (
			<div className="relative h-full min-h-64 overflow-hidden rounded-xl border bg-card shadow-sm">
				<div className="h-full overflow-y-auto px-6 py-8 sm:px-10 sm:py-12">
					{revealed ? back : front}
				</div>
				{!revealed ? (
					<button
						type="button"
						onClick={onReveal}
						className="absolute inset-0 cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
						aria-label="Reveal answer"
					/>
				) : null}
			</div>
		);
	}

	return (
		<div className="relative h-full min-h-64 [perspective:1200px]">
			<motion.div
				className="relative h-full rounded-xl border bg-card shadow-sm [transform-style:preserve-3d]"
				animate={{ rotateY: revealed ? 180 : 0 }}
				transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
			>
				<Face hidden={revealed}>{front}</Face>
				<Face hidden={!revealed} className="[transform:rotateY(180deg)]">
					{back}
				</Face>
			</motion.div>
			{!revealed ? (
				<button
					type="button"
					onClick={onReveal}
					className="absolute inset-0 cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
					aria-label="Reveal answer"
				/>
			) : null}
		</div>
	);
}
