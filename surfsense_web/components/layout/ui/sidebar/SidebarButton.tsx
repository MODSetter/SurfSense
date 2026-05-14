"use client";

import type { LucideIcon } from "lucide-react";
import type React from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SidebarButtonProps {
	icon: LucideIcon;
	label: string;
	onClick?: () => void;
	isCollapsed?: boolean;
	isActive?: boolean;
	badge?: React.ReactNode;
	collapsedOverlay?: React.ReactNode;
	collapsedIconNode?: React.ReactNode;
	expandedIconNode?: React.ReactNode;
	trailingContent?: React.ReactNode;
	tooltipContent?: React.ReactNode;
	className?: string;
	buttonProps?: React.ButtonHTMLAttributes<HTMLButtonElement>;
}

const baseClassName = cn(
	"group/sidebar-button relative h-9 justify-start gap-0 rounded-md mx-2 px-2 text-sm text-left",
	"transition-colors hover:bg-accent hover:text-accent-foreground",
	"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
);

export function SidebarButton({
	icon: Icon,
	label,
	onClick,
	isCollapsed = false,
	isActive = false,
	badge,
	collapsedOverlay,
	collapsedIconNode,
	expandedIconNode,
	trailingContent,
	tooltipContent,
	className,
	buttonProps,
}: SidebarButtonProps) {
	const activeClassName = "bg-accent text-accent-foreground";

	const iconNode = isCollapsed
		? (collapsedIconNode ?? <Icon className="h-3.5 w-3.5" />)
		: (expandedIconNode ?? <Icon className="h-3.5 w-3.5 shrink-0" />);

	const button = (
		<Button
			variant="ghost"
			type="button"
			onClick={onClick}
			aria-label={isCollapsed ? label : undefined}
			className={cn(baseClassName, isActive && activeClassName, className)}
			{...buttonProps}
		>
			<span
				className={cn(
					"flex min-w-0 items-center translate-x-0.5 transition-transform duration-200 ease-out",
					isCollapsed ? "shrink-0" : "flex-1"
				)}
			>
				<span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
					{iconNode}
				</span>

				<span
					className={cn(
						"min-w-0 overflow-hidden whitespace-nowrap text-left",
						"transition-[max-width,opacity,margin-left] duration-200 ease-out",
						isCollapsed
							? "max-w-0 opacity-0 ml-0"
							: "max-w-[260px] flex-1 opacity-100 ml-2"
					)}
				>
					<span className="block truncate">{label}</span>
				</span>
			</span>

			{!isCollapsed && trailingContent}
			{!isCollapsed && badge && typeof badge !== "string" ? badge : null}
			{!isCollapsed && badge && typeof badge === "string" ? (
				<span className="ml-1 inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium">
					{badge}
				</span>
			) : null}

			{collapsedOverlay && (
				<span
					aria-hidden={!isCollapsed}
					className={cn(
						"pointer-events-none absolute inset-0 transition-opacity duration-150",
						isCollapsed ? "opacity-100" : "opacity-0"
					)}
				>
					{collapsedOverlay}
				</span>
			)}

			<span className="sr-only">{label}</span>
		</Button>
	);

	const renderTooltip = isCollapsed || !!tooltipContent;
	if (!renderTooltip) {
		return button;
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>{button}</TooltipTrigger>
			<TooltipContent side="right" className="max-w-xs">
				{isCollapsed
					? (tooltipContent ?? (
							<>
								{label}
								{typeof badge === "string" && ` (${badge})`}
							</>
						))
					: tooltipContent}
			</TooltipContent>
		</Tooltip>
	);
}
