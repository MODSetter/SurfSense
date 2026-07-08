"use client";

import { useAtomValue } from "jotai";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { activeTabAtom, type Tab } from "@/atoms/tabs/tabs.atom";
import { Logo } from "@/components/Logo";
import { Spinner } from "@/components/ui/spinner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-mobile";
import { useElectronAPI } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";
import { SidebarProvider, useSidebarState } from "../../hooks";
import {
	SIDEBAR_MAX_WIDTH,
	SIDEBAR_MIN_WIDTH,
	useSidebarResize,
} from "../../hooks/useSidebarResize";
import type { ChatItem, NavItem, PageUsage, User, Workspace } from "../../types/layout.types";
import { Header } from "../header";
import { IconRail } from "../icon-rail";
import {
	RightPanel,
	RightPanelExpandButton,
	RightPanelToggleButton,
} from "../right-panel/RightPanel";
import { MobileSidebar, MobileSidebarTrigger, Sidebar, SidebarCollapseButton } from "../sidebar";
import type { NotificationsDropdownData } from "../sidebar/NotificationsDropdown";
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

interface LayoutShellProps {
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
	onWorkspaceDelete?: (workspace: Workspace) => void;
	onWorkspaceSettings?: (workspace: Workspace) => void;
	onAddWorkspace: () => void;
	workspace: Workspace | null;
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
	isAllChatsPage?: boolean;
	useWorkspacePanel?: boolean;
	workspacePanelViewportClassName?: string;
	workspacePanelContentClassName?: string;
	children: React.ReactNode;
	className?: string;
	notifications?: NotificationsDropdownData;
	isLoadingChats?: boolean;
	onTabSwitch?: (tab: Tab) => void;
	onTabPrefetch?: (tab: Tab) => void;
	playgroundSidebar?: React.ReactNode;
}

function MainContentPanel({
	isChatPage,
	onTabSwitch,
	onTabPrefetch,
	onNewChat,
	showRightPanelExpandButton = true,
	showTopBorder = false,
	children,
}: {
	isChatPage: boolean;
	onTabSwitch?: (tab: Tab) => void;
	onTabPrefetch?: (tab: Tab) => void;
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
				onTabPrefetch={onTabPrefetch}
				onNewChat={onNewChat}
				rightActions={showRightPanelExpandButton ? <RightPanelExpandButton /> : null}
				className="min-w-0"
			/>
			<div className="relative flex flex-1 flex-col bg-panel overflow-hidden min-w-0">
				<Header />

				{isDocumentTab && activeTab.documentId && activeTab.workspaceId ? (
					<div className="flex-1 overflow-hidden">
						<DocumentTabContent
							key={activeTab.documentId}
							documentId={activeTab.documentId}
							workspaceId={activeTab.workspaceId}
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
	workspaces,
	activeWorkspaceId,
	onWorkspaceSelect,
	onWorkspaceDelete,
	onWorkspaceSettings,
	onAddWorkspace,
	workspace,
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
	isAllChatsPage = false,
	useWorkspacePanel = false,
	workspacePanelViewportClassName,
	workspacePanelContentClassName,
	children,
	className,
	notifications,
	isLoadingChats = false,
	onTabSwitch,
	onTabPrefetch,
	playgroundSidebar,
}: LayoutShellProps) {
	const isMobile = useIsMobile();
	const electronAPI = useElectronAPI();
	const isMacDesktop = electronAPI?.versions.platform === "darwin";
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const [isPlaygroundSidebarCollapsed, setIsPlaygroundSidebarCollapsed] = useState(false);
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
	const handlePlaygroundSidebarToggle = () => {
		setIsPlaygroundSidebarCollapsed((collapsed) => !collapsed);
	};

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
							workspaces={workspaces}
							activeWorkspaceId={activeWorkspaceId}
							onWorkspaceSelect={onWorkspaceSelect}
							onAddWorkspace={onAddWorkspace}
							workspace={workspace}
							navItems={navItems}
							onNavItemClick={onNavItemClick}
							chats={chats}
							activeChatId={activeChatId}
							onNewChat={onNewChat}
							onChatSelect={onChatSelect}
							onChatPrefetch={onChatPrefetch}
							onChatRename={onChatRename}
							onChatDelete={onChatDelete}
							onChatArchive={onChatArchive}
							onViewAllChats={onViewAllChats}
							isAllChatsActive={isAllChatsPage}
							user={user}
							onSettings={onSettings}
							onManageMembers={onManageMembers}
							onUserSettings={onUserSettings}
							onAnnouncements={onAnnouncements}
							announcementUnreadCount={announcementUnreadCount}
							notifications={notifications}
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
								workspaces={workspaces}
								activeWorkspaceId={activeWorkspaceId}
								onWorkspaceSelect={onWorkspaceSelect}
								onWorkspaceDelete={onWorkspaceDelete}
								onWorkspaceSettings={onWorkspaceSettings}
								onAddWorkspace={onAddWorkspace}
								isSingleRailMode={false}
								user={user}
								onUserSettings={onUserSettings}
								onAnnouncements={onAnnouncements}
								announcementUnreadCount={announcementUnreadCount}
								notifications={notifications}
								onLogout={onLogout}
								theme={theme}
								setTheme={setTheme}
							/>
						</div>

						{/* Sidebar + slide-out panels share one container; overflow visible so panels can overlay main content. Negative right margin closes the flex gap so the sidebar sits flush against the main panel, separated only by a border. */}
						<div
							className={cn(
								"relative hidden md:flex shrink-0 z-20 -mr-2 bg-panel",
								isMacDesktop ? "rounded-tl-xl border-l border-t border-r" : "border-r"
							)}
						>
							<Sidebar
								workspace={workspace}
								isCollapsed={isCollapsed}
								onToggleCollapse={toggleCollapsed}
								navItems={navItems}
								onNavItemClick={onNavItemClick}
								onPlaygroundItemClick={
									playgroundSidebar ? handlePlaygroundSidebarToggle : undefined
								}
								chats={chats}
								activeChatId={activeChatId}
								onNewChat={onNewChat}
								onChatSelect={onChatSelect}
								onChatPrefetch={onChatPrefetch}
								onChatRename={onChatRename}
								onChatDelete={onChatDelete}
								onChatArchive={onChatArchive}
								onViewAllChats={onViewAllChats}
								isAllChatsActive={isAllChatsPage}
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
						</div>

						{playgroundSidebar ? (
							<div
								aria-hidden={isPlaygroundSidebarCollapsed}
								className={cn(
									"hidden md:flex shrink-0 overflow-hidden -mr-2 bg-panel transition-[width,opacity] duration-200 ease-out",
									isPlaygroundSidebarCollapsed
										? "w-0 opacity-0 pointer-events-none"
										: "w-[240px] opacity-100",
									isMacDesktop && !isPlaygroundSidebarCollapsed && "border-t"
								)}
							>
								<div className="w-[240px] shrink-0">{playgroundSidebar}</div>
							</div>
						) : null}

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
										onTabPrefetch={onTabPrefetch}
										onNewChat={onNewChat}
										showRightPanelExpandButton={!isMacDesktop}
										showTopBorder={isMacDesktop}
									>
										{children}
									</MainContentPanel>

									{/* Right panel — Report/Editor/Citations/Artifacts (desktop only) */}
									<RightPanel showTopBorder={isMacDesktop} />
								</>
							)}
						</DesktopWorkspaceRegion>
					</div>
				</div>
			</TooltipProvider>
		</SidebarProvider>
	);
}
