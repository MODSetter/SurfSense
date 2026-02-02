"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface SidebarSectionProps {
	title: string;
	defaultOpen?: boolean;
	children: React.ReactNode;
	action?: React.ReactNode;
	persistentAction?: React.ReactNode;
	className?: string;
	fillHeight?: boolean;
}

export function SidebarSection({
	title,
	defaultOpen = true,
	children,
	action,
	persistentAction,
	className,
	fillHeight = false,
}: SidebarSectionProps) {
	const [isOpen, setIsOpen] = useState(defaultOpen);

	return (
		<Collapsible
			open={isOpen}
			onOpenChange={setIsOpen}
			className={cn(
				"overflow-hidden",
				fillHeight && "flex flex-col min-h-0",
				fillHeight && isOpen && "flex-1",
				className
			)}
		>
			<div className="flex items-center group/section shrink-0">
				<CollapsibleTrigger className="flex flex-1 items-center gap-1.5 px-2 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors min-w-0">
					<ChevronRight
						className={cn(
							"h-3.5 w-3.5 shrink-0 transition-transform duration-200",
							isOpen && "rotate-90"
						)}
					/>
					<span className="uppercase tracking-wider truncate">{title}</span>
				</CollapsibleTrigger>

				{/* Action button - visible on hover (always visible on mobile) */}
				{action && (
					<div className="shrink-0 opacity-100 md:opacity-0 md:group-hover/section:opacity-100 transition-opacity pr-1 flex items-center">
						{action}
					</div>
				)}

				{/* Persistent action - always visible */}
				{persistentAction && (
					<div className="shrink-0 pr-1 flex items-center">{persistentAction}</div>
				)}
			</div>

			<CollapsibleContent className={cn("overflow-hidden flex-1 flex flex-col min-h-0")}>
				<div className={cn("px-2 pb-2 flex-1 flex flex-col min-h-0 overflow-hidden")}>
					{children}
				</div>
			</CollapsibleContent>
		</Collapsible>
	);
}
