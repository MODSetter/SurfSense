"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SearchSpaceAvatarProps {
	name: string;
	isActive?: boolean;
	onClick?: () => void;
	size?: "sm" | "md";
}

/**
 * Generates a consistent color based on search space name
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1", // indigo
		"#22c55e", // green
		"#f59e0b", // amber
		"#ef4444", // red
		"#8b5cf6", // violet
		"#06b6d4", // cyan
		"#ec4899", // pink
		"#14b8a6", // teal
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from search space name (max 2 chars)
 */
function getInitials(name: string): string {
	const words = name.trim().split(/\s+/);
	if (words.length >= 2) {
		return (words[0][0] + words[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function SearchSpaceAvatar({
	name,
	isActive,
	onClick,
	size = "md",
}: SearchSpaceAvatarProps) {
	const bgColor = stringToColor(name);
	const initials = getInitials(name);
	const sizeClasses = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<button
					type="button"
					onClick={onClick}
					className={cn(
						"flex items-center justify-center rounded-lg font-semibold text-white transition-all",
						"hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
						sizeClasses,
						isActive && "ring-2 ring-primary ring-offset-1 ring-offset-background"
					)}
					style={{ backgroundColor: bgColor }}
				>
					{initials}
				</button>
			</TooltipTrigger>
			<TooltipContent side="right" sideOffset={8}>
				{name}
			</TooltipContent>
		</Tooltip>
	);
}
