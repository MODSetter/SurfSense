"use client";

import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { useSidebarState } from "../../hooks";
import type {
	ChatItem,
	NavItem,
	NoteItem,
	PageUsage,
	User,
	Workspace,
} from "../../types/layout.types";
import { Header } from "../header";
import { IconRail } from "../icon-rail";
import { MobileSidebar, MobileSidebarTrigger, Sidebar } from "../sidebar";

interface LayoutShellProps {
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
	onInviteMembers?: () => void;
	onSeeAllWorkspaces?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	breadcrumb?: React.ReactNode;
	languageSwitcher?: React.ReactNode;
	theme?: string;
	onToggleTheme?: () => void;
	defaultCollapsed?: boolean;
	isChatPage?: boolean;
	children: React.ReactNode;
	className?: string;
}

export function LayoutShell({
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
	onInviteMembers,
	onSeeAllWorkspaces,
	onLogout,
	pageUsage,
	breadcrumb,
	languageSwitcher,
	theme,
	onToggleTheme,
	defaultCollapsed = false,
	isChatPage = false,
	children,
	className,
}: LayoutShellProps) {
	const isMobile = useIsMobile();
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
	const { isCollapsed, toggleCollapsed } = useSidebarState(defaultCollapsed);

	// Mobile layout
	if (isMobile) {
		return (
			<TooltipProvider delayDuration={0}>
				<div className={cn("flex h-screen w-full flex-col bg-background", className)}>
					<Header
						breadcrumb={breadcrumb}
						languageSwitcher={languageSwitcher}
						theme={theme}
						onToggleTheme={onToggleTheme}
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
						onChatDelete={onChatDelete}
						onViewAllChats={onViewAllChats}
						notes={notes}
						activeNoteId={activeNoteId}
						onNoteSelect={onNoteSelect}
						onNoteDelete={onNoteDelete}
						onAddNote={onAddNote}
						onViewAllNotes={onViewAllNotes}
						user={user}
						onSettings={onSettings}
						onInviteMembers={onInviteMembers}
						onSeeAllWorkspaces={onSeeAllWorkspaces}
						onLogout={onLogout}
						pageUsage={pageUsage}
					/>

					<main className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
						{children}
					</main>
				</div>
			</TooltipProvider>
		);
	}

	// Desktop layout
	return (
		<TooltipProvider delayDuration={0}>
			<div className={cn("flex h-screen w-full gap-2 p-2 overflow-hidden bg-muted/40", className)}>
				<div className="hidden md:flex overflow-hidden">
					<IconRail
						workspaces={workspaces}
						activeWorkspaceId={activeWorkspaceId}
						onWorkspaceSelect={onWorkspaceSelect}
						onAddWorkspace={onAddWorkspace}
					/>
				</div>

				<div className="flex flex-1 rounded-xl border bg-background overflow-hidden">
					<Sidebar
						workspace={workspace}
						isCollapsed={isCollapsed}
						onToggleCollapse={toggleCollapsed}
						navItems={navItems}
						onNavItemClick={onNavItemClick}
						chats={chats}
						activeChatId={activeChatId}
						onNewChat={onNewChat}
						onChatSelect={onChatSelect}
						onChatDelete={onChatDelete}
						onViewAllChats={onViewAllChats}
						notes={notes}
						activeNoteId={activeNoteId}
						onNoteSelect={onNoteSelect}
						onNoteDelete={onNoteDelete}
						onAddNote={onAddNote}
						onViewAllNotes={onViewAllNotes}
						user={user}
						onSettings={onSettings}
						onInviteMembers={onInviteMembers}
						onSeeAllWorkspaces={onSeeAllWorkspaces}
						onLogout={onLogout}
						pageUsage={pageUsage}
						className="hidden md:flex border-r shrink-0"
					/>

					<main className="flex-1 flex flex-col min-w-0">
						<Header
							breadcrumb={breadcrumb}
							languageSwitcher={languageSwitcher}
							theme={theme}
							onToggleTheme={onToggleTheme}
						/>

						<div className={cn("flex-1", isChatPage ? "overflow-hidden" : "overflow-auto")}>
							{children}
						</div>
					</main>
				</div>
			</div>
		</TooltipProvider>
	);
}
