"use client";

import { FolderOpen, PenSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { ChatListItem } from "./ChatListItem";
import { NavSection } from "./NavSection";
import { PageUsageDisplay } from "./PageUsageDisplay";
import { SidebarCollapseButton } from "./SidebarCollapseButton";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarSection } from "./SidebarSection";
import { SidebarUserProfile } from "./SidebarUserProfile";

interface SidebarProps {
	searchSpace: SearchSpace | null;
	isCollapsed?: boolean;
	onToggleCollapse?: () => void;
	navItems: NavItem[];
	onNavItemClick?: (item: NavItem) => void;
	chats: ChatItem[];
	sharedChats?: ChatItem[];
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onChatArchive?: (chat: ChatItem) => void;
	onViewAllSharedChats?: () => void;
	onViewAllPrivateChats?: () => void;
	user: User;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onUserSettings?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	className?: string;
}

export function Sidebar({
	searchSpace,
	isCollapsed = false,
	onToggleCollapse,
	navItems,
	onNavItemClick,
	chats,
	sharedChats = [],
	activeChatId,
	onNewChat,
	onChatSelect,
	onChatDelete,
	onChatArchive,
	onViewAllSharedChats,
	onViewAllPrivateChats,
	user,
	onSettings,
	onManageMembers,
	onUserSettings,
	onLogout,
	pageUsage,
	theme,
	setTheme,
	className,
}: SidebarProps) {
	const t = useTranslations("sidebar");

	return (
		<div
			className={cn(
				"flex h-full flex-col bg-sidebar text-sidebar-foreground transition-all duration-200 overflow-hidden",
				isCollapsed ? "w-[60px]" : "w-[240px]",
				className
			)}
		>
			{/* Header - search space name or collapse button when collapsed */}
			{isCollapsed ? (
				<div className="flex h-14 shrink-0 items-center justify-center border-b">
					<SidebarCollapseButton
						isCollapsed={isCollapsed}
						onToggle={onToggleCollapse ?? (() => {})}
					/>
				</div>
			) : (
				<div className="flex h-14 shrink-0 items-center justify-between px-1 border-b">
					<SidebarHeader
						searchSpace={searchSpace}
						isCollapsed={isCollapsed}
						onSettings={onSettings}
						onManageMembers={onManageMembers}
					/>
					<div className="">
						<SidebarCollapseButton
							isCollapsed={isCollapsed}
							onToggle={onToggleCollapse ?? (() => {})}
						/>
					</div>
				</div>
			)}

			{/* New chat button */}
			<div className="p-2">
				{isCollapsed ? (
					<Tooltip>
						<TooltipTrigger asChild>
							<Button variant="outline" size="icon" className="w-full h-10" onClick={onNewChat}>
								<PenSquare className="h-4 w-4" />
								<span className="sr-only">{t("new_chat")}</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="right">{t("new_chat")}</TooltipContent>
					</Tooltip>
				) : (
					<Button variant="outline" className="w-full justify-start gap-2" onClick={onNewChat}>
						<PenSquare className="h-4 w-4" />
						{t("new_chat")}
					</Button>
				)}
			</div>

			{/* Chat sections - fills available space */}
			{isCollapsed ? (
				<div className="flex-1 w-[60px]" />
			) : (
				<div className="flex-1 flex flex-col gap-1 py-2 w-[240px] min-h-0 overflow-hidden">
					{/* Shared Chats Section - takes only space needed, max 50% */}
					<SidebarSection
						title={t("shared_chats")}
						defaultOpen={true}
						fillHeight={false}
						className="shrink-0 max-h-[50%] flex flex-col"
						action={
							onViewAllSharedChats ? (
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8 shrink-0 hover:bg-transparent hover:text-current focus-visible:ring-0"
											onClick={onViewAllSharedChats}
										>
											<FolderOpen className="h-4 w-4" />
										</Button>
									</TooltipTrigger>
									<TooltipContent side="top">
										{t("view_all_shared_chats") || "View all shared chats"}
									</TooltipContent>
								</Tooltip>
							) : undefined
						}
					>
						{sharedChats.length > 0 ? (
							<div className="relative min-h-0 flex-1">
								<div
									className={`flex flex-col gap-0.5 max-h-full overflow-y-auto scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent ${sharedChats.length > 4 ? "pb-8" : ""}`}
								>
									{sharedChats.slice(0, 20).map((chat) => (
										<ChatListItem
											key={chat.id}
											name={chat.name}
											isActive={chat.id === activeChatId}
											archived={chat.archived}
											onClick={() => onChatSelect(chat)}
											onArchive={() => onChatArchive?.(chat)}
											onDelete={() => onChatDelete?.(chat)}
										/>
									))}
								</div>
								{/* Gradient fade indicator when more than 4 items */}
								{sharedChats.length > 4 && (
									<div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-sidebar via-sidebar/90 to-transparent" />
								)}
							</div>
						) : (
							<p className="px-2 py-1 text-xs text-muted-foreground">{t("no_shared_chats")}</p>
						)}
					</SidebarSection>

					{/* Private Chats Section - fills remaining space */}
					<SidebarSection
						title={t("chats")}
						defaultOpen={true}
						fillHeight={true}
						action={
							onViewAllPrivateChats ? (
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8 shrink-0 hover:bg-transparent hover:text-current focus-visible:ring-0"
											onClick={onViewAllPrivateChats}
										>
											<FolderOpen className="h-4 w-4" />
										</Button>
									</TooltipTrigger>
									<TooltipContent side="top">
										{t("view_all_private_chats") || "View all private chats"}
									</TooltipContent>
								</Tooltip>
							) : undefined
						}
					>
						{chats.length > 0 ? (
							<div className="relative flex-1 min-h-0">
								<div
									className={`flex flex-col gap-0.5 h-full overflow-y-auto scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent ${chats.length > 4 ? "pb-8" : ""}`}
								>
									{chats.slice(0, 20).map((chat) => (
										<ChatListItem
											key={chat.id}
											name={chat.name}
											isActive={chat.id === activeChatId}
											archived={chat.archived}
											onClick={() => onChatSelect(chat)}
											onArchive={() => onChatArchive?.(chat)}
											onDelete={() => onChatDelete?.(chat)}
										/>
									))}
								</div>
								{/* Gradient fade indicator when more than 4 items */}
								{chats.length > 4 && (
									<div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-sidebar via-sidebar/90 to-transparent" />
								)}
							</div>
						) : (
							<p className="px-2 py-1 text-xs text-muted-foreground">{t("no_chats")}</p>
						)}
					</SidebarSection>
				</div>
			)}

			{/* Footer */}
			<div className="mt-auto border-t">
				{/* Platform navigation */}
				{navItems.length > 0 && (
					<NavSection items={navItems} onItemClick={onNavItemClick} isCollapsed={isCollapsed} />
				)}

				{pageUsage && !isCollapsed && (
					<PageUsageDisplay pagesUsed={pageUsage.pagesUsed} pagesLimit={pageUsage.pagesLimit} />
				)}

				<SidebarUserProfile
					user={user}
					onUserSettings={onUserSettings}
					onLogout={onLogout}
					isCollapsed={isCollapsed}
					theme={theme}
					setTheme={setTheme}
				/>
			</div>
		</div>
	);
}
