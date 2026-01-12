"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import type {
	ChatItem,
	NavItem,
	NoteItem,
	PageUsage,
	User,
	SearchSpace,
} from "../../types/layout.types";
import { IconRail } from "../icon-rail";
import { Sidebar } from "./Sidebar";

interface MobileSidebarProps {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onAddSearchSpace: () => void;
	searchSpace: SearchSpace | null;
	navItems: NavItem[];
	onNavItemClick?: (item: NavItem) => void;
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
	onSettings?: () => void;
	onManageMembers?: () => void;
	onSeeAllSearchSpaces?: () => void;
	onUserSettings?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
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
	onAddSearchSpace,
	searchSpace,
	navItems,
	onNavItemClick,
	chats,
	activeChatId,
	onNewChat,
	onChatSelect,
	onChatDelete,
	onViewAllChats,
	notes,
	activeNoteId,
	onNoteSelect,
	onNoteDelete,
	onAddNote,
	onViewAllNotes,
	user,
	onSettings,
	onManageMembers,
	onSeeAllSearchSpaces,
	onUserSettings,
	onLogout,
	pageUsage,
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

	const handleNoteSelect = (note: NoteItem) => {
		onNoteSelect(note);
		onOpenChange(false);
	};

	return (
		<Sheet open={isOpen} onOpenChange={onOpenChange}>
			<SheetContent side="left" className="w-[320px] p-0 flex">
				<SheetTitle className="sr-only">Navigation</SheetTitle>

				<div className="shrink-0 border-r bg-muted/40">
					<ScrollArea className="h-full">
						<IconRail
							searchSpaces={searchSpaces}
							activeSearchSpaceId={activeSearchSpaceId}
							onSearchSpaceSelect={handleSearchSpaceSelect}
							onAddSearchSpace={onAddSearchSpace}
						/>
					</ScrollArea>
				</div>

				<div className="flex-1 overflow-hidden">
					<Sidebar
						searchSpace={searchSpace}
						isCollapsed={false}
						navItems={navItems}
						onNavItemClick={handleNavItemClick}
						chats={chats}
						activeChatId={activeChatId}
						onNewChat={() => {
							onNewChat();
							onOpenChange(false);
						}}
						onChatSelect={handleChatSelect}
						onChatDelete={onChatDelete}
						onViewAllChats={onViewAllChats}
						notes={notes}
						activeNoteId={activeNoteId}
						onNoteSelect={handleNoteSelect}
						onNoteDelete={onNoteDelete}
						onAddNote={onAddNote}
						onViewAllNotes={onViewAllNotes}
						user={user}
						onSettings={onSettings}
						onManageMembers={onManageMembers}
						onSeeAllSearchSpaces={onSeeAllSearchSpaces}
						onUserSettings={onUserSettings}
						onLogout={onLogout}
						pageUsage={pageUsage}
						className="w-full border-none"
					/>
				</div>
			</SheetContent>
		</Sheet>
	);
}
