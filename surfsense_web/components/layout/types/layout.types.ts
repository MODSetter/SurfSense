import type { LucideIcon } from "lucide-react";
import type { DocumentsProcessingStatus } from "@/hooks/use-documents-processing";

export interface Workspace {
	id: number;
	name: string;
	description?: string | null;
	isOwner: boolean;
	memberCount: number;
	createdAt?: string;
}

export interface User {
	email: string;
	name?: string;
	avatarUrl?: string;
}

export interface NavItem {
	title: string;
	url: string;
	icon: LucideIcon;
	isActive?: boolean;
	badge?: string | number;
	statusIndicator?: DocumentsProcessingStatus;
}

export interface ChatItem {
	id: number;
	name: string;
	url: string;
	isActive?: boolean;
	visibility?: "PRIVATE" | "SEARCH_SPACE";
	isOwnThread?: boolean;
	archived?: boolean;
}

export interface PageUsage {
	pagesUsed: number;
	pagesLimit: number;
}

export interface IconRailProps {
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
	onAddWorkspace: () => void;
	className?: string;
}

export interface SidebarHeaderProps {
	workspace: Workspace | null;
	onSettings?: () => void;
}

export interface SidebarSectionProps {
	title: string;
	defaultOpen?: boolean;
	children: React.ReactNode;
	action?: React.ReactNode;
}

export interface NavSectionProps {
	items: NavItem[];
	onItemClick?: (item: NavItem) => void;
}

export interface ChatsSectionProps {
	chats: ChatItem[];
	activeChatId?: number | null;
	onChatSelect: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onViewAllChats?: () => void;
	workspaceId?: string;
}

export interface SidebarUserProfileProps {
	user: User;
	workspaceId?: string;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onSwitchWorkspace?: () => void;
	onToggleTheme?: () => void;
	onLogout?: () => void;
	theme?: string;
}

export interface SidebarProps {
	workspace: Workspace | null;
	workspaceId?: string;
	navItems: NavItem[];
	chats: ChatItem[];
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onViewAllChats?: () => void;
	user: User;
	theme?: string;
	onSettings?: () => void;
	onManageMembers?: () => void;
	onToggleTheme?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	className?: string;
}

export interface LayoutShellProps {
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
	onAddWorkspace: () => void;
	sidebarProps: Omit<SidebarProps, "className">;
	children: React.ReactNode;
	className?: string;
}
