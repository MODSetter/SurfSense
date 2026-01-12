"use client";

import { FileText, FolderOpen, MessageSquare, PenSquare, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type {
	ChatItem,
	NavItem,
	NoteItem,
	PageUsage,
	SearchSpace,
	User,
} from "../../types/layout.types";
import { ChatListItem } from "./ChatListItem";
import { NavSection } from "./NavSection";
import { NoteListItem } from "./NoteListItem";
import { PageUsageDisplay } from "./PageUsageDisplay";
import { SidebarCollapseButton } from "./SidebarCollapseButton";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarSection } from "./SidebarSection";
import { SidebarUserProfile } from "./SidebarUserProfile";

interface SidebarProps {
	searchSpace: SearchSpace | null;
	isCollapsed?: boolean;
	onToggleCollapse?: () => void;
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
	onUserSettings?: () => void;
	onLogout?: () => void;
	pageUsage?: PageUsage;
	className?: string;
}

export function Sidebar({
	searchSpace,
	isCollapsed = false,
	onToggleCollapse,
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
	onUserSettings,
	onLogout,
	pageUsage,
	className,
}: SidebarProps) {
	const t = useTranslations("sidebar");

	return (
		<div
			className={cn(
				"flex h-full flex-col bg-sidebar text-sidebar-foreground transition-all duration-200 overflow-hidden",
				isCollapsed ? "w-[60px]" : "w-[240px]",
				className
			)}
		>
			{/* Header - search space name or collapse button when collapsed */}
			{isCollapsed ? (
				<div className="flex h-14 shrink-0 items-center justify-center border-b">
					<SidebarCollapseButton
						isCollapsed={isCollapsed}
						onToggle={onToggleCollapse ?? (() => {})}
					/>
				</div>
			) : (
				<div className="flex h-14 shrink-0 items-center justify-between px-1 border-b">
					<SidebarHeader
						searchSpace={searchSpace}
						isCollapsed={isCollapsed}
						onSettings={onSettings}
						onManageMembers={onManageMembers}
					/>
					<div className="">
						<SidebarCollapseButton
							isCollapsed={isCollapsed}
							onToggle={onToggleCollapse ?? (() => {})}
						/>
					</div>
				</div>
			)}

			{/* New chat button */}
			<div className="p-2">
				{isCollapsed ? (
					<Tooltip>
						<TooltipTrigger asChild>
							<Button variant="outline" size="icon" className="w-full h-10" onClick={onNewChat}>
								<PenSquare className="h-4 w-4" />
								<span className="sr-only">{t("new_chat")}</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="right">{t("new_chat")}</TooltipContent>
					</Tooltip>
				) : (
					<Button variant="outline" className="w-full justify-start gap-2" onClick={onNewChat}>
						<PenSquare className="h-4 w-4" />
						{t("new_chat")}
					</Button>
				)}
			</div>

			{/* Platform navigation */}
			{navItems.length > 0 && (
				<NavSection items={navItems} onItemClick={onNavItemClick} isCollapsed={isCollapsed} />
			)}

			{/* Scrollable content */}
			<ScrollArea className="flex-1">
				{isCollapsed ? (
					<div className="flex flex-col items-center gap-2 py-2 w-[60px]">
						{chats.length > 0 && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-10 w-10"
										onClick={() => onToggleCollapse?.()}
									>
										<MessageSquare className="h-4 w-4" />
										<span className="sr-only">{t("recent_chats")}</span>
									</Button>
								</TooltipTrigger>
								<TooltipContent side="right">
									{t("recent_chats")} ({chats.length})
								</TooltipContent>
							</Tooltip>
						)}
						{notes.length > 0 && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-10 w-10"
										onClick={() => onToggleCollapse?.()}
									>
										<FileText className="h-4 w-4" />
										<span className="sr-only">{t("notes")}</span>
									</Button>
								</TooltipTrigger>
								<TooltipContent side="right">
									{t("notes")} ({notes.length})
								</TooltipContent>
							</Tooltip>
						)}
					</div>
				) : (
					<div className="flex flex-col gap-1 py-2 w-[240px]">
						<SidebarSection
							title={t("recent_chats")}
							defaultOpen={true}
							action={
								onViewAllChats && chats.length > 0 ? (
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-5 w-5"
												onClick={onViewAllChats}
											>
												<FolderOpen className="h-3.5 w-3.5" />
											</Button>
										</TooltipTrigger>
										<TooltipContent side="top">{t("view_all_chats")}</TooltipContent>
									</Tooltip>
								) : undefined
							}
						>
							{chats.length > 0 ? (
								<div className="flex flex-col gap-0.5">
									{chats.map((chat) => (
										<ChatListItem
											key={chat.id}
											name={chat.name}
											isActive={chat.id === activeChatId}
											onClick={() => onChatSelect(chat)}
											onDelete={() => onChatDelete?.(chat)}
										/>
									))}
								</div>
							) : (
								<p className="px-2 py-1 text-xs text-muted-foreground">{t("no_recent_chats")}</p>
							)}
						</SidebarSection>

						<SidebarSection
							title={t("notes")}
							defaultOpen={true}
							action={
								onViewAllNotes && notes.length > 0 ? (
									<Tooltip>
										<TooltipTrigger asChild>
											<Button
												variant="ghost"
												size="icon"
												className="h-5 w-5"
												onClick={onViewAllNotes}
											>
												<FolderOpen className="h-3.5 w-3.5" />
											</Button>
										</TooltipTrigger>
										<TooltipContent side="top">{t("view_all_notes")}</TooltipContent>
									</Tooltip>
								) : undefined
							}
							persistentAction={
								onAddNote && notes.length > 0 ? (
									<Tooltip>
										<TooltipTrigger asChild>
											<Button variant="ghost" size="icon" className="h-5 w-5" onClick={onAddNote}>
												<Plus className="h-3.5 w-3.5" />
											</Button>
										</TooltipTrigger>
										<TooltipContent side="top">{t("add_note")}</TooltipContent>
									</Tooltip>
								) : undefined
							}
						>
							{notes.length > 0 ? (
								<div className="flex flex-col gap-0.5">
									{notes.map((note) => (
										<NoteListItem
											key={note.id}
											name={note.name}
											isActive={note.id === activeNoteId}
											isReindexing={note.isReindexing}
											onClick={() => onNoteSelect(note)}
											onDelete={() => onNoteDelete?.(note)}
										/>
									))}
								</div>
							) : onAddNote ? (
								<button
									type="button"
									onClick={onAddNote}
									className="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
								>
									<Plus className="h-3.5 w-3.5" />
									{t("create_new_note")}
								</button>
							) : (
								<p className="px-2 py-1 text-xs text-muted-foreground">{t("no_notes")}</p>
							)}
						</SidebarSection>
					</div>
				)}
			</ScrollArea>

			{/* Footer */}
			<div className="mt-auto">
				{pageUsage && !isCollapsed && (
					<PageUsageDisplay pagesUsed={pageUsage.pagesUsed} pagesLimit={pageUsage.pagesLimit} />
				)}

				<SidebarUserProfile
					user={user}
					onUserSettings={onUserSettings}
					onLogout={onLogout}
					isCollapsed={isCollapsed}
				/>
			</div>
		</div>
	);
}
