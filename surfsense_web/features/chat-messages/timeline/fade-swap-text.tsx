"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { FC, ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Replaces changing activity copy without moving it. The outgoing text
 * disappears first, then the replacement fades in.
 */
export const FadeSwapText: FC<{
	swapKey: string;
	children: ReactNode;
	className?: string;
	contentClassName?: string;
}> = ({ swapKey, children, className, contentClassName }) => {
	const reducedMotion = useReducedMotion();

	return (
		<span className={cn("inline-grid min-w-0", className)}>
			<AnimatePresence initial={false} mode="wait">
				<motion.span
					key={swapKey}
					className={cn("col-start-1 row-start-1 block min-w-0", contentClassName)}
					initial={reducedMotion ? false : { opacity: 0 }}
					animate={{
						opacity: 1,
						transition: { duration: reducedMotion ? 0 : 0.16, ease: "easeOut" },
					}}
					exit={{
						opacity: 0,
						transition: { duration: reducedMotion ? 0 : 0.1, ease: "easeOut" },
					}}
				>
					{children}
				</motion.span>
			</AnimatePresence>
		</span>
	);
};
