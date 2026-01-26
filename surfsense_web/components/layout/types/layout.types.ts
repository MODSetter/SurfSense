import type { LucideIcon } from "lucide-react";

export interface SearchSpace {
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
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onAddSearchSpace: () => void;
	className?: string;
}

export interface SidebarHeaderProps {
	searchSpace: SearchSpace | null;
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
	onViewAllSharedChats?: () => void;
	onViewAllPrivateChats?: () => void;
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
	onManageMembers?: () => void;
	onSwitchSearchSpace?: () => void;
	onToggleTheme?: () => void;
	onLogout?: () => void;
	theme?: string;
}

export interface SidebarProps {
	searchSpace: SearchSpace | null;
	searchSpaceId?: string;
	navItems: NavItem[];
	chats: ChatItem[];
	sharedChats?: ChatItem[];
	activeChatId?: number | null;
	onNewChat: () => void;
	onChatSelect: (chat: ChatItem) => void;
	onChatDelete?: (chat: ChatItem) => void;
	onViewAllSharedChats?: () => void;
	onViewAllPrivateChats?: () => void;
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
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onAddSearchSpace: () => void;
	sidebarProps: Omit<SidebarProps, "className">;
	children: React.ReactNode;
	className?: string;
}
