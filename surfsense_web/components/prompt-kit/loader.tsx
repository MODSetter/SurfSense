"use client";

import { cn } from "@/lib/utils";

export interface LoaderProps {
	variant?: "text-shimmer";
	size?: "sm" | "md" | "lg";
	text?: string;
	className?: string;
}

const textSizes = {
	sm: "text-xs",
	md: "text-sm",
	lg: "text-base",
} as const;

/**
 * TextShimmerLoader - A text loader with a shimmer gradient animation
 * Used for in-progress states in write_todos and chain-of-thought
 */
export function TextShimmerLoader({
	text = "Thinking",
	className,
	size = "md",
}: {
	text?: string;
	className?: string;
	size?: "sm" | "md" | "lg";
}) {
	return (
		<>
			<style>
				{`
          @keyframes shimmer {
            0% { background-position: 200% 50%; }
            100% { background-position: -200% 50%; }
          }
        `}
			</style>
			<span
				className={cn(
					"bg-[linear-gradient(to_right,var(--muted-foreground)_40%,var(--foreground)_60%,var(--muted-foreground)_80%)]",
					"bg-[length:200%_auto] bg-clip-text font-medium text-transparent",
					"animate-[shimmer_4s_infinite_linear]",
					textSizes[size],
					className
				)}
			>
				{text}
			</span>
		</>
	);
}

/**
 * Loader component - currently only supports text-shimmer variant
 * Can be extended with more variants if needed in the future
 */
export function Loader({ variant = "text-shimmer", size = "md", text, className }: LoaderProps) {
	switch (variant) {
		case "text-shimmer":
		default:
			return <TextShimmerLoader text={text} size={size} className={className} />;
	}
}
