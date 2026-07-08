"use client";

import { useSelectedLayoutSegments } from "next/navigation";
import type React from "react";
import { useMemo } from "react";
import {
	getPlaygroundNavGroups,
	getPlaygroundNavItems,
	getPlaygroundSelectedLabel,
	RoutedSectionShell,
} from "@/components/layout";

interface PlaygroundLayoutShellProps {
	workspaceId: string;
	children: React.ReactNode;
}

export function PlaygroundLayoutShell({ workspaceId, children }: PlaygroundLayoutShellProps) {
	const segments = useSelectedLayoutSegments();
	const base = `/dashboard/${workspaceId}/playground`;

	const topLevelItems = useMemo(() => getPlaygroundNavItems(base), [base]);
	const providerGroups = useMemo(() => getPlaygroundNavGroups(base), [base]);

	const activeValue =
		segments.length >= 2
			? `${segments[0]}/${segments[1]}`
			: segments[0] && topLevelItems.some((item) => item.value === segments[0])
				? segments[0]
				: "overview";

	const selectedLabel = getPlaygroundSelectedLabel(activeValue, topLevelItems, providerGroups);

	return (
		<RoutedSectionShell
			title="API Playground"
			items={topLevelItems}
			groups={providerGroups}
			activeValue={activeValue}
			selectedLabel={selectedLabel}
			mobileNav="drawer"
			desktopNav={false}
		>
			{children}
		</RoutedSectionShell>
	);
}
