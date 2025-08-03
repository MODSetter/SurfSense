"use client";

import type { LucideIcon } from "lucide-react";
import type * as React from "react";
import { useMemo } from "react";

import {
	SidebarGroup,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";

interface NavSecondaryItem {
	title: string;
	url: string;
	icon: LucideIcon;
}

export function NavSecondary({
	items,
	...props
}: {
	items: NavSecondaryItem[];
} & React.ComponentPropsWithoutRef<typeof SidebarGroup>) {
	// Memoize items to prevent unnecessary re-renders
	const memoizedItems = useMemo(() => items, [items]);

	return (
		<SidebarGroup {...props}>
			<SidebarGroupLabel>SearchSpace</SidebarGroupLabel>
			<SidebarMenu>
				{memoizedItems.map((item, index) => (
					<SidebarMenuItem key={`${item.title}-${index}`}>
						<SidebarMenuButton asChild size="sm" aria-label={item.title}>
							<a href={item.url}>
								<item.icon />
								<span>{item.title}</span>
							</a>
						</SidebarMenuButton>
					</SidebarMenuItem>
				))}
			</SidebarMenu>
		</SidebarGroup>
	);
}
