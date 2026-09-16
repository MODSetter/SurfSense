"use client";

import { motion, useMotionTemplate, useMotionValue } from "motion/react";
import type React from "react";
import { type MouseEvent as ReactMouseEvent, useState } from "react";
import { CanvasRevealEffect } from "@/components/ui/canvas-reveal-effect";
import { cn } from "@/lib/utils";

export const CardSpotlight = ({
	children,
	radius = 350,
	color = "#262626",
	dotColors = [
		[59, 130, 246],
		[139, 92, 246],
	],
	className,
	...props
}: {
	radius?: number;
	color?: string;
	/** One to three `[r, g, b]` triples for the dot reveal. */
	dotColors?: number[][];
	children: React.ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) => {
	const mouseX = useMotionValue(0);
	const mouseY = useMotionValue(0);
	function handleMouseMove({ currentTarget, clientX, clientY }: ReactMouseEvent<HTMLDivElement>) {
		const { left, top } = currentTarget.getBoundingClientRect();

		mouseX.set(clientX - left);
		mouseY.set(clientY - top);
	}

	const [isHovering, setIsHovering] = useState(false);
	const handleMouseEnter = () => setIsHovering(true);
	const handleMouseLeave = () => setIsHovering(false);
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: vendored as-is from Aceternity UI; the pointer handlers only drive a decorative spotlight, there is no action to expose to keyboard or assistive tech.
		<div
			className={cn(
				"group/spotlight p-10 rounded-md relative border border-neutral-800 bg-black dark:border-neutral-800",
				className
			)}
			onMouseMove={handleMouseMove}
			onMouseEnter={handleMouseEnter}
			onMouseLeave={handleMouseLeave}
			{...props}
		>
			<motion.div
				className="pointer-events-none absolute z-0 -inset-px rounded-md opacity-0 transition duration-300 group-hover/spotlight:opacity-100"
				style={{
					backgroundColor: color,
					maskImage: useMotionTemplate`
            radial-gradient(
              ${radius}px circle at ${mouseX}px ${mouseY}px,
              white,
              transparent 80%
            )
          `,
				}}
			>
				{isHovering && (
					<CanvasRevealEffect
						animationSpeed={5}
						containerClassName="bg-transparent absolute inset-0 pointer-events-none"
						colors={dotColors}
						dotSize={3}
					/>
				)}
			</motion.div>
			{children}
		</div>
	);
};
