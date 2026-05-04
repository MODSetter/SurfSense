"use client";

import { CreditCard, SquarePen, Zap } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { cn } from "@/lib/utils";
import { SIDEBAR_MIN_WIDTH } from "../../hooks/useSidebarResize";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { AuthenticatedPageUsageDisplay } from "./AuthenticatedPageUsageDisplay";
import { ChatListItem } from "./ChatListItem";
import { NavSection } from "./NavSection";
import { PremiumTokenUsageDisplay } from "./PremiumTokenUsageDisplay";
import { SidebarButton } from "./SidebarButton";
import { SidebarCollapseButton } from "./SidebarCollapseButton";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarSection } from "./SidebarSection";
import { SidebarUserProfile } from "./SidebarUserProfile";

function ChatListItemSkeleton() {
	return (
		<div className="flex w-full items-center gap-2 rounded-md p-2">
			<Skeleton className="h-4 w-4 shrink-0 rounded" />
			<Skeleton className="h-4 w-full max-w-[180px]" />
		</div>
	);
}

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
	onChatRename?: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onChatArchive?: (chat: ChatItem) => void;
	onViewAllSharedChats?: () => void;
	onViewAllPrivateChats?: () => void;
	isSharedChatsPanelOpen?: boolean;
	isPrivateChatsPanelOpen?: boolean;
	user: User;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onUserSettings?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	className?: string;
	isLoadingChats?: boolean;
	disableTooltips?: boolean;
	sidebarWidth?: number;
	isResizing?: boolean;
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
	onChatRename,
	onChatDelete,
	onChatArchive,
	onViewAllSharedChats,
	onViewAllPrivateChats,
	isSharedChatsPanelOpen = false,
	isPrivateChatsPanelOpen = false,
	user,
	onSettings,
	onManageMembers,
	onUserSettings,
	onLogout,
	pageUsage,
	theme,
	setTheme,
	className,
	isLoadingChats = false,
	disableTooltips = false,
	sidebarWidth = SIDEBAR_MIN_WIDTH,
	isResizing = false,
}: SidebarProps) {
	const t = useTranslations("sidebar");
	const [openDropdownChatId, setOpenDropdownChatId] = useState<number | null>(null);

	return (
		<div
			className={cn(
				"relative flex h-full flex-col bg-sidebar text-sidebar-foreground overflow-hidden select-none",
				isCollapsed ? "w-[60px] transition-[width] duration-200" : "",
				!isCollapsed && !isResizing ? "transition-[width] duration-200" : "",
				className
			)}
			style={!isCollapsed ? { width: sidebarWidth } : undefined}
		>
			{/* Header - search space name or collapse button when collapsed */}
			{isCollapsed ? (
				<div className="flex h-14 shrink-0 items-center justify-center border-b">
					<SidebarCollapseButton
						isCollapsed={isCollapsed}
						onToggle={onToggleCollapse ?? (() => {})}
						disableTooltip={disableTooltips}
					/>
				</div>
			) : (
				<div className="flex h-14 shrink-0 items-center gap-0 px-1 border-b">
					<SidebarHeader
						searchSpace={searchSpace}
						isCollapsed={isCollapsed}
						onSettings={onSettings}
						onManageMembers={onManageMembers}
					/>
					<div className="shrink-0">
						<SidebarCollapseButton
							isCollapsed={isCollapsed}
							onToggle={onToggleCollapse ?? (() => {})}
							disableTooltip={disableTooltips}
						/>
					</div>
				</div>
			)}

			{/* New chat button */}
			<div className={cn("flex flex-col gap-0.5 py-2", isCollapsed && "items-center")}>
				<SidebarButton
					icon={SquarePen}
					label={t("new_chat")}
					onClick={onNewChat}
					isCollapsed={isCollapsed}
				/>
			</div>

			{/* Chat sections - fills available space */}
			{isCollapsed ? (
				<div className="flex-1 w-[60px]" />
			) : (
				<div className="flex-1 flex flex-col gap-1 py-2 w-full min-h-0 overflow-hidden">
					{/* Shared Chats Section - takes only space needed, max 50% */}
					<SidebarSection
						title={t("shared_chats")}
						defaultOpen={true}
						fillHeight={false}
						className="shrink-0 max-h-[50%] flex flex-col"
						alwaysShowAction={!disableTooltips && isSharedChatsPanelOpen}
						action={
							onViewAllSharedChats ? (
								<button
									type="button"
									onClick={onViewAllSharedChats}
									className="text-xs font-medium text-muted-foreground/60 hover:text-muted-foreground transition-colors whitespace-nowrap cursor-pointer bg-transparent border-none p-0 focus:outline-none"
								>
									{!disableTooltips && isSharedChatsPanelOpen ? t("hide") : t("show_all")}
								</button>
							) : undefined
						}
					>
						{isLoadingChats ? (
							<div className="flex flex-col gap-0.5">
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
							</div>
						) : sharedChats.length > 0 ? (
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
											dropdownOpen={openDropdownChatId === chat.id}
											onDropdownOpenChange={(open) => setOpenDropdownChatId(open ? chat.id : null)}
											onClick={() => onChatSelect(chat)}
											onRename={() => onChatRename?.(chat)}
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
						alwaysShowAction={!disableTooltips && isPrivateChatsPanelOpen}
						action={
							onViewAllPrivateChats ? (
								<button
									type="button"
									onClick={onViewAllPrivateChats}
									className="text-xs font-medium text-muted-foreground/60 hover:text-muted-foreground transition-colors whitespace-nowrap cursor-pointer bg-transparent border-none p-0 focus:outline-none"
								>
									{!disableTooltips && isPrivateChatsPanelOpen ? t("hide") : t("show_all")}
								</button>
							) : undefined
						}
					>
						{isLoadingChats ? (
							<div className="flex flex-col gap-0.5">
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
								<ChatListItemSkeleton />
							</div>
						) : chats.length > 0 ? (
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
											dropdownOpen={openDropdownChatId === chat.id}
											onDropdownOpenChange={(open) => setOpenDropdownChatId(open ? chat.id : null)}
											onClick={() => onChatSelect(chat)}
											onRename={() => onChatRename?.(chat)}
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

				<SidebarUsageFooter pageUsage={pageUsage} isCollapsed={isCollapsed} />

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

function SidebarUsageFooter({
	pageUsage,
	isCollapsed,
}: {
	pageUsage?: PageUsage;
	isCollapsed: boolean;
}) {
	const params = useParams();
	const searchSpaceId = params?.search_space_id ?? "";
	const isAnonymous = useIsAnonymous();

	if (isCollapsed) return null;

	if (isAnonymous) {
		return (
			<div className="px-3 py-3 border-t space-y-3">
				{pageUsage && (
					<div className="space-y-1.5">
						<div className="flex justify-between items-center text-xs">
							<span className="text-muted-foreground">
								{pageUsage.pagesUsed.toLocaleString()} / {pageUsage.pagesLimit.toLocaleString()}{" "}
								tokens
							</span>
							<span className="font-medium">
								{Math.min(
									(pageUsage.pagesUsed / Math.max(pageUsage.pagesLimit, 1)) * 100,
									100
								).toFixed(0)}
								%
							</span>
						</div>
						<Progress
							value={Math.min((pageUsage.pagesUsed / Math.max(pageUsage.pagesLimit, 1)) * 100, 100)}
							className="h-1.5"
						/>
					</div>
				)}
				<Link
					href="/register"
					className="flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
				>
					Create Free Account
				</Link>
			</div>
		);
	}

	return (
		<div className="px-3 py-3 border-t space-y-3">
			<PremiumTokenUsageDisplay />
			<AuthenticatedPageUsageDisplay />
			<div className="space-y-0.5">
				<Link
					href={`/dashboard/${searchSpaceId}/more-pages`}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<Zap className="h-3 w-3 shrink-0" />
						Get Free Pages
					</span>
					<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
						FREE
					</Badge>
				</Link>
				<Link
					href={`/dashboard/${searchSpaceId}/buy-more`}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<CreditCard className="h-3 w-3 shrink-0" />
						Buy More
					</span>
					<span className="text-[10px] font-medium text-muted-foreground">
						$1/1k &middot; $1/1M
					</span>
				</Link>
			</div>
		</div>
	);
}
