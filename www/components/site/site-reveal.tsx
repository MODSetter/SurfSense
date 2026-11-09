"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

/**
 * One quiet scroll reveal per section: fade + small rise, triggered once when
 * the block enters the viewport. Renders statically under prefers-reduced-motion.
 */
export function Reveal({
	children,
	className,
	delay = 0,
}: {
	children: ReactNode;
	className?: string;
	delay?: number;
}) {
	const reduce = useReducedMotion() ?? false;

	if (reduce) {
		return <div className={className}>{children}</div>;
	}

	return (
		<motion.div
			className={className}
			initial={{ opacity: 0, y: 12 }}
			whileInView={{ opacity: 1, y: 0 }}
			viewport={{ once: true, amount: 0.2 }}
			transition={{ duration: 0.28, ease: EASE_OUT, delay }}
		>
			{children}
		</motion.div>
	);
}
