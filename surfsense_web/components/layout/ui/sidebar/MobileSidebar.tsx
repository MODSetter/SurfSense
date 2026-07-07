"use client";

import { PanelLeft, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import type { ChatItem, NavItem, PageUsage, User, Workspace } from "../../types/layout.types";
import { WorkspaceAvatar } from "../icon-rail/WorkspaceAvatar";
import { NotificationsDropdown, type NotificationsDropdownData } from "./NotificationsDropdown";
import { Sidebar } from "./Sidebar";
import { SidebarUserProfile } from "./SidebarUserProfile";

interface MobileSidebarProps {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
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
	isAllChatsActive?: boolean;
	user: User;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onUserSettings?: () => void;
	onAnnouncements?: () => void;
	announcementUnreadCount?: number;
	notifications?: NotificationsDropdownData;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	isLoadingChats?: boolean;
}

export function MobileSidebarTrigger({ onClick }: { onClick: () => void }) {
	return (
		<Button
			variant="ghost"
			size="icon"
			onClick={onClick}
			className="md:hidden h-8 w-8 shrink-0 text-muted-foreground hover:bg-transparent hover:text-muted-foreground"
		>
			<PanelLeft className="h-4 w-4" />
			<span className="sr-only">Open menu</span>
		</Button>
	);
}

export function MobileSidebar({
	isOpen,
	onOpenChange,
	workspaces,
	activeWorkspaceId,
	onWorkspaceSelect,

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
	isAllChatsActive = false,
	user,
	onSettings,
	onManageMembers,
	onUserSettings,
	onAnnouncements,
	announcementUnreadCount = 0,
	notifications,
	onLogout,
	pageUsage,
	theme,
	setTheme,
	isLoadingChats = false,
}: MobileSidebarProps) {
	const handleWorkspaceSelect = (id: number) => {
		onWorkspaceSelect(id);
	};

	const handleNavItemClick = (item: NavItem) => {
		onNavItemClick?.(item);
		onOpenChange(false);
	};

	const handleChatSelect = (chat: ChatItem) => {
		onChatSelect(chat);
		onOpenChange(false);
	};

	return (
		<Sheet open={isOpen} onOpenChange={onOpenChange}>
			<SheetContent
				side="left"
				className="w-[340px] p-0 flex flex-row gap-0 bg-panel [&>button]:hidden"
			>
				<SheetTitle className="sr-only">Navigation</SheetTitle>

				{/* Vertical Workspaces Rail - left side */}
				<div className="flex h-full w-14 shrink-0 flex-col items-center border-r bg-rail">
					<ScrollArea className="w-full flex-1">
						<div className="flex flex-col items-center gap-2 px-1.5 py-3">
							{workspaces.map((space) => (
								<WorkspaceAvatar
									key={space.id}
									name={space.name}
									isActive={space.id === activeWorkspaceId}
									isShared={space.memberCount > 1}
									isOwner={space.isOwner}
									onClick={() => handleWorkspaceSelect(space.id)}
									size="md"
									disableTooltip
								/>
							))}
							<Button
								variant="ghost"
								size="icon"
								onClick={onAddWorkspace}
								className="h-10 w-10 shrink-0 rounded-lg border-2 border-dashed border-muted-foreground/30 hover:border-muted-foreground/50"
							>
								<Plus className="h-5 w-5 text-muted-foreground" />
								<span className="sr-only">Add workspace</span>
							</Button>
						</div>
					</ScrollArea>
					<SidebarUserProfile
						user={user}
						onUserSettings={
							onUserSettings
								? () => {
										onOpenChange(false);
										onUserSettings();
									}
								: undefined
						}
						onAnnouncements={
							onAnnouncements
								? () => {
										onOpenChange(false);
										onAnnouncements();
									}
								: undefined
						}
						announcementUnreadCount={announcementUnreadCount}
						onLogout={onLogout}
						isCollapsed
						theme={theme}
						setTheme={setTheme}
						topContent={
							notifications ? (
								<NotificationsDropdown
									notifications={notifications}
									onCloseMobileSidebar={() => onOpenChange(false)}
								/>
							) : undefined
						}
					/>
				</div>

				{/* Sidebar Content - right side */}
				<div className="flex-1 overflow-hidden flex flex-col [&>*]:!w-full">
					<Sidebar
						workspace={workspace}
						isCollapsed={false}
						onToggleCollapse={() => onOpenChange(false)}
						navItems={navItems}
						onNavItemClick={handleNavItemClick}
						chats={chats}
						activeChatId={activeChatId}
						onNewChat={() => {
							onNewChat();
							onOpenChange(false);
						}}
						onChatSelect={handleChatSelect}
						onChatPrefetch={onChatPrefetch}
						onChatRename={onChatRename}
						onChatDelete={onChatDelete}
						onChatArchive={onChatArchive}
						onViewAllChats={
							onViewAllChats
								? () => {
										onOpenChange(false);
										onViewAllChats();
									}
								: undefined
						}
						isAllChatsActive={isAllChatsActive}
						user={user}
						onSettings={
							onSettings
								? () => {
										onOpenChange(false);
										onSettings();
									}
								: undefined
						}
						onManageMembers={
							onManageMembers
								? () => {
										onOpenChange(false);
										onManageMembers();
									}
								: undefined
						}
						onUserSettings={
							onUserSettings
								? () => {
										onOpenChange(false);
										onUserSettings();
									}
								: undefined
						}
						onAnnouncements={
							onAnnouncements
								? () => {
										onOpenChange(false);
										onAnnouncements();
									}
								: undefined
						}
						onNavigate={() => onOpenChange(false)}
						announcementUnreadCount={announcementUnreadCount}
						onLogout={onLogout}
						pageUsage={pageUsage}
						theme={theme}
						setTheme={setTheme}
						className="w-full border-none"
						isLoadingChats={isLoadingChats}
						disableTooltips
						renderUserProfile={false}
					/>
				</div>
			</SheetContent>
		</Sheet>
	);
}
