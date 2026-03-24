"use client";

import { CheckCircle2, CircleAlert } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { NavItem } from "../../types/layout.types";
import { SidebarButton } from "./SidebarButton";

interface NavSectionProps {
	items: NavItem[];
	onItemClick?: (item: NavItem) => void;
	isCollapsed?: boolean;
}

function StatusBadge({ status }: { status: NavItem["statusIndicator"] }) {
	if (status === "processing") {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center h-[14px] w-[14px] rounded-full bg-primary/15">
				<Spinner size="xs" className="text-primary" />
			</span>
		);
	}
	if (status === "success") {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center h-[14px] w-[14px] rounded-full bg-emerald-500/15 animate-in fade-in duration-300">
				<CheckCircle2 className="h-[10px] w-[10px] text-emerald-500" />
			</span>
		);
	}
	if (status === "error") {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center h-[14px] w-[14px] rounded-full bg-destructive/15 animate-in fade-in duration-300">
				<CircleAlert className="h-[10px] w-[10px] text-destructive" />
			</span>
		);
	}
	return null;
}

function StatusIcon({
	status,
	FallbackIcon,
	className,
}: {
	status: NavItem["statusIndicator"];
	FallbackIcon: NavItem["icon"];
	className?: string;
}) {
	if (status === "processing") {
		return <Spinner size="sm" className={cn("shrink-0 text-primary", className)} />;
	}
	if (status === "success") {
		return (
			<CheckCircle2
				className={cn("shrink-0 text-emerald-500 animate-in fade-in duration-300", className)}
			/>
		);
	}
	if (status === "error") {
		return (
			<CircleAlert
				className={cn("shrink-0 text-destructive animate-in fade-in duration-300", className)}
			/>
		);
	}
	return <FallbackIcon className={cn("shrink-0", className)} />;
}

function CollapsedOverlay({ item }: { item: NavItem }) {
	const indicator = item.statusIndicator;
	if (indicator && indicator !== "idle") {
		return <StatusBadge status={indicator} />;
	}
	if (item.badge) {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center min-w-[14px] h-[14px] px-0.5 rounded-full bg-red-500 text-white text-[9px] font-medium">
				{item.badge}
			</span>
		);
	}
	return null;
}

export function NavSection({ items, onItemClick, isCollapsed = false }: NavSectionProps) {
	return (
		<div className={cn("flex flex-col gap-0.5 py-2", isCollapsed && "items-center")}>
			{items.map((item) => {
				const joyrideAttr =
					item.title === "Inbox" || item.title.toLowerCase().includes("inbox")
						? { "data-joyride": "inbox-sidebar" as const }
						: {};

				return (
					<SidebarButton
						key={item.url}
						icon={item.icon}
						label={item.title}
						onClick={() => onItemClick?.(item)}
						isCollapsed={isCollapsed}
						isActive={item.isActive}
						badge={item.badge}
						collapsedOverlay={<CollapsedOverlay item={item} />}
						expandedIconNode={
							<StatusIcon
								status={item.statusIndicator}
								FallbackIcon={item.icon}
								className="h-4 w-4"
							/>
						}
						buttonProps={joyrideAttr}
					/>
				);
			})}
		</div>
	);
}
