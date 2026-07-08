"use client";

import { ChevronRight, History, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { PLAYGROUND_PLATFORMS } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";
import type { RoutedSectionGroup, RoutedSectionItem } from "../RoutedSectionShell";

interface PlaygroundSidebarProps {
	workspaceId: string;
	className?: string;
}

export function getPlaygroundNavItems(base: string): RoutedSectionItem[] {
	return [
		{
			value: "overview",
			label: "Overview",
			href: base,
			icon: <LayoutGrid className="h-4 w-4" />,
		},
		{
			value: "runs",
			label: "API Runs",
			href: `${base}/runs`,
			icon: <History className="h-4 w-4" />,
		},
	];
}

export function getPlaygroundNavGroups(base: string): RoutedSectionGroup[] {
	return PLAYGROUND_PLATFORMS.map((platform) => {
		const Icon = platform.icon;
		return {
			value: platform.id,
			label: platform.label,
			icon: <Icon className="h-4 w-4 shrink-0" />,
			items: platform.verbs.map((verb) => ({
				value: `${platform.id}/${verb.verb}`,
				label: verb.label,
				href: `${base}/${platform.id}/${verb.verb}`,
			})),
		};
	});
}

export function getPlaygroundActiveValue(
	pathname: string | null,
	base: string,
	items: RoutedSectionItem[]
): string {
	if (!pathname?.startsWith(base)) return "";

	const rest = pathname.slice(base.length).replace(/^\/+/, "");
	if (!rest) return "overview";

	const [first, second] = rest.split("/");
	if (second) return `${first}/${second}`;
	if (items.some((item) => item.value === first)) return first;

	return "overview";
}

export function getPlaygroundSelectedLabel(
	activeValue: string,
	items: RoutedSectionItem[],
	groups: RoutedSectionGroup[]
): string {
	const topLevelItem = items.find((item) => item.value === activeValue);
	if (topLevelItem) return topLevelItem.label;

	const group = groups.find((item) => item.items.some((child) => child.value === activeValue));
	const child = group?.items.find((item) => item.value === activeValue);

	if (group && child) return `${group.label}: ${child.label}`;
	return "API Playground";
}

function findActiveGroupValue(groups: RoutedSectionGroup[], activeValue: string): string | null {
	return (
		groups.find((group) => group.items.some((item) => item.value === activeValue))?.value ?? null
	);
}

function PlaygroundNavLink({
	item,
	activeValue,
}: {
	item: RoutedSectionItem;
	activeValue: string;
}) {
	const isActive = activeValue === item.value;

	return (
		<Link
			href={item.href}
			replace
			scroll={false}
			prefetch
			className={cn(
				"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
				isActive
					? "bg-accent text-accent-foreground"
					: "bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground"
			)}
		>
			{item.icon}
			<span className="min-w-0 truncate">{item.label}</span>
		</Link>
	);
}

function PlaygroundNavGroup({
	group,
	activeValue,
	isExpanded,
	onToggle,
}: {
	group: RoutedSectionGroup;
	activeValue: string;
	isExpanded: boolean;
	onToggle: () => void;
}) {
	return (
		<div className="flex flex-col gap-0.5">
			<button
				type="button"
				aria-expanded={isExpanded}
				onClick={onToggle}
				className={cn(
					"inline-flex h-auto items-center justify-start gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:outline-none",
					isExpanded
						? "text-accent-foreground"
						: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
				)}
			>
				{group.icon}
				<span className="min-w-0 truncate">{group.label}</span>
				<ChevronRight
					className={cn("ml-auto h-4 w-4 shrink-0 transition-transform", isExpanded && "rotate-90")}
				/>
			</button>
			<div
				className={cn(
					"grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-out",
					isExpanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
				)}
				aria-hidden={!isExpanded}
			>
				<div className="min-h-0 overflow-hidden">
					<div className="flex flex-col gap-0.5 pl-10">
						{group.items.map((item) => (
							<PlaygroundNavLink key={item.value} item={item} activeValue={activeValue} />
						))}
					</div>
				</div>
			</div>
		</div>
	);
}

export function PlaygroundSidebar({ workspaceId, className }: PlaygroundSidebarProps) {
	const pathname = usePathname();
	const base = `/dashboard/${workspaceId}/playground`;
	const items = useMemo(() => getPlaygroundNavItems(base), [base]);
	const groups = useMemo(() => getPlaygroundNavGroups(base), [base]);
	const activeValue = getPlaygroundActiveValue(pathname, base, items);
	const [expandedGroup, setExpandedGroup] = useState<string | null>(() =>
		findActiveGroupValue(groups, activeValue)
	);

	useEffect(() => {
		const activeGroup = findActiveGroupValue(groups, activeValue);
		if (activeGroup) {
			setExpandedGroup(activeGroup);
		}
	}, [activeValue, groups]);

	return (
		<aside
			className={cn(
				"flex h-full w-[240px] shrink-0 flex-col overflow-hidden border-r bg-panel text-sidebar-foreground select-none",
				className
			)}
		>
			<div className="flex h-12 shrink-0 items-center px-3">
				<h1 className="truncate text-lg font-semibold tracking-tight text-foreground">
					API Playground
				</h1>
			</div>
			<nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4 pt-1.5">
				<div className="flex flex-col gap-0.5">
					{items.map((item) => (
						<PlaygroundNavLink key={item.value} item={item} activeValue={activeValue} />
					))}
					<Separator className="my-3 bg-border" />
					{groups.map((group) => (
						<PlaygroundNavGroup
							key={group.value}
							group={group}
							activeValue={activeValue}
							isExpanded={expandedGroup === group.value}
							onToggle={() =>
								setExpandedGroup((current) => (current === group.value ? null : group.value))
							}
						/>
					))}
				</div>
			</nav>
		</aside>
	);
}
