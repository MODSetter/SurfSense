"use client";

import { useAtomValue } from "jotai";
import { AnimatePresence, motion } from "motion/react";
import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import { activeTabAtom, type Tab } from "@/atoms/tabs/tabs.atom";
import { Logo } from "@/components/Logo";
import { Spinner } from "@/components/ui/spinner";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { InboxItem } from "@/hooks/use-inbox";
import { useIsMobile } from "@/hooks/use-mobile";
import { useElectronAPI } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";
import { SidebarProvider, useSidebarState } from "../../hooks";
import {
	SIDEBAR_MAX_WIDTH,
	SIDEBAR_MIN_WIDTH,
	useSidebarResize,
} from "../../hooks/useSidebarResize";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { Header } from "../header";
import { IconRail } from "../icon-rail";
import {
	RightPanel,
	RightPanelExpandButton,
	RightPanelToggleButton,
} from "../right-panel/RightPanel";
import {
	AllChatsSidebarContent,
	DocumentsSidebar,
	InboxSidebarContent,
	MobileSidebar,
	MobileSidebarTrigger,
	Sidebar,
	SidebarCollapseButton,
} from "../sidebar";
import { SidebarSlideOutPanel } from "../sidebar/SidebarSlideOutPanel";
import { TabBar } from "../tabs/TabBar";
import { WorkspacePanel } from "./WorkspacePanel";

const DocumentTabContent = dynamic(
	() => import("../tabs/DocumentTabContent").then((m) => ({ default: m.DocumentTabContent })),
	{
		ssr: false,
		loading: () => (
			<div className="flex-1 flex items-center justify-center h-full">
				<Spinner size="lg" />
			</div>
		),
	}
);

function MacDesktopTitleBar({
	isSidebarCollapsed,
	onToggleSidebar,
	disableRightPanelToggle = false,
}: {
	isSidebarCollapsed: boolean;
	onToggleSidebar: () => void;
	disableRightPanelToggle?: boolean;
}) {
	return (
		<div className="flex h-9 shrink-0 items-center bg-rail px-2 [app-region:drag] [-webkit-app-region:drag]">
			<div className="ml-[72px] flex h-full items-center [app-region:no-drag] [-webkit-app-region:no-drag]">
				<SidebarCollapseButton
					isCollapsed={isSidebarCollapsed}
					onToggle={onToggleSidebar}
					className="h-6 w-6 rounded-md"
					iconClassName="h-3.5 w-3.5"
				/>
			</div>
			<div className="ml-auto flex h-full items-center [app-region:no-drag] [-webkit-app-region:no-drag]">
				<RightPanelToggleButton
					disabled={disableRightPanelToggle}
					className="h-6 w-6 rounded-md"
					iconClassName="h-3.5 w-3.5"
				/>
			</div>
		</div>
	);
}

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

export type ActiveSlideoutPanel = "inbox" | "chats" | null;

// Inbox-related props — per-tab data sources with independent loading/pagination
interface InboxProps {
	isOpen: boolean;
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
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatRename?: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onChatArchive?: (chat: ChatItem) => void;
	onViewAllChats?: () => void;
	user: User;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onUserSettings?: () => void;
	onAnnouncements?: () => void;
	announcementUnreadCount?: number;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	defaultCollapsed?: boolean;
	isChatPage?: boolean;
	useWorkspacePanel?: boolean;
	workspacePanelViewportClassName?: string;
	workspacePanelContentClassName?: string;
	children: React.ReactNode;
	className?: string;
	// Unified slide-out panel state
	activeSlideoutPanel?: ActiveSlideoutPanel;
	onSlideoutPanelChange?: (panel: ActiveSlideoutPanel) => void;
	// Inbox props
	inbox?: InboxProps;
	isLoadingChats?: boolean;
	// All chats panel props
	allChatsPanel?: {
		searchSpaceId: string;
	};
	documentsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
	};
	onTabSwitch?: (tab: Tab) => void;
}

function MainContentPanel({
	isChatPage,
	onTabSwitch,
	onNewChat,
	showRightPanelExpandButton = true,
	showTopBorder = false,
	children,
}: {
	isChatPage: boolean;
	onTabSwitch?: (tab: Tab) => void;
	onNewChat?: () => void;
	showRightPanelExpandButton?: boolean;
	showTopBorder?: boolean;
	children: React.ReactNode;
}) {
	const activeTab = useAtomValue(activeTabAtom);
	const isDocumentTab = activeTab?.type === "document";

	return (
		<div
			className={cn("relative isolate flex flex-1 flex-col min-w-0", showTopBorder && "border-t")}
		>
			<TabBar
				onTabSwitch={onTabSwitch}
				onNewChat={onNewChat}
				rightActions={showRightPanelExpandButton ? <RightPanelExpandButton /> : null}
				className="min-w-0"
			/>
			<div className="relative flex flex-1 flex-col bg-panel overflow-hidden min-w-0">
				<Header />

				{isDocumentTab && activeTab.documentId && activeTab.searchSpaceId ? (
					<div className="flex-1 overflow-hidden">
						<DocumentTabContent
							key={activeTab.documentId}
							documentId={activeTab.documentId}
							searchSpaceId={activeTab.searchSpaceId}
							title={activeTab.title}
						/>
					</div>
				) : (
					<div className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
						{children}
					</div>
				)}
			</div>
		</div>
	);
}

function DesktopWorkspaceRegion({ children }: { children: React.ReactNode }) {
	return <div className="flex h-full min-w-0 flex-1 -mr-2">{children}</div>;
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
	activeChatId,
	onNewChat,
	onChatSelect,
	onChatRename,
	onChatDelete,
	onChatArchive,
	onViewAllChats,
	user,
	onSettings,
	onManageMembers,
	onUserSettings,
	onAnnouncements,
	announcementUnreadCount = 0,
	onLogout,
	pageUsage,
	theme,
	setTheme,
	defaultCollapsed = false,
	isChatPage = false,
	useWorkspacePanel = false,
	workspacePanelViewportClassName,
	workspacePanelContentClassName,
	children,
	className,
	activeSlideoutPanel = null,
	onSlideoutPanelChange,
	inbox,
	isLoadingChats = false,
	allChatsPanel,
	documentsPanel,
	onTabSwitch,
}: LayoutShellProps) {
	const isMobile = useIsMobile();
	const electronAPI = useElectronAPI();
	const isMacDesktop = electronAPI?.versions.platform === "darwin";
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const { isCollapsed, setIsCollapsed, toggleCollapsed } = useSidebarState(defaultCollapsed);
	const {
		sidebarWidth,
		handlePointerDown: onResizePointerDown,
		isDragging: isResizing,
	} = useSidebarResize();

	// Memoize context value to prevent unnecessary re-renders
	const sidebarContextValue = useMemo(
		() => ({ isCollapsed, setIsCollapsed, toggleCollapsed }),
		[isCollapsed, setIsCollapsed, toggleCollapsed]
	);

	const closeSlideout = useCallback(
		(open: boolean) => {
			if (!open) onSlideoutPanelChange?.(null);
		},
		[onSlideoutPanelChange]
	);

	const anySlideOutOpen = activeSlideoutPanel !== null;

	const panelAriaLabel =
		activeSlideoutPanel === "inbox" ? "Inbox" : activeSlideoutPanel === "chats" ? "Chats" : "Panel";

	// Mobile layout
	if (isMobile) {
		return (
			<SidebarProvider value={sidebarContextValue}>
				<TooltipProvider delayDuration={0}>
					<div className={cn("flex h-screen w-full flex-col bg-panel", className)}>
						<Header
							mobileMenuTrigger={<MobileSidebarTrigger onClick={() => setMobileMenuOpen(true)} />}
						/>

						<MobileSidebar
							isOpen={mobileMenuOpen}
							onOpenChange={setMobileMenuOpen}
							searchSpaces={searchSpaces}
							activeSearchSpaceId={activeSearchSpaceId}
							onSearchSpaceSelect={onSearchSpaceSelect}
							onAddSearchSpace={onAddSearchSpace}
							searchSpace={searchSpace}
							navItems={navItems}
							onNavItemClick={onNavItemClick}
							chats={chats}
							activeChatId={activeChatId}
							onNewChat={onNewChat}
							onChatSelect={onChatSelect}
							onChatRename={onChatRename}
							onChatDelete={onChatDelete}
							onChatArchive={onChatArchive}
							onViewAllChats={onViewAllChats}
							isChatsPanelOpen={activeSlideoutPanel === "chats"}
							user={user}
							onSettings={onSettings}
							onManageMembers={onManageMembers}
							onUserSettings={onUserSettings}
							onAnnouncements={onAnnouncements}
							announcementUnreadCount={announcementUnreadCount}
							onLogout={onLogout}
							pageUsage={pageUsage}
							theme={theme}
							setTheme={setTheme}
							isLoadingChats={isLoadingChats}
						/>

						{useWorkspacePanel ? (
							<WorkspacePanel
								viewportClassName={workspacePanelViewportClassName}
								contentClassName={workspacePanelContentClassName}
							>
								{children}
							</WorkspacePanel>
						) : (
							<main className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
								{children}
							</main>
						)}

						{/* Mobile unified slide-out panel */}
						<SidebarSlideOutPanel
							open={anySlideOutOpen}
							onOpenChange={closeSlideout}
							ariaLabel={panelAriaLabel}
						>
							<AnimatePresence mode="popLayout" initial={false}>
								{activeSlideoutPanel === "inbox" && inbox && (
									<motion.div
										key="inbox"
										className="h-full flex flex-col"
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										transition={{ duration: 0.15 }}
									>
										<InboxSidebarContent
											onOpenChange={(open) => closeSlideout(open)}
											comments={inbox.comments}
											status={inbox.status}
											totalUnreadCount={inbox.totalUnreadCount}
											onCloseMobileSidebar={() => setMobileMenuOpen(false)}
										/>
									</motion.div>
								)}
								{activeSlideoutPanel === "chats" && allChatsPanel && (
									<motion.div
										key="chats"
										className="h-full flex flex-col"
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										transition={{ duration: 0.15 }}
									>
										<AllChatsSidebarContent
											onOpenChange={(open) => closeSlideout(open)}
											searchSpaceId={allChatsPanel.searchSpaceId}
											onCloseMobileSidebar={() => setMobileMenuOpen(false)}
										/>
									</motion.div>
								)}
							</AnimatePresence>
						</SidebarSlideOutPanel>

						{/* Mobile Documents Sidebar - separate (not part of slide-out group) */}
						{documentsPanel && (
							<DocumentsSidebar
								open={documentsPanel.open}
								onOpenChange={documentsPanel.onOpenChange}
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
				<div className={cn("flex h-screen w-full flex-col overflow-hidden bg-rail", className)}>
					{isMacDesktop ? (
						<MacDesktopTitleBar
							isSidebarCollapsed={isCollapsed}
							onToggleSidebar={toggleCollapsed}
							disableRightPanelToggle={useWorkspacePanel}
						/>
					) : null}
					<div className="flex min-h-0 flex-1 w-full gap-2 px-2 py-0 overflow-hidden">
						<div
							className={cn(
								"hidden md:flex overflow-hidden -mr-2 pr-2 bg-rail",
								!isMacDesktop && "border-r"
							)}
						>
							<IconRail
								searchSpaces={searchSpaces}
								activeSearchSpaceId={activeSearchSpaceId}
								onSearchSpaceSelect={onSearchSpaceSelect}
								onSearchSpaceDelete={onSearchSpaceDelete}
								onSearchSpaceSettings={onSearchSpaceSettings}
								onAddSearchSpace={onAddSearchSpace}
								isSingleRailMode={false}
								user={user}
								onUserSettings={onUserSettings}
								onAnnouncements={onAnnouncements}
								announcementUnreadCount={announcementUnreadCount}
								onLogout={onLogout}
								theme={theme}
								setTheme={setTheme}
							/>
						</div>

						{/* Sidebar + slide-out panels share one container; overflow visible so panels can overlay main content. Negative right margin closes the flex gap so the sidebar sits flush against the main panel, separated only by a border. */}
						<div
							className={cn(
								"relative hidden md:flex shrink-0 z-20 -mr-2 bg-panel",
								isMacDesktop ? "rounded-tl-xl border-t border-r border-l" : "border-r"
							)}
						>
							<Sidebar
								searchSpace={searchSpace}
								isCollapsed={isCollapsed}
								onToggleCollapse={toggleCollapsed}
								navItems={navItems}
								onNavItemClick={onNavItemClick}
								chats={chats}
								activeChatId={activeChatId}
								onNewChat={onNewChat}
								onChatSelect={onChatSelect}
								onChatRename={onChatRename}
								onChatDelete={onChatDelete}
								onChatArchive={onChatArchive}
								onViewAllChats={onViewAllChats}
								isChatsPanelOpen={activeSlideoutPanel === "chats"}
								user={user}
								onSettings={onSettings}
								onManageMembers={onManageMembers}
								onUserSettings={onUserSettings}
								onAnnouncements={onAnnouncements}
								announcementUnreadCount={announcementUnreadCount}
								onLogout={onLogout}
								pageUsage={pageUsage}
								theme={theme}
								setTheme={setTheme}
								renderUserProfile={false}
								renderCollapseButton={!isMacDesktop}
								collapsedHeaderContent={
									isMacDesktop ? (
										<Logo disableLink priority className="h-7 w-7 rounded-md" />
									) : undefined
								}
								className={cn("flex shrink-0", isMacDesktop && "rounded-tl-xl")}
								isLoadingChats={isLoadingChats}
								sidebarWidth={sidebarWidth}
								isResizing={isResizing}
							/>

							{!isCollapsed && (
								<hr
									aria-orientation="vertical"
									aria-label="Resize sidebar"
									aria-valuemin={SIDEBAR_MIN_WIDTH}
									aria-valuemax={SIDEBAR_MAX_WIDTH}
									aria-valuenow={sidebarWidth}
									tabIndex={0}
									onPointerDown={onResizePointerDown}
									style={{ touchAction: "none" }}
									className={cn(
										"absolute top-0 right-0 h-full w-4 translate-x-1/2 z-50 m-0 border-0 bg-transparent p-0 select-none cursor-col-resize",
										"after:content-[''] after:absolute after:inset-y-0 after:left-1/2 after:w-px after:-translate-x-1/2 after:bg-transparent hover:after:bg-border/80 after:transition-colors",
										isResizing && "after:bg-border"
									)}
								/>
							)}

							{/* Unified slide-out panel — shell stays open, content cross-fades */}
							<SidebarSlideOutPanel
								open={anySlideOutOpen}
								onOpenChange={closeSlideout}
								ariaLabel={panelAriaLabel}
							>
								<AnimatePresence mode="popLayout" initial={false}>
									{activeSlideoutPanel === "inbox" && inbox && (
										<motion.div
											key="inbox"
											className="h-full flex flex-col"
											initial={{ opacity: 0 }}
											animate={{ opacity: 1 }}
											exit={{ opacity: 0 }}
											transition={{ duration: 0.15 }}
										>
											<InboxSidebarContent
												onOpenChange={(open) => closeSlideout(open)}
												comments={inbox.comments}
												status={inbox.status}
												totalUnreadCount={inbox.totalUnreadCount}
											/>
										</motion.div>
									)}
									{activeSlideoutPanel === "chats" && allChatsPanel && (
										<motion.div
											key="chats"
											className="h-full flex flex-col"
											initial={{ opacity: 0 }}
											animate={{ opacity: 1 }}
											exit={{ opacity: 0 }}
											transition={{ duration: 0.15 }}
										>
											<AllChatsSidebarContent
												onOpenChange={(open) => closeSlideout(open)}
												searchSpaceId={allChatsPanel.searchSpaceId}
											/>
										</motion.div>
									)}
								</AnimatePresence>
							</SidebarSlideOutPanel>
						</div>

						<DesktopWorkspaceRegion>
							{useWorkspacePanel ? (
								<WorkspacePanel
									className={isMacDesktop ? "border-t" : undefined}
									viewportClassName={workspacePanelViewportClassName}
									contentClassName={workspacePanelContentClassName}
								>
									{children}
								</WorkspacePanel>
							) : (
								<>
									{/* Main content panel */}
									<MainContentPanel
										isChatPage={isChatPage}
										onTabSwitch={onTabSwitch}
										onNewChat={onNewChat}
										showRightPanelExpandButton={!isMacDesktop}
										showTopBorder={isMacDesktop}
									>
										{children}
									</MainContentPanel>

									{/* Right panel — tabbed Sources/Report (desktop only) */}
									{documentsPanel ? (
										<RightPanel
											documentsPanel={{
												open: documentsPanel.open,
												onOpenChange: documentsPanel.onOpenChange,
											}}
											showCollapseButton={!isMacDesktop}
											showTopBorder={isMacDesktop}
										/>
									) : null}
								</>
							)}
						</DesktopWorkspaceRegion>
					</div>
				</div>
			</TooltipProvider>
		</SidebarProvider>
	);
}
