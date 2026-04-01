"use client";

import { CheckCircle2, CircleAlert, RefreshCw } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { NavItem } from "../../types/layout.types";
import { SidebarButton } from "./SidebarButton";

interface NavSectionProps {
	items: NavItem[];
	onItemClick?: (item: NavItem) => void;
	isCollapsed?: boolean;
}

function getStatusInfo(status: NavItem["statusIndicator"]) {
	switch (status) {
		case "processing":
			return {
				tooltip: "New or updated documents are still being prepared for search.",
			};
		case "background_sync":
			return {
				pillLabel: "Background sync",
				tooltip:
					"Periodic sync is checking for updates in the background. Existing documents stay searchable while this runs.",
			};
		case "success":
			return {
				tooltip: "All document updates are fully synced.",
			};
		case "error":
			return {
				pillLabel: "Needs attention",
				tooltip: "Some documents failed to sync. Open Documents or Inbox for details.",
			};
		default:
			return {};
	}
}

function StatusPill({ status }: { status: NavItem["statusIndicator"] }) {
	const { pillLabel } = getStatusInfo(status);

	if (!pillLabel) {
		return null;
	}

	return (
		<span className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
			{pillLabel}
		</span>
	);
}

function StatusBadge({ status }: { status: NavItem["statusIndicator"] }) {
	if (status === "processing") {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center h-[14px] w-[14px] rounded-full bg-primary/15">
				<Spinner size="xs" className="text-primary" />
			</span>
		);
	}
	if (status === "background_sync") {
		return (
			<span className="absolute top-0.5 right-0.5 inline-flex items-center justify-center h-[14px] w-[14px] rounded-full bg-primary/15">
				<RefreshCw className="h-[9px] w-[9px] text-primary animate-[spin_3s_linear_infinite]" />
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
	if (status === "background_sync") {
		return (
			<RefreshCw
				className={cn("shrink-0 text-primary animate-[spin_3s_linear_infinite]", className)}
			/>
		);
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
				const { tooltip } = getStatusInfo(item.statusIndicator);

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
						trailingContent={<StatusPill status={item.statusIndicator} />}
						tooltipContent={tooltip}
						buttonProps={joyrideAttr}
					/>
				);
			})}
		</div>
	);
}
