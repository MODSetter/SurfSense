"use client";

import { useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { InboxItem } from "@/hooks/use-inbox";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { SidebarProvider, useSidebarState } from "../../hooks";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { Header } from "../header";
import { IconRail } from "../icon-rail";
import { InboxSidebar, MobileSidebar, MobileSidebarTrigger, Sidebar } from "../sidebar";

// Tab-specific data source props
interface TabDataSource {
	items: InboxItem[];
	unreadCount: number;
	loading: boolean;
	loadingMore?: boolean;
	hasMore?: boolean;
	loadMore?: () => void;
}

// Inbox-related props with separate data sources per tab
interface InboxProps {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
	/** Mentions tab data source with independent pagination */
	mentions: TabDataSource;
	/** Status tab data source with independent pagination */
	status: TabDataSource;
	/** Combined unread count for nav badge */
	totalUnreadCount: number;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
	/** Whether the inbox is docked (permanent) */
	isDocked?: boolean;
	/** Callback to change docked state */
	onDockedChange?: (docked: boolean) => void;
}

interface LayoutShellProps {
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onSearchSpaceDelete?: (searchSpace: SearchSpace) => void;
	onSearchSpaceSettings?: (searchSpace: SearchSpace) => void;
	onAddSearchSpace: () => void;
	searchSpace: SearchSpace | null;
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
	breadcrumb?: React.ReactNode;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	defaultCollapsed?: boolean;
	isChatPage?: boolean;
	children: React.ReactNode;
	className?: string;
	// Inbox props
	inbox?: InboxProps;
}

export function LayoutShell({
	searchSpaces,
	activeSearchSpaceId,
	onSearchSpaceSelect,
	onSearchSpaceDelete,
	onSearchSpaceSettings,
	onAddSearchSpace,
	searchSpace,
	navItems,
	onNavItemClick,
	chats,
	sharedChats,
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
	breadcrumb,
	theme,
	setTheme,
	defaultCollapsed = false,
	isChatPage = false,
	children,
	className,
	inbox,
}: LayoutShellProps) {
	const isMobile = useIsMobile();
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const { isCollapsed, setIsCollapsed, toggleCollapsed } = useSidebarState(defaultCollapsed);

	// Memoize context value to prevent unnecessary re-renders
	const sidebarContextValue = useMemo(
		() => ({ isCollapsed, setIsCollapsed, toggleCollapsed }),
		[isCollapsed, setIsCollapsed, toggleCollapsed]
	);

	// Mobile layout
	if (isMobile) {
		return (
			<SidebarProvider value={sidebarContextValue}>
				<TooltipProvider delayDuration={0}>
					<div className={cn("flex h-screen w-full flex-col bg-background", className)}>
						<Header
							breadcrumb={breadcrumb}
							mobileMenuTrigger={<MobileSidebarTrigger onClick={() => setMobileMenuOpen(true)} />}
						/>

						<MobileSidebar
							isOpen={mobileMenuOpen}
							onOpenChange={setMobileMenuOpen}
							searchSpaces={searchSpaces}
							activeSearchSpaceId={activeSearchSpaceId}
							onSearchSpaceSelect={onSearchSpaceSelect}
							onSearchSpaceDelete={onSearchSpaceDelete}
							onSearchSpaceSettings={onSearchSpaceSettings}
							onAddSearchSpace={onAddSearchSpace}
							searchSpace={searchSpace}
							navItems={navItems}
							onNavItemClick={onNavItemClick}
							chats={chats}
							sharedChats={sharedChats}
							activeChatId={activeChatId}
							onNewChat={onNewChat}
							onChatSelect={onChatSelect}
							onChatDelete={onChatDelete}
							onChatArchive={onChatArchive}
							onViewAllSharedChats={onViewAllSharedChats}
							onViewAllPrivateChats={onViewAllPrivateChats}
							user={user}
							onSettings={onSettings}
							onManageMembers={onManageMembers}
							onUserSettings={onUserSettings}
							onLogout={onLogout}
							pageUsage={pageUsage}
							theme={theme}
							setTheme={setTheme}
						/>

						<main className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
							{children}
						</main>

						{/* Mobile Inbox Sidebar - only render when open to avoid scroll blocking */}
						{inbox?.isOpen && (
							<InboxSidebar
								open={inbox.isOpen}
								onOpenChange={inbox.onOpenChange}
								mentions={inbox.mentions}
								status={inbox.status}
								totalUnreadCount={inbox.totalUnreadCount}
								markAsRead={inbox.markAsRead}
								markAllAsRead={inbox.markAllAsRead}
								onCloseMobileSidebar={() => setMobileMenuOpen(false)}
							/>
						)}
					</div>
				</TooltipProvider>
			</SidebarProvider>
		);
	}

	// Desktop layout
	return (
		<SidebarProvider value={sidebarContextValue}>
			<TooltipProvider delayDuration={0}>
				<div
					className={cn("flex h-screen w-full gap-2 p-2 overflow-hidden bg-muted/40", className)}
				>
					<div className="hidden md:flex overflow-hidden">
						<IconRail
							searchSpaces={searchSpaces}
							activeSearchSpaceId={activeSearchSpaceId}
							onSearchSpaceSelect={onSearchSpaceSelect}
							onSearchSpaceDelete={onSearchSpaceDelete}
							onSearchSpaceSettings={onSearchSpaceSettings}
							onAddSearchSpace={onAddSearchSpace}
						/>
					</div>

					{/* Main container with sidebar and content - relative for inbox positioning */}
					<div className="relative flex flex-1 rounded-xl border bg-background overflow-hidden">
						<Sidebar
							searchSpace={searchSpace}
							isCollapsed={isCollapsed}
							onToggleCollapse={toggleCollapsed}
							navItems={navItems}
							onNavItemClick={onNavItemClick}
							chats={chats}
							sharedChats={sharedChats}
							activeChatId={activeChatId}
							onNewChat={onNewChat}
							onChatSelect={onChatSelect}
							onChatDelete={onChatDelete}
							onChatArchive={onChatArchive}
							onViewAllSharedChats={onViewAllSharedChats}
							onViewAllPrivateChats={onViewAllPrivateChats}
							user={user}
							onSettings={onSettings}
							onManageMembers={onManageMembers}
							onUserSettings={onUserSettings}
							onLogout={onLogout}
							pageUsage={pageUsage}
							theme={theme}
							setTheme={setTheme}
							className="hidden md:flex border-r shrink-0"
						/>

						{/* Docked Inbox Sidebar - renders as flex sibling between sidebar and content */}
						{inbox?.isDocked && (
							<InboxSidebar
								open={inbox.isOpen}
								onOpenChange={inbox.onOpenChange}
								mentions={inbox.mentions}
								status={inbox.status}
								totalUnreadCount={inbox.totalUnreadCount}
								markAsRead={inbox.markAsRead}
								markAllAsRead={inbox.markAllAsRead}
								isDocked={inbox.isDocked}
								onDockedChange={inbox.onDockedChange}
							/>
						)}

						<main className="flex-1 flex flex-col min-w-0">
							<Header breadcrumb={breadcrumb} />

							<div className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
								{children}
							</div>
						</main>

						{/* Floating Inbox Sidebar - positioned absolutely on top of content */}
						{inbox && !inbox.isDocked && (
							<InboxSidebar
								open={inbox.isOpen}
								onOpenChange={inbox.onOpenChange}
								mentions={inbox.mentions}
								status={inbox.status}
								totalUnreadCount={inbox.totalUnreadCount}
								markAsRead={inbox.markAsRead}
								markAllAsRead={inbox.markAllAsRead}
								isDocked={false}
								onDockedChange={inbox.onDockedChange}
							/>
						)}
					</div>
				</div>
			</TooltipProvider>
		</SidebarProvider>
	);
}
