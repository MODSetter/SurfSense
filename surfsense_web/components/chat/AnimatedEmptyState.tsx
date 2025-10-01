"use client";

import { useInView } from "motion/react";
import { Manrope } from "next/font/google";
import { useEffect, useMemo, useReducer, useRef } from "react";
import { RoughNotation, RoughNotationGroup } from "react-rough-notation";
import { useSidebar } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

// Font configuration - could be moved to a global font config file
const manrope = Manrope({
	subsets: ["latin"],
	weight: ["400", "700"],
	display: "swap", // Optimize font loading
	variable: "--font-manrope",
});

// Constants for timing - makes it easier to adjust and more maintainable
const TIMING = {
	SIDEBAR_TRANSITION: 300, // Wait for sidebar transition + buffer
	LAYOUT_SETTLE: 100, // Small delay to ensure layout is fully settled
} as const;

// Animation configuration
const ANIMATION_CONFIG = {
	HIGHLIGHT: {
		type: "highlight" as const,
		animationDuration: 2000,
		iterations: 3,
		color: "#3b82f680",
		multiline: true,
	},
	UNDERLINE: {
		type: "underline" as const,
		animationDuration: 2000,
		iterations: 3,
		color: "#10b981",
	},
} as const;

// State management with useReducer for better organization
interface HighlightState {
	shouldShowHighlight: boolean;
	layoutStable: boolean;
}

type HighlightAction =
	| { type: "SIDEBAR_CHANGED" }
	| { type: "LAYOUT_STABILIZED" }
	| { type: "SHOW_HIGHLIGHT" }
	| { type: "HIDE_HIGHLIGHT" };

const highlightReducer = (state: HighlightState, action: HighlightAction): HighlightState => {
	switch (action.type) {
		case "SIDEBAR_CHANGED":
			return {
				shouldShowHighlight: false,
				layoutStable: false,
			};
		case "LAYOUT_STABILIZED":
			return {
				...state,
				layoutStable: true,
			};
		case "SHOW_HIGHLIGHT":
			return {
				...state,
				shouldShowHighlight: true,
			};
		case "HIDE_HIGHLIGHT":
			return {
				...state,
				shouldShowHighlight: false,
			};
		default:
			return state;
	}
};

const initialState: HighlightState = {
	shouldShowHighlight: false,
	layoutStable: true,
};

export function AnimatedEmptyState() {
	const ref = useRef<HTMLDivElement>(null);
	const isInView = useInView(ref);
	const [{ shouldShowHighlight, layoutStable }, dispatch] = useReducer(
		highlightReducer,
		initialState
	);

	// Memoize class names to prevent unnecessary recalculations
	const headingClassName = useMemo(
		() =>
			cn(
				"text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50 mb-6",
				manrope.className
			),
		[]
	);

	const paragraphClassName = useMemo(
		() => "text-lg sm:text-xl text-neutral-600 dark:text-neutral-300 mb-8 max-w-2xl mx-auto",
		[]
	);

	// Handle sidebar state changes
	useEffect(() => {
		dispatch({ type: "SIDEBAR_CHANGED" });

		const stabilizeTimer = setTimeout(() => {
			dispatch({ type: "LAYOUT_STABILIZED" });
		}, TIMING.SIDEBAR_TRANSITION);

		return () => clearTimeout(stabilizeTimer);
	}, []);

	// Handle highlight visibility based on layout stability and viewport visibility
	useEffect(() => {
		if (!layoutStable || !isInView) {
			dispatch({ type: "HIDE_HIGHLIGHT" });
			return;
		}

		const showTimer = setTimeout(() => {
			dispatch({ type: "SHOW_HIGHLIGHT" });
		}, TIMING.LAYOUT_SETTLE);

		return () => clearTimeout(showTimer);
	}, [layoutStable, isInView]);

	return (
		<div ref={ref} className="flex-1 flex items-center justify-center w-full min-h-[400px]">
			<div className="max-w-4xl mx-auto px-4 py-10 text-center">
				<RoughNotationGroup show={shouldShowHighlight}>
					<h1 className={headingClassName}>
						<RoughNotation {...ANIMATION_CONFIG.HIGHLIGHT}>
							<span>SurfSense</span>
						</RoughNotation>
					</h1>

					<p className={paragraphClassName}>
						<RoughNotation {...ANIMATION_CONFIG.UNDERLINE}>Let's Start Surfing</RoughNotation>{" "}
						through your knowledge base.
					</p>
				</RoughNotationGroup>
			</div>
		</div>
	);
}
