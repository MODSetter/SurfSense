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
 * Used for in-progress activity and reasoning states.
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
		<span
			className={cn(
				"bg-[linear-gradient(to_right,var(--muted-foreground)_35%,var(--foreground)_50%,var(--muted-foreground)_65%)]",
				"bg-[length:200%_100%] bg-clip-text font-medium text-transparent",
				"animate-[shimmer-text_1.8s_infinite_linear] motion-reduce:animate-none motion-reduce:text-foreground",
				textSizes[size],
				className
			)}
		>
			{text}
		</span>
	);
}

/**
 * Loader component - currently only supports text-shimmer variant
 * Can be extended with more variants if needed in the future
 */
export function Loader({ size = "md", text, className }: LoaderProps) {
	return <TextShimmerLoader text={text} size={size} className={className} />;
}
