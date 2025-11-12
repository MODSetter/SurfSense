"use client";

import { Podcast } from "lucide-react";
import { motion } from "motion/react";

export function PodcastPlayerCompactSkeleton() {
	return (
		<div className="flex flex-col gap-3 p-3">
			{/* Header with icon and title */}
			<div className="flex items-center gap-2">
				<motion.div
					className="w-8 h-8 bg-primary/20 rounded-md flex items-center justify-center flex-shrink-0"
					animate={{ scale: [1, 1.05, 1] }}
					transition={{
						repeat: Infinity,
						duration: 2,
					}}
				>
					<Podcast className="h-4 w-4 text-primary" />
				</motion.div>
				{/* Title skeleton */}
				<div className="h-4 bg-muted rounded w-32 flex-grow animate-pulse" />
			</div>

			{/* Progress bar skeleton */}
			<div className="flex items-center gap-1">
				<div className="h-1 bg-muted rounded flex-grow animate-pulse" />
				<div className="h-4 bg-muted rounded w-12 animate-pulse" />
			</div>

			{/* Controls skeleton */}
			<div className="flex items-center justify-between gap-1">
				<div className="h-7 w-7 bg-muted rounded-full animate-pulse" />
				<div className="h-8 w-8 bg-primary/20 rounded-full animate-pulse" />
				<div className="h-7 w-7 bg-muted rounded-full animate-pulse" />
				<div className="h-7 w-7 bg-muted rounded-full animate-pulse" />
			</div>
		</div>
	);
}
