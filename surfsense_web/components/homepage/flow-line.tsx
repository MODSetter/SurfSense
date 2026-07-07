"use client";

import { motion, useReducedMotion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

/** Column centers for the three equal-width step cards (1/6, 1/2, 5/6). */
const NODES = ["16.666%", "50%", "83.333%"];

/**
 * Decorative data-flow line tying the three "How it works" steps together.
 * Sequence on first view: nodes pop in, the line draws left-to-right, then a
 * repeating dash pattern drifts forever to read as data flowing. Uses only
 * transform and background-position; renders statically under reduced motion.
 */
export function FlowLine() {
	const reduce = useReducedMotion() ?? false;

	const dashes = {
		backgroundImage: "repeating-linear-gradient(90deg, currentColor 0 6px, transparent 6px 16px)",
	};

	return (
		<div aria-hidden className="relative mt-8 mb-4 hidden h-3 text-brand md:block">
			{/* Line track between the outer nodes */}
			<div className="absolute top-1/2 left-[16.666%] h-0.5 w-[66.666%] -translate-y-1/2 overflow-hidden rounded-full opacity-70">
				{reduce ? (
					<div className="size-full" style={dashes} />
				) : (
					<motion.div
						className="size-full origin-left"
						initial={{ scaleX: 0 }}
						whileInView={{ scaleX: 1 }}
						viewport={{ once: true, amount: 0.5 }}
						transition={{ duration: 0.7, ease: EASE_OUT, delay: 0.35 }}
					>
						<motion.div
							className="size-full"
							style={dashes}
							animate={{ backgroundPositionX: ["0px", "32px"] }}
							transition={{ duration: 1.6, ease: "linear", repeat: Infinity }}
						/>
					</motion.div>
				)}
			</div>

			{/* Step nodes at each column center */}
			{NODES.map((left, i) => (
				<span
					key={left}
					className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
					style={{ left }}
				>
					{reduce ? (
						<span className="block size-3 rounded-full border-2 border-brand bg-background" />
					) : (
						<motion.span
							className="block size-3 rounded-full border-2 border-brand bg-background"
							initial={{ scale: 0 }}
							whileInView={{ scale: 1 }}
							viewport={{ once: true, amount: 0.5 }}
							transition={{ duration: 0.3, ease: EASE_OUT, delay: 0.1 + i * 0.12 }}
						/>
					)}
				</span>
			))}
		</div>
	);
}
