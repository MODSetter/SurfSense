"use client";

import {
	ChevronRight,
	FolderOpen,
	Loader2,
	type LucideIcon,
	MessageCircleMore,
	MoreHorizontal,
	RefreshCw,
	Trash2,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { AllChatsSidebar } from "./all-chats-sidebar";

interface ChatAction {
	name: string;
	icon: string;
	onClick: () => void;
}

interface ChatItem {
	name: string;
	url: string;
	icon: LucideIcon;
	id?: number;
	search_space_id?: number;
	actions?: ChatAction[];
}

interface NavChatsProps {
	chats: ChatItem[];
	defaultOpen?: boolean;
	searchSpaceId?: string;
	isSourcesExpanded?: boolean;
}

// Map of icon names to their components
const actionIconMap: Record<string, LucideIcon> = {
	MessageCircleMore,
	Trash2,
	MoreHorizontal,
	RefreshCw,
};

export function NavChats({
	chats,
	defaultOpen = true,
	searchSpaceId,
	isSourcesExpanded = false,
}: NavChatsProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const pathname = usePathname();
	const isMobile = useIsMobile();
	const [isDeleting, setIsDeleting] = useState<number | null>(null);
	const [isOpen, setIsOpen] = useState(defaultOpen);
	const [isAllChatsSidebarOpen, setIsAllChatsSidebarOpen] = useState(false);

	// Auto-collapse on smaller screens when Sources is expanded
	useEffect(() => {
		if (isSourcesExpanded && isMobile) {
			setIsOpen(false);
		}
	}, [isSourcesExpanded, isMobile]);

	// Handle chat deletion with loading state
	const handleDeleteChat = useCallback(async (chatId: number, deleteAction: () => void) => {
		setIsDeleting(chatId);
		try {
			await deleteAction();
		} finally {
			setIsDeleting(null);
		}
	}, []);

	// Handle chat navigation
	const handleChatClick = useCallback(
		(url: string) => {
			router.push(url);
		},
		[router]
	);

	return (
		<SidebarGroup className="group-data-[collapsible=icon]:hidden">
			<Collapsible open={isOpen} onOpenChange={setIsOpen}>
				<div className="flex items-center group/header">
					<CollapsibleTrigger asChild>
						<SidebarGroupLabel className="cursor-pointer rounded-md px-2 py-1.5 -mx-2 transition-colors flex items-center gap-1.5 flex-1">
							<ChevronRight
								className={cn(
									"h-3.5 w-3.5 text-muted-foreground transition-all duration-200 shrink-0",
									isOpen && "rotate-90"
								)}
							/>
							<span>{t("recent_chats") || "Recent Chats"}</span>
						</SidebarGroupLabel>
					</CollapsibleTrigger>

					{/* Action buttons - always visible on hover */}
					<div className="flex items-center gap-0.5 opacity-0 group-hover/header:opacity-100 transition-opacity pr-1">
						{searchSpaceId && chats.length > 0 && (
							<Button
								variant="ghost"
								size="icon"
								className="h-5 w-5"
								onClick={(e) => {
									e.stopPropagation();
									setIsAllChatsSidebarOpen(true);
								}}
								aria-label={t("view_all_chats") || "View all chats"}
							>
								<FolderOpen className="h-3.5 w-3.5" />
							</Button>
						)}
					</div>
				</div>

				<CollapsibleContent>
					{chats.length > 0 ? (
						<SidebarGroupContent>
							<SidebarMenu>
								{chats.map((chat) => {
									const isDeletingChat = isDeleting === chat.id;
									const isActive = pathname === chat.url;

									return (
										<SidebarMenuItem key={chat.id || chat.name} className="group/chat">
											{/* Main navigation button */}
											<SidebarMenuButton
												onClick={() => handleChatClick(chat.url)}
												disabled={isDeletingChat}
												className={cn(
													"pr-8", // Make room for the action button
													isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
													isDeletingChat && "opacity-50"
												)}
											>
												<chat.icon className="h-4 w-4 shrink-0" />
												<span className="truncate">{chat.name}</span>
											</SidebarMenuButton>

											{/* Actions dropdown - positioned absolutely */}
											{chat.actions && chat.actions.length > 0 && (
												<div className="absolute right-1 top-1/2 -translate-y-1/2">
													<DropdownMenu>
														<DropdownMenuTrigger asChild>
															<Button
																variant="ghost"
																size="icon"
																className={cn(
																	"h-6 w-6",
																	"opacity-0 group-hover/chat:opacity-100 focus:opacity-100",
																	"data-[state=open]:opacity-100",
																	"transition-opacity"
																)}
																disabled={isDeletingChat}
															>
																{isDeletingChat ? (
																	<Loader2 className="h-3.5 w-3.5 animate-spin" />
																) : (
																	<MoreHorizontal className="h-3.5 w-3.5" />
																)}
																<span className="sr-only">
																	{t("more_options") || "More options"}
																</span>
															</Button>
														</DropdownMenuTrigger>
														<DropdownMenuContent align="end" side="right" className="w-40">
															{chat.actions.map((action, actionIndex) => {
																const ActionIcon = actionIconMap[action.icon] || MessageCircleMore;
																const isDeleteAction = action.name.toLowerCase().includes("delete");

																return (
																	<DropdownMenuItem
																		key={`${action.name}-${actionIndex}`}
																		onClick={() => {
																			if (isDeleteAction) {
																				handleDeleteChat(chat.id || 0, action.onClick);
																			} else {
																				action.onClick();
																			}
																		}}
																		disabled={isDeletingChat}
																		className={
																			isDeleteAction
																				? "text-destructive focus:text-destructive"
																				: ""
																		}
																	>
																		<ActionIcon className="mr-2 h-4 w-4" />
																		<span>
																			{isDeletingChat && isDeleteAction
																				? t("deleting") || "Deleting..."
																				: action.name}
																		</span>
																	</DropdownMenuItem>
																);
															})}
														</DropdownMenuContent>
													</DropdownMenu>
												</div>
											)}
										</SidebarMenuItem>
									);
								})}
							</SidebarMenu>
						</SidebarGroupContent>
					) : (
						<div className="flex items-center gap-2 px-2 py-1 text-muted-foreground/60 text-xs">
							<MessageCircleMore className="h-3.5 w-3.5" />
							<span>{t("no_recent_chats") || "No recent chats"}</span>
						</div>
					)}
				</CollapsibleContent>
			</Collapsible>

			{/* All Chats Sheet */}
			{searchSpaceId && (
				<AllChatsSidebar
					open={isAllChatsSidebarOpen}
					onOpenChange={setIsAllChatsSidebarOpen}
					searchSpaceId={searchSpaceId}
				/>
			)}
		</SidebarGroup>
	);
}
