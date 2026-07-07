"use client";

import { History, LayoutGrid } from "lucide-react";
import { useSelectedLayoutSegments } from "next/navigation";
import type React from "react";
import { useMemo } from "react";
import {
	type RoutedSectionGroup,
	type RoutedSectionItem,
	RoutedSectionShell,
} from "@/components/layout";
import { PLAYGROUND_PLATFORMS } from "@/lib/playground/catalog";

interface PlaygroundLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

export function PlaygroundLayoutShell({ workspaceId, children }: PlaygroundLayoutShellProps) {
	const segments = useSelectedLayoutSegments();
	const base = `/dashboard/${workspaceId}/playground`;

	const topLevelItems = useMemo<RoutedSectionItem[]>(
		() => [
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
		],
		[base]
	);

	const providerGroups = useMemo<RoutedSectionGroup[]>(
		() =>
			PLAYGROUND_PLATFORMS.map((platform) => {
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
			}),
		[base]
	);

	const activeValue =
		segments.length >= 2
			? `${segments[0]}/${segments[1]}`
			: segments[0] && topLevelItems.some((item) => item.value === segments[0])
				? segments[0]
				: "overview";

	const selectedLabel = getSelectedLabel(activeValue, topLevelItems, providerGroups);

	return (
		<RoutedSectionShell
			title="API Playground"
			items={topLevelItems}
			groups={providerGroups}
			activeValue={activeValue}
			selectedLabel={selectedLabel}
			mobileNav="drawer"
		>
			{children}
		</RoutedSectionShell>
	);
}

function getSelectedLabel(
	activeValue: string,
	items: RoutedSectionItem[],
	groups: RoutedSectionGroup[]
): string {
	const topLevelItem = items.find((item) => item.value === activeValue);
	if (topLevelItem) return topLevelItem.label;

	const group = groups.find((item) => item.items.some((child) => child.value === activeValue));
	const child = group?.items.find((item) => item.value === activeValue);

	if (group && child) return `${group.label} / ${child.label}`;
	return "API Playground";
}
