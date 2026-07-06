"use client";

import { CreditCard, SquarePen, Zap } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type ReactNode, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { getWorkspaceIdParam } from "@/lib/route-params";
import { cn } from "@/lib/utils";
import { SIDEBAR_MIN_WIDTH } from "../../hooks/useSidebarResize";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { ChatListItem } from "./ChatListItem";
import { CreditBalanceDisplay } from "./CreditBalanceDisplay";
import { NavSection } from "./NavSection";
import { SidebarButton } from "./SidebarButton";
import { SidebarCollapseButton } from "./SidebarCollapseButton";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarSection } from "./SidebarSection";
import { SidebarUserProfile } from "./SidebarUserProfile";

const CHAT_LIST_SKELETON_WIDTHS = ["w-[78%]", "w-[64%]", "w-[86%]", "w-[58%]", "w-[72%]"];

function ChatListItemSkeleton({ widthClass }: { widthClass: string }) {
	return (
		<div className="group/item relative w-full">
			<div className="flex h-[32px] w-full items-center rounded-md px-2 py-1.5">
				<Skeleton className={cn("h-4 rounded", widthClass)} />
			</div>
		</div>
	);
}

function ChatListSkeletonRows() {
	return (
		<div className="flex flex-col gap-0.5">
			{CHAT_LIST_SKELETON_WIDTHS.map((widthClass) => (
				<ChatListItemSkeleton key={widthClass} widthClass={widthClass} />
			))}
		</div>
	);
}

function CollapsedInboxIcon({ item }: { item: NavItem }) {
	const Icon = item.icon;

	return (
		<span className="relative flex h-3.5 w-3.5 items-center justify-center">
			<Icon className="h-3.5 w-3.5" />
			{typeof item.badge === "string" ? (
				<span className="absolute right-0 top-0 flex min-w-3.5 -translate-y-1/2 translate-x-1/2 items-center justify-center rounded-full bg-destructive px-1 text-[9px] font-medium leading-3 text-destructive-foreground">
					{item.badge}
				</span>
			) : null}
		</span>
	);
}

interface SidebarProps {
	searchSpace: SearchSpace | null;
	isCollapsed?: boolean;
	onToggleCollapse?: () => void;
	navItems: NavItem[];
	onNavItemClick?: (item: NavItem) => void;
	chats: ChatItem[];
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatPrefetch?: (chat: ChatItem) => void;
	onChatRename?: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onChatArchive?: (chat: ChatItem) => void;
	onViewAllChats?: () => void;
	isAllChatsActive?: boolean;
	user: User;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onUserSettings?: () => void;
	onAnnouncements?: () => void;
	onNavigate?: () => void;
	announcementUnreadCount?: number;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	className?: string;
	isLoadingChats?: boolean;
	disableTooltips?: boolean;
	sidebarWidth?: number;
	isResizing?: boolean;
	renderUserProfile?: boolean;
	renderCollapseButton?: boolean;
	collapsedHeaderContent?: ReactNode;
}

export function Sidebar({
	searchSpace,
	isCollapsed = false,
	onToggleCollapse,
	navItems,
	onNavItemClick,
	chats,
	activeChatId,
	onNewChat,
	onChatSelect,
	onChatPrefetch,
	onChatRename,
	onChatDelete,
	onChatArchive,
	onViewAllChats,
	isAllChatsActive = false,
	user,
	onSettings,
	onManageMembers,
	onUserSettings,
	onAnnouncements,
	onNavigate,
	announcementUnreadCount = 0,
	onLogout,
	pageUsage,
	theme,
	setTheme,
	className,
	isLoadingChats = false,
	disableTooltips = false,
	sidebarWidth = SIDEBAR_MIN_WIDTH,
	isResizing = false,
	renderUserProfile = true,
	renderCollapseButton = true,
	collapsedHeaderContent,
}: SidebarProps) {
	const t = useTranslations("sidebar");
	const [openDropdownChatId, setOpenDropdownChatId] = useState<number | null>(null);

	// Inbox, Automations, and Documents are rendered explicitly right below
	// New Chat. Pull them out of the nav items list so they don't also appear
	// in the bottom NavSection. Documents is only present in navItems on
	// mobile; Automations is identified by URL suffix so the same code path
	// works across search spaces.
	const inboxItem = useMemo(() => navItems.find((item) => item.url === "#inbox"), [navItems]);
	const automationsItem = useMemo(
		() => navItems.find((item) => item.url.endsWith("/automations")),
		[navItems]
	);
	const artifactsItem = useMemo(
		() => navItems.find((item) => item.url.endsWith("/artifacts")),
		[navItems]
	);
	const documentsItem = useMemo(
		() => navItems.find((item) => item.url === "#documents"),
		[navItems]
	);
	const footerNavItems = useMemo(
		() =>
			navItems.filter(
				(item) =>
					item.url !== "#inbox" &&
					item.url !== "#documents" &&
					!item.url.endsWith("/automations") &&
					!item.url.endsWith("/artifacts")
			),
		[navItems]
	);

	const collapsedWidth = 51;

	return (
		<div
			className={cn(
				"relative flex h-full flex-col bg-panel text-sidebar-foreground overflow-hidden select-none",
				!isResizing && "transition-[width] duration-200 ease-out",
				className
			)}
			style={{ width: isCollapsed ? collapsedWidth : sidebarWidth }}
		>
			<div className="relative flex h-12 shrink-0 items-center gap-0 px-1 border-b">
				<div
					className={cn(
						"min-w-0 overflow-hidden",
						"transition-[max-width,opacity,margin-right] duration-200 ease-out",
						isCollapsed ? "max-w-0 opacity-0 mr-0" : "max-w-[400px] flex-1 opacity-100"
					)}
					aria-hidden={isCollapsed}
				>
					<SidebarHeader
						searchSpace={searchSpace}
						isCollapsed={false}
						onSettings={onSettings}
						onManageMembers={onManageMembers}
					/>
				</div>
				{collapsedHeaderContent ? (
					<div
						aria-hidden={!isCollapsed}
						className={cn(
							"pointer-events-none absolute inset-y-0 left-0 flex items-center justify-center transition-opacity duration-150",
							isCollapsed ? "opacity-100 delay-150" : "opacity-0"
						)}
						style={{ width: collapsedWidth }}
					>
						{collapsedHeaderContent}
					</div>
				) : null}
				{renderCollapseButton ? (
					<div className={cn("shrink-0", isCollapsed && "mx-auto")}>
						<SidebarCollapseButton
							isCollapsed={isCollapsed}
							onToggle={onToggleCollapse ?? (() => {})}
							disableTooltip={disableTooltips}
						/>
					</div>
				) : null}
			</div>

			<div className="flex flex-col gap-0.5 py-1.5">
				<SidebarButton
					icon={SquarePen}
					label={t("new_chat")}
					onClick={onNewChat}
					isCollapsed={isCollapsed}
				/>
				{inboxItem && (
					<SidebarButton
						icon={inboxItem.icon}
						label={inboxItem.title}
						onClick={() => onNavItemClick?.(inboxItem)}
						isCollapsed={isCollapsed}
						isActive={inboxItem.isActive}
						badge={inboxItem.badge}
						collapsedIconNode={<CollapsedInboxIcon item={inboxItem} />}
						tooltipContent={isCollapsed ? inboxItem.title : undefined}
						buttonProps={
							{
								"data-joyride": "inbox-sidebar",
							} as React.ButtonHTMLAttributes<HTMLButtonElement>
						}
					/>
				)}
				{automationsItem && (
					<SidebarButton
						icon={automationsItem.icon}
						label={automationsItem.title}
						onClick={() => onNavItemClick?.(automationsItem)}
						isCollapsed={isCollapsed}
						isActive={automationsItem.isActive}
						tooltipContent={isCollapsed ? automationsItem.title : undefined}
					/>
				)}
				{artifactsItem && (
					<SidebarButton
						icon={artifactsItem.icon}
						label={artifactsItem.title}
						onClick={() => onNavItemClick?.(artifactsItem)}
						isCollapsed={isCollapsed}
						isActive={artifactsItem.isActive}
						tooltipContent={isCollapsed ? artifactsItem.title : undefined}
					/>
				)}
				{documentsItem && (
					<SidebarButton
						icon={documentsItem.icon}
						label={documentsItem.title}
						onClick={() => onNavItemClick?.(documentsItem)}
						isCollapsed={isCollapsed}
						isActive={documentsItem.isActive}
						tooltipContent={isCollapsed ? documentsItem.title : undefined}
					/>
				)}
			</div>

			{/* Chat sections - fills available space */}
			{isCollapsed ? (
				<div className="flex-1 w-full" />
			) : (
				<div className="flex-1 flex flex-col gap-1 pt-2 w-full min-h-0 overflow-hidden">
					<SidebarSection
						title={t("recents")}
						defaultOpen={true}
						fillHeight={true}
						alwaysShowAction={!disableTooltips && isAllChatsActive}
						action={
							onViewAllChats ? (
								<Button
									type="button"
									variant="ghost"
									onClick={onViewAllChats}
									className="h-auto cursor-pointer whitespace-nowrap bg-transparent p-0 text-xs font-medium text-muted-foreground/60 transition-colors hover:bg-transparent hover:text-muted-foreground"
								>
									{!disableTooltips && isAllChatsActive ? t("hide") : t("show_all")}
								</Button>
							) : undefined
						}
					>
						{isLoadingChats ? (
							<ChatListSkeletonRows />
						) : chats.length > 0 ? (
							<div className="relative flex-1 min-h-0">
								<div
									className={`flex flex-col gap-0.5 h-full overflow-y-auto scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent ${chats.length > 4 ? "pb-2" : ""}`}
								>
									{chats.slice(0, 20).map((chat) => (
										<ChatListItem
											key={chat.id}
											name={chat.name}
											isActive={chat.id === activeChatId}
											isShared={chat.visibility === "SEARCH_SPACE"}
											archived={chat.archived}
											dropdownOpen={openDropdownChatId === chat.id}
											onDropdownOpenChange={(open) => setOpenDropdownChatId(open ? chat.id : null)}
											onClick={() => onChatSelect(chat)}
											onPrefetch={() => onChatPrefetch?.(chat)}
											onRename={() => onChatRename?.(chat)}
											onArchive={() => onChatArchive?.(chat)}
											onDelete={() => onChatDelete?.(chat)}
										/>
									))}
								</div>
								{/* Gradient fade indicator when more than 4 items */}
								{chats.length > 4 && (
									<div className="pointer-events-none absolute bottom-0 left-0 right-0 h-5 bg-gradient-to-t from-sidebar/80 to-transparent" />
								)}
							</div>
						) : (
							<p className="px-2 py-1 text-sm text-muted-foreground/60">{t("no_chats")}</p>
						)}
					</SidebarSection>
				</div>
			)}

			{/* Footer */}
			<div className="mt-auto border-t">
				{/* Platform navigation */}
				{footerNavItems.length > 0 && (
					<NavSection
						items={footerNavItems}
						onItemClick={onNavItemClick}
						isCollapsed={isCollapsed}
					/>
				)}

				<SidebarUsageFooter
					pageUsage={pageUsage}
					isCollapsed={isCollapsed}
					hasNavSectionAbove={footerNavItems.length > 0}
					onNavigate={onNavigate}
				/>

				{renderUserProfile && (
					<SidebarUserProfile
						user={user}
						onUserSettings={onUserSettings}
						onAnnouncements={onAnnouncements}
						announcementUnreadCount={announcementUnreadCount}
						onLogout={onLogout}
						isCollapsed={isCollapsed}
						theme={theme}
						setTheme={setTheme}
					/>
				)}
			</div>
		</div>
	);
}

function SidebarUsageFooter({
	pageUsage,
	isCollapsed,
	hasNavSectionAbove = false,
	onNavigate,
}: {
	pageUsage?: PageUsage;
	isCollapsed: boolean;
	hasNavSectionAbove?: boolean;
	onNavigate?: () => void;
}) {
	const params = useParams();
	const searchSpaceId = getWorkspaceIdParam(params) ?? "";
	const isAnonymous = useIsAnonymous();

	if (isCollapsed) return null;

	const containerClass = cn("px-3 py-3 space-y-3", hasNavSectionAbove && "border-t");

	if (isAnonymous) {
		return (
			<div className={containerClass}>
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
		<div className={containerClass}>
			<CreditBalanceDisplay />
			<div className="space-y-0.5">
				<Link
					href={`/dashboard/${searchSpaceId}/earn-credits`}
					onClick={onNavigate}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<Zap className="h-3 w-3 shrink-0" />
						Earn credits
					</span>
					<Badge className="h-4 rounded px-1 text-[10px] font-semibold leading-none bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
						FREE
					</Badge>
				</Link>
				<Link
					href={`/dashboard/${searchSpaceId}/buy-more`}
					onClick={onNavigate}
					className="group flex w-full items-center justify-between rounded-md px-1.5 py-1 transition-colors hover:bg-accent"
				>
					<span className="flex items-center gap-1.5 text-xs text-muted-foreground group-hover:text-accent-foreground">
						<CreditCard className="h-3 w-3 shrink-0" />
						Buy credits
					</span>
				</Link>
			</div>
		</div>
	);
}
