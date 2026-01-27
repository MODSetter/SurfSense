"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { NavItem } from "../../types/layout.types";

interface NavSectionProps {
	items: NavItem[];
	onItemClick?: (item: NavItem) => void;
	isCollapsed?: boolean;
}

export function NavSection({ items, onItemClick, isCollapsed = false }: NavSectionProps) {
	return (
		<div className={cn("flex flex-col gap-0.5 py-2", isCollapsed && "items-center")}>
			{items.map((item) => {
				const Icon = item.icon;

				// Add data-joyride for onboarding tour
				const joyrideAttr =
					item.title === "Documents" || item.title.toLowerCase().includes("documents")
						? { "data-joyride": "documents-sidebar" }
						: item.title === "Inbox" || item.title.toLowerCase().includes("inbox")
							? { "data-joyride": "inbox-sidebar" }
							: {};

				if (isCollapsed) {
					return (
						<Tooltip key={item.url}>
							<TooltipTrigger asChild>
								<button
									type="button"
									onClick={() => onItemClick?.(item)}
									className={cn(
										"relative flex h-10 w-10 items-center justify-center rounded-md transition-colors",
										"hover:bg-accent hover:text-accent-foreground",
										"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
									)}
									{...joyrideAttr}
								>
									<Icon className="h-4 w-4" />
									{item.badge && (
										<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center min-w-[14px] h-[14px] px-0.5 rounded-full bg-red-500 text-white text-[9px] font-medium">
											{item.badge}
										</span>
									)}
									<span className="sr-only">{item.title}</span>
								</button>
							</TooltipTrigger>
							<TooltipContent side="right">
								{item.title}
								{item.badge && ` (${item.badge})`}
							</TooltipContent>
						</Tooltip>
					);
				}

				return (
					<button
						key={item.url}
						type="button"
						onClick={() => onItemClick?.(item)}
						className={cn(
							"flex items-center gap-2 rounded-md mx-2 px-2 py-1.5 text-sm transition-colors text-left",
							"hover:bg-accent hover:text-accent-foreground",
							"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						)}
						{...joyrideAttr}
					>
						<Icon className="h-4 w-4 shrink-0" />
						<span className="flex-1 truncate">{item.title}</span>
						{item.badge && (
							<span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium">
								{item.badge}
							</span>
						)}
					</button>
				);
			})}
		</div>
	);
}
