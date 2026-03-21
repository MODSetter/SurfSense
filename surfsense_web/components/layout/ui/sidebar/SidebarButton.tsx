"use client";

import type { LucideIcon } from "lucide-react";
import type React from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SidebarButtonProps {
	icon: LucideIcon;
	label: string;
	onClick?: () => void;
	isCollapsed?: boolean;
	badge?: React.ReactNode;
	/** Overlay in the top-right corner of the collapsed icon (e.g. status badge) */
	collapsedOverlay?: React.ReactNode;
	/** Custom icon node for expanded mode — overrides the default <Icon> rendering */
	expandedIconNode?: React.ReactNode;
	className?: string;
	/** Extra attributes spread onto the inner <button> (e.g. data-joyride) */
	buttonProps?: React.ButtonHTMLAttributes<HTMLButtonElement>;
}

const expandedClassName = cn(
	"flex items-center gap-2 rounded-md mx-2 px-2 py-1.5 text-sm transition-colors text-left",
	"hover:bg-accent hover:text-accent-foreground",
	"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
);

const collapsedClassName = cn(
	"relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
	"hover:bg-accent hover:text-accent-foreground",
	"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
);

export function SidebarButton({
	icon: Icon,
	label,
	onClick,
	isCollapsed = false,
	badge,
	collapsedOverlay,
	expandedIconNode,
	className,
	buttonProps,
}: SidebarButtonProps) {
	if (isCollapsed) {
		return (
			<Tooltip>
				<TooltipTrigger asChild>
					<button
						type="button"
						onClick={onClick}
						className={cn(collapsedClassName, className)}
						{...buttonProps}
					>
						<Icon className="h-4 w-4" />
						{collapsedOverlay}
						<span className="sr-only">{label}</span>
					</button>
				</TooltipTrigger>
				<TooltipContent side="right">
					{label}
					{typeof badge === "string" && ` (${badge})`}
				</TooltipContent>
			</Tooltip>
		);
	}

	return (
		<button
			type="button"
			onClick={onClick}
			className={cn(expandedClassName, className)}
			{...buttonProps}
		>
			{expandedIconNode ?? <Icon className="h-4 w-4 shrink-0" />}
			<span className="flex-1 truncate">{label}</span>
			{badge && typeof badge !== "string" ? badge : null}
			{badge && typeof badge === "string" ? (
				<span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium">
					{badge}
				</span>
			) : null}
		</button>
	);
}
