"use client";

import { useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { InboxItem } from "@/hooks/use-inbox";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { SidebarProvider, useSidebarState } from "../../hooks";
import { useSidebarResize } from "../../hooks/useSidebarResize";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { Header } from "../header";
import { IconRail } from "../icon-rail";
import { RightPanel } from "../right-panel/RightPanel";
import {
	AllPrivateChatsSidebar,
	AllSharedChatsSidebar,
	AnnouncementsSidebar,
	DocumentsSidebar,
	InboxSidebar,
	MobileSidebar,
	MobileSidebarTrigger,
	Sidebar,
} from "../sidebar";

// Per-tab data source
interface TabDataSource {
	items: InboxItem[];
	unreadCount: number;
	loading: boolean;
	loadingMore: boolean;
	hasMore: boolean;
	loadMore: () => void;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
}

// Inbox-related props — per-tab data sources with independent loading/pagination
interface InboxProps {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
	totalUnreadCount: number;
	comments: TabDataSource;
	status: TabDataSource;
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
	onChatRename?: (chat: ChatItem) => void;
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
	defaultCollapsed?: boolean;
	isChatPage?: boolean;
	children: React.ReactNode;
	className?: string;
	// Inbox props
	inbox?: InboxProps;
	announcementsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
	};
	isLoadingChats?: boolean;
	// All chats panel props
	allSharedChatsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
		searchSpaceId: string;
	};
	allPrivateChatsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
		searchSpaceId: string;
	};
	documentsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
		isDocked?: boolean;
		onDockedChange?: (docked: boolean) => void;
	};
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
	onChatRename,
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
	defaultCollapsed = false,
	isChatPage = false,
	children,
	className,
	inbox,
	announcementsPanel,
	isLoadingChats = false,
	allSharedChatsPanel,
	allPrivateChatsPanel,
	documentsPanel,
}: LayoutShellProps) {
	const isMobile = useIsMobile();
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const { isCollapsed, setIsCollapsed, toggleCollapsed } = useSidebarState(defaultCollapsed);
	const {
		sidebarWidth,
		handleMouseDown: onResizeMouseDown,
		isDragging: isResizing,
	} = useSidebarResize();

	// Memoize context value to prevent unnecessary re-renders
	const sidebarContextValue = useMemo(
		() => ({ isCollapsed, setIsCollapsed, toggleCollapsed, sidebarWidth }),
		[isCollapsed, setIsCollapsed, toggleCollapsed, sidebarWidth]
	);

	// Mobile layout
	if (isMobile) {
		return (
			<SidebarProvider value={sidebarContextValue}>
				<TooltipProvider delayDuration={0}>
					<div className={cn("flex h-screen w-full flex-col bg-main-panel", className)}>
						<Header
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
							onChatRename={onChatRename}
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
							isLoadingChats={isLoadingChats}
						/>

						<main className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
							{children}
						</main>

						{/* Mobile Inbox Sidebar - only render when open to avoid scroll blocking */}
						{inbox?.isOpen && (
							<InboxSidebar
								open={inbox.isOpen}
								onOpenChange={inbox.onOpenChange}
								comments={inbox.comments}
								status={inbox.status}
								totalUnreadCount={inbox.totalUnreadCount}
								onCloseMobileSidebar={() => setMobileMenuOpen(false)}
							/>
						)}

						{/* Mobile Documents Sidebar - slide-out panel */}
						{documentsPanel && (
							<DocumentsSidebar
								open={documentsPanel.open}
								onOpenChange={documentsPanel.onOpenChange}
							/>
						)}

						{/* Mobile Announcements Sidebar */}
						{announcementsPanel?.open && (
							<AnnouncementsSidebar
								open={announcementsPanel.open}
								onOpenChange={announcementsPanel.onOpenChange}
								onCloseMobileSidebar={() => setMobileMenuOpen(false)}
							/>
						)}

						{/* Mobile All Shared Chats - slide-out panel */}
						{allSharedChatsPanel && (
							<AllSharedChatsSidebar
								open={allSharedChatsPanel.open}
								onOpenChange={allSharedChatsPanel.onOpenChange}
								searchSpaceId={allSharedChatsPanel.searchSpaceId}
								onCloseMobileSidebar={() => setMobileMenuOpen(false)}
							/>
						)}

						{/* Mobile All Private Chats - slide-out panel */}
						{allPrivateChatsPanel && (
							<AllPrivateChatsSidebar
								open={allPrivateChatsPanel.open}
								onOpenChange={allPrivateChatsPanel.onOpenChange}
								searchSpaceId={allPrivateChatsPanel.searchSpaceId}
								onCloseMobileSidebar={() => setMobileMenuOpen(false)}
							/>
						)}
					</div>
				</TooltipProvider>
			</SidebarProvider>
		);
	}

	const anySlideOutOpen =
		inbox?.isOpen ||
		announcementsPanel?.open ||
		allSharedChatsPanel?.open ||
		allPrivateChatsPanel?.open;

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

					{/* Sidebar + slide-out panels share one container; overflow visible so panels can overlay main content */}
					<div
						className={cn(
							"relative hidden md:flex shrink-0 border bg-sidebar z-20 transition-[border-radius,border-color] duration-200",
							anySlideOutOpen
								? "rounded-l-xl border-r-0 delay-0"
								: "rounded-xl delay-150"
						)}
					>
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
							onChatRename={onChatRename}
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
							className={cn(
								"flex shrink-0 transition-[border-radius] duration-200",
								anySlideOutOpen ? "rounded-l-xl delay-0" : "rounded-xl delay-150"
							)}
							isLoadingChats={isLoadingChats}
							sidebarWidth={sidebarWidth}
							isResizing={isResizing}
						/>

						{/* Slide-out panels render as siblings next to the sidebar */}
						{inbox && (
							<InboxSidebar
								open={inbox.isOpen}
								onOpenChange={inbox.onOpenChange}
								comments={inbox.comments}
								status={inbox.status}
								totalUnreadCount={inbox.totalUnreadCount}
							/>
						)}

						{announcementsPanel && (
							<AnnouncementsSidebar
								open={announcementsPanel.open}
								onOpenChange={announcementsPanel.onOpenChange}
							/>
						)}

						{allSharedChatsPanel && (
							<AllSharedChatsSidebar
								open={allSharedChatsPanel.open}
								onOpenChange={allSharedChatsPanel.onOpenChange}
								searchSpaceId={allSharedChatsPanel.searchSpaceId}
							/>
						)}

						{allPrivateChatsPanel && (
							<AllPrivateChatsSidebar
								open={allPrivateChatsPanel.open}
								onOpenChange={allPrivateChatsPanel.onOpenChange}
								searchSpaceId={allPrivateChatsPanel.searchSpaceId}
							/>
						)}
					</div>

					{/* Resize handle — negative margins eat the flex gap so spacing stays unchanged */}
					{!isCollapsed && (
						<div
							role="slider"
							aria-label="Resize sidebar"
							aria-valuemin={0}
							aria-valuemax={100}
							aria-valuenow={50}
							tabIndex={0}
							onMouseDown={onResizeMouseDown}
							className="hidden md:block h-full cursor-col-resize z-30"
							style={{ width: 8, marginLeft: -8, marginRight: -8 }}
						/>
					)}

					{/* Main content panel */}
					<div className="relative flex flex-1 flex-col rounded-xl border bg-main-panel overflow-hidden min-w-0">
						<Header />

						<div className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
							{children}
						</div>
					</div>

					{/* Right panel — tabbed Sources/Report (desktop only) */}
					{documentsPanel && (
						<RightPanel
							documentsPanel={{
								open: documentsPanel.open,
								onOpenChange: documentsPanel.onOpenChange,
							}}
						/>
					)}
				</div>
			</TooltipProvider>
		</SidebarProvider>
	);
}
