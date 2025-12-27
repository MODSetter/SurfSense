"use client";

import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
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
	const t = useTranslations("sidebar");

	// Memoize items to prevent unnecessary re-renders
	const memoizedItems = useMemo(() => items, [items]);

	return (
		<SidebarGroup {...props}>
			<SidebarGroupLabel>{t("search_space")}</SidebarGroupLabel>
			<SidebarMenu>
				{memoizedItems.map((item, index) => (
					<SidebarMenuItem key={`${item.title}-${index}`}>
						{item.url === "#" ? (
							// Non-interactive display item (e.g., search space name)
							<div className="flex h-7 w-full items-center gap-2 rounded-md px-2 text-xs text-sidebar-foreground">
								<item.icon className="h-4 w-4 shrink-0" />
								<span className="truncate">{item.title}</span>
							</div>
						) : (
							// Interactive link item
							<SidebarMenuButton asChild size="sm" aria-label={item.title}>
								<a href={item.url}>
									<item.icon />
									<span>{item.title}</span>
								</a>
							</SidebarMenuButton>
						)}
					</SidebarMenuItem>
				))}
			</SidebarMenu>
		</SidebarGroup>
	);
}
