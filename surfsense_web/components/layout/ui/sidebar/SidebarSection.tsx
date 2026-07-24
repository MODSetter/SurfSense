"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Collapsible, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface SidebarSectionProps {
	title: string;
	defaultOpen?: boolean;
	children: React.ReactNode;
	action?: React.ReactNode;
	alwaysShowAction?: boolean;
	persistentAction?: React.ReactNode;
	className?: string;
	contentClassName?: string;
	fillHeight?: boolean;
}

export function SidebarSection({
	title,
	defaultOpen = true,
	children,
	action,
	alwaysShowAction = false,
	persistentAction,
	className,
	contentClassName,
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
			<div className="flex items-center group/section shrink-0 pl-4 pr-2.5 py-1">
				<CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-accent-foreground transition-colors min-w-0">
					<span className="truncate">{title}</span>
					<ChevronRight
						className={cn(
							"h-3.5 w-3.5 shrink-0 transition-[color,opacity,transform] duration-200 opacity-100 md:opacity-0 md:group-hover/section:opacity-100",
							isOpen && "rotate-90"
						)}
					/>
				</CollapsibleTrigger>

				{action && (
					<div
						className={cn(
							"transition-opacity ml-1.5 flex items-center",
							alwaysShowAction
								? "opacity-100"
								: "opacity-100 md:opacity-0 md:group-hover/section:opacity-100"
						)}
					>
						{action}
					</div>
				)}

				{persistentAction && (
					<div
						className={cn(
							"shrink-0 ml-auto flex items-center transition-opacity",
							isOpen ? "opacity-100" : "pointer-events-none opacity-0"
						)}
						aria-hidden={!isOpen}
					>
						{persistentAction}
					</div>
				)}
			</div>

			<div
				className={cn(
					"grid flex-1 overflow-hidden transition-opacity duration-200 ease-out",
					isOpen ? "grid-rows-[1fr] opacity-100" : "pointer-events-none grid-rows-[0fr] opacity-0"
				)}
				aria-hidden={!isOpen}
			>
				<div className="min-h-0 overflow-hidden">
					<div
						className={cn("px-2 flex h-full min-h-0 flex-col overflow-hidden", contentClassName)}
					>
						{children}
					</div>
				</div>
			</div>
		</Collapsible>
	);
}
