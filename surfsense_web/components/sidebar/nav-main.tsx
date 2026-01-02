"use client";

import { ChevronRight, type LucideIcon } from "lucide-react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	SidebarGroup,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuAction,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarMenuSub,
	SidebarMenuSubButton,
	SidebarMenuSubItem,
} from "@/components/ui/sidebar";

interface NavItem {
	title: string;
	url: string;
	icon: LucideIcon;
	isActive?: boolean;
	items?: {
		title: string;
		url: string;
	}[];
}

interface NavMainProps {
	items: NavItem[];
}

export function NavMain({ items }: NavMainProps) {
	const t = useTranslations("nav_menu");
	const pathname = usePathname();

	// Translation function that handles both exact matches and fallback to original
	const translateTitle = (title: string): string => {
		const titleMap: Record<string, string> = {
			Researcher: "researcher",
			"Manage LLMs": "manage_llms",
			Sources: "sources",
			"Manage Documents": "manage_documents",
			"Manage Connectors": "manage_connectors",
			Podcasts: "podcasts",
			Logs: "logs",
			Platform: "platform",
			Team: "team",
		};

		const key = titleMap[title];
		return key ? t(key) : title;
	};

	// Check if an item is active based on pathname
	const isItemActive = useCallback(
		(item: NavItem): boolean => {
			if (!pathname) return false;

			// For items without sub-items, check if pathname matches or starts with the URL
			if (!item.items?.length) {
				// Chat item: active ONLY when on new-chat page without a specific chat ID
				// (i.e., exactly /dashboard/{id}/new-chat, not /dashboard/{id}/new-chat/123)
				if (item.url.includes("/new-chat")) {
					// Match exactly the new-chat base URL (ends with /new-chat)
					return pathname.endsWith("/new-chat");
				}
				// Logs item: active when on logs page
				if (item.url.includes("/logs")) {
					return pathname.includes("/logs");
				}
				// Check exact match or prefix match
				return pathname === item.url || pathname.startsWith(`${item.url}/`);
			}

			// For items with sub-items (like Sources), check if any sub-item URL matches
			return item.items.some(
				(subItem) => pathname === subItem.url || pathname.startsWith(subItem.url)
			);
		},
		[pathname]
	);

	// Memoize items to prevent unnecessary re-renders
	const memoizedItems = useMemo(() => items, [items]);

	// Track expanded state for items with sub-menus (like Sources)
	const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>(() => {
		const initial: Record<string, boolean> = {};
		items.forEach((item) => {
			if (item.items?.length) {
				initial[item.title] = item.isActive ?? false;
			}
		});
		return initial;
	});

	// Handle collapsible state change
	const handleOpenChange = useCallback((title: string, isOpen: boolean) => {
		setExpandedItems((prev) => ({ ...prev, [title]: isOpen }));
	}, []);

	return (
		<SidebarGroup>
			<SidebarGroupLabel>{translateTitle("Platform")}</SidebarGroupLabel>
			<SidebarMenu>
				{memoizedItems.map((item, index) => {
					const translatedTitle = translateTitle(item.title);
					const hasSub = !!item.items?.length;
					const isActive = isItemActive(item);
					const isItemOpen = expandedItems[item.title] ?? isActive ?? false;
					return (
						<Collapsible
							key={`${item.title}-${index}`}
							asChild
							open={hasSub ? isItemOpen : undefined}
							onOpenChange={hasSub ? (open) => handleOpenChange(item.title, open) : undefined}
							defaultOpen={!hasSub ? isActive : undefined}
						>
							<SidebarMenuItem>
								{hasSub ? (
									// When the item has children, make the whole row a collapsible trigger
									<>
										<CollapsibleTrigger asChild>
											<SidebarMenuButton
												asChild
												tooltip={translatedTitle}
												isActive={isActive}
												aria-label={`${translatedTitle} with submenu`}
											>
												<button type="button" className="flex items-center gap-2 w-full text-left">
													<item.icon />
													<span>{translatedTitle}</span>
												</button>
											</SidebarMenuButton>
										</CollapsibleTrigger>

										<CollapsibleTrigger asChild>
											<SidebarMenuAction
												className="data-[state=open]:rotate-90 transition-transform duration-200"
												aria-label={`Toggle ${translatedTitle} submenu`}
											>
												<ChevronRight />
												<span className="sr-only">Toggle submenu</span>
											</SidebarMenuAction>
										</CollapsibleTrigger>

										<CollapsibleContent className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2 duration-200">
											<SidebarMenuSub>
												{item.items?.map((subItem, subIndex) => {
													const translatedSubTitle = translateTitle(subItem.title);
													return (
														<SidebarMenuSubItem key={`${subItem.title}-${subIndex}`}>
															<SidebarMenuSubButton asChild aria-label={translatedSubTitle}>
																<a href={subItem.url}>
																	<span>{translatedSubTitle}</span>
																</a>
															</SidebarMenuSubButton>
														</SidebarMenuSubItem>
													);
												})}
											</SidebarMenuSub>
										</CollapsibleContent>
									</>
								) : (
									// Leaf item: treat as a normal link
									<SidebarMenuButton
										asChild
										tooltip={translatedTitle}
										isActive={isActive}
										aria-label={translatedTitle}
									>
										<a href={item.url}>
											<item.icon />
											<span>{translatedTitle}</span>
										</a>
									</SidebarMenuButton>
								)}
							</SidebarMenuItem>
						</Collapsible>
					);
				})}
			</SidebarMenu>
		</SidebarGroup>
	);
}
