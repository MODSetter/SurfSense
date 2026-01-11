import type { LucideIcon } from "lucide-react";

export interface Workspace {
	id: number;
	name: string;
	description?: string | null;
	isOwner: boolean;
	memberCount: number;
}

export interface User {
	email: string;
	name?: string;
}

export interface NavItem {
	title: string;
	url: string;
	icon: LucideIcon;
	isActive?: boolean;
	badge?: string | number;
}

export interface ChatItem {
	id: number;
	name: string;
	url: string;
	isActive?: boolean;
}

export interface NoteItem {
	id: number;
	name: string;
	url: string;
	isActive?: boolean;
	isReindexing?: boolean;
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
	searchSpaceId?: string;
}

export interface NotesSectionProps {
	notes: NoteItem[];
	activeNoteId?: number | null;
	onNoteSelect: (note: NoteItem) => void;
	onNoteDelete?: (note: NoteItem) => void;
	onAddNote?: () => void;
	onViewAllNotes?: () => void;
	searchSpaceId?: string;
}

export interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export interface SidebarUserProfileProps {
	user: User;
	searchSpaceId?: string;
	onSettings?: () => void;
	onInviteMembers?: () => void;
	onSwitchWorkspace?: () => void;
	onToggleTheme?: () => void;
	onLogout?: () => void;
	theme?: string;
}

export interface SidebarProps {
	workspace: Workspace | null;
	searchSpaceId?: string;
	navItems: NavItem[];
	chats: ChatItem[];
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onViewAllChats?: () => void;
	notes: NoteItem[];
	activeNoteId?: number | null;
	onNoteSelect: (note: NoteItem) => void;
	onNoteDelete?: (note: NoteItem) => void;
	onAddNote?: () => void;
	onViewAllNotes?: () => void;
	user: User;
	theme?: string;
	onSettings?: () => void;
	onInviteMembers?: () => void;
	onSwitchWorkspace?: () => void;
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
