"use client";

import { Menu, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import type { ChatItem, NavItem, PageUsage, SearchSpace, User } from "../../types/layout.types";
import { SearchSpaceAvatar } from "../icon-rail/SearchSpaceAvatar";
import { Sidebar } from "./Sidebar";

interface MobileSidebarProps {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
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
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
}

export function MobileSidebarTrigger({ onClick }: { onClick: () => void }) {
	return (
		<Button variant="ghost" size="icon" className="md:hidden h-8 w-8" onClick={onClick}>
			<Menu className="h-5 w-5" />
			<span className="sr-only">Open menu</span>
		</Button>
	);
}

export function MobileSidebar({
	isOpen,
	onOpenChange,
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
	theme,
	setTheme,
}: MobileSidebarProps) {
	const handleSearchSpaceSelect = (id: number) => {
		onSearchSpaceSelect(id);
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
			<SheetContent side="left" className="w-[300px] p-0 flex flex-col">
				<SheetTitle className="sr-only">Navigation</SheetTitle>

				{/* Horizontal Search Spaces Rail */}
				<div className="shrink-0 border-b bg-muted/40 px-2 py-2 overflow-hidden">
					<div className="flex items-center gap-2 px-1 py-1 overflow-x-auto scrollbar-thin scrollbar-thumb-muted-foreground/20">
						{searchSpaces.map((space) => (
							<div key={space.id} className="shrink-0">
								<SearchSpaceAvatar
									name={space.name}
									isActive={space.id === activeSearchSpaceId}
									isShared={space.memberCount > 1}
									isOwner={space.isOwner}
									onClick={() => handleSearchSpaceSelect(space.id)}
									onDelete={onSearchSpaceDelete ? () => onSearchSpaceDelete(space) : undefined}
									onSettings={
										onSearchSpaceSettings ? () => onSearchSpaceSettings(space) : undefined
									}
									size="md"
								/>
							</div>
						))}
						<Button
							variant="ghost"
							size="icon"
							onClick={onAddSearchSpace}
							className="h-10 w-10 shrink-0 rounded-lg border-2 border-dashed border-muted-foreground/30 hover:border-muted-foreground/50"
						>
							<Plus className="h-5 w-5 text-muted-foreground" />
							<span className="sr-only">Add search space</span>
						</Button>
					</div>
				</div>

				{/* Sidebar Content */}
				<div className="flex-1 overflow-hidden">
					<Sidebar
						searchSpace={searchSpace}
						isCollapsed={false}
						navItems={navItems}
						onNavItemClick={handleNavItemClick}
						chats={chats}
						sharedChats={sharedChats}
						activeChatId={activeChatId}
						onNewChat={() => {
							onNewChat();
							onOpenChange(false);
						}}
						onChatSelect={handleChatSelect}
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
						className="w-full border-none"
					/>
				</div>
			</SheetContent>
		</Sheet>
	);
}
