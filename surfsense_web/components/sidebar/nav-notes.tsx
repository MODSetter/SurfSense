"use client";

import {
	ChevronRight,
	FileText,
	FolderOpen,
	Loader2,
	type LucideIcon,
	MoreHorizontal,
	Plus,
	Trash2,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLogsSummary } from "@/hooks/use-logs";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import { AllNotesSidebar } from "./all-notes-sidebar";

interface NoteAction {
	name: string;
	icon: string;
	onClick: () => void;
}

interface NoteItem {
	name: string;
	url: string;
	icon: LucideIcon;
	id?: number;
	search_space_id?: number;
	actions?: NoteAction[];
}

interface NavNotesProps {
	notes: NoteItem[];
	onAddNote?: () => void;
	defaultOpen?: boolean;
	searchSpaceId?: string;
	isSourcesExpanded?: boolean;
}

// Map of icon names to their components
const actionIconMap: Record<string, LucideIcon> = {
	FileText,
	Trash2,
	MoreHorizontal,
};

export function NavNotes({
	notes,
	onAddNote,
	defaultOpen = true,
	searchSpaceId,
	isSourcesExpanded = false,
}: NavNotesProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const pathname = usePathname();
	const isMobile = useIsMobile();
	const [isDeleting, setIsDeleting] = useState<number | null>(null);
	const [isOpen, setIsOpen] = useState(defaultOpen);
	const [isAllNotesSidebarOpen, setIsAllNotesSidebarOpen] = useState(false);

	// Poll for active reindexing tasks to show inline loading indicators
	const { summary } = useLogsSummary(
		searchSpaceId ? Number(searchSpaceId) : 0,
		24,
		{ refetchInterval: 2000 }
	);

	// Create a Set of document IDs that are currently being reindexed
	const reindexingDocumentIds = useMemo(() => {
		if (!summary?.active_tasks) return new Set<number>();
		return new Set(
			summary.active_tasks
				.filter((task) => task.document_id != null)
				.map((task) => task.document_id as number)
		);
	}, [summary?.active_tasks]);

	// Auto-collapse on smaller screens when Sources is expanded
	useEffect(() => {
		if (isSourcesExpanded && isMobile) {
			setIsOpen(false);
		}
	}, [isSourcesExpanded, isMobile]);

	// Handle note deletion with loading state
	const handleDeleteNote = useCallback(async (noteId: number, deleteAction: () => void) => {
		setIsDeleting(noteId);
		try {
			await deleteAction();
		} finally {
			setIsDeleting(null);
		}
	}, []);

	// Handle note navigation
	const handleNoteClick = useCallback(
		(url: string) => {
			router.push(url);
		},
		[router]
	);

	return (
		<SidebarGroup className="group-data-[collapsible=icon]:hidden">
			<Collapsible open={isOpen} onOpenChange={setIsOpen}>
				<div className="flex items-center group/header">
					<CollapsibleTrigger asChild>
						<SidebarGroupLabel className="cursor-pointer rounded-md px-2 py-1.5 -mx-2 transition-colors flex items-center gap-1.5 flex-1">
							<ChevronRight
								className={cn(
									"h-3.5 w-3.5 text-muted-foreground transition-all duration-200 shrink-0",
									isOpen && "rotate-90"
								)}
							/>
							<span>{t("notes") || "Notes"}</span>
						</SidebarGroupLabel>
					</CollapsibleTrigger>

					{/* Action buttons - always visible on hover */}
					<div className="flex items-center gap-0.5 opacity-0 group-hover/header:opacity-100 transition-opacity pr-1">
						{searchSpaceId && notes.length > 0 && (
							<Button
								variant="ghost"
								size="icon"
								className="h-5 w-5"
								onClick={(e) => {
									e.stopPropagation();
									setIsAllNotesSidebarOpen(true);
								}}
								aria-label={t("view_all_notes") || "View all notes"}
							>
								<FolderOpen className="h-3.5 w-3.5" />
							</Button>
						)}
						{onAddNote && (
							<Button
								variant="ghost"
								size="icon"
								className="h-5 w-5"
								onClick={(e) => {
									e.stopPropagation();
									onAddNote();
								}}
								aria-label={t("add_note") || "Add note"}
							>
								<Plus className="h-3.5 w-3.5" />
							</Button>
						)}
					</div>
				</div>

				<CollapsibleContent>
					<SidebarGroupContent>
						<SidebarMenu>
							{notes.length > 0 ? (
								notes.map((note) => {
									const isDeletingNote = isDeleting === note.id;
									const isActive = pathname === note.url;
									const isReindexing = note.id ? reindexingDocumentIds.has(note.id) : false;

									return (
										<SidebarMenuItem key={note.id || note.name} className="group/note">
											{/* Main navigation button */}
											<SidebarMenuButton
												onClick={() => handleNoteClick(note.url)}
												disabled={isDeletingNote}
												className={cn(
													"pr-8", // Make room for the action button
													isActive && "bg-sidebar-accent text-sidebar-accent-foreground font-medium",
													isDeletingNote && "opacity-50"
												)}
											>
												{isReindexing ? (
													<Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
												) : (
													<note.icon className="h-4 w-4 shrink-0" />
												)}
												<span className="truncate">{note.name}</span>
											</SidebarMenuButton>

											{/* Actions dropdown - positioned absolutely */}
											{note.actions && note.actions.length > 0 && (
												<div className="absolute right-1 top-1/2 -translate-y-1/2">
													<DropdownMenu>
														<DropdownMenuTrigger asChild>
															<Button
																variant="ghost"
																size="icon"
																className={cn(
																	"h-6 w-6",
																	"opacity-0 group-hover/note:opacity-100 focus:opacity-100",
																	"data-[state=open]:opacity-100",
																	"transition-opacity"
																)}
																disabled={isDeletingNote}
															>
																{isDeletingNote ? (
																	<Loader2 className="h-3.5 w-3.5 animate-spin" />
																) : (
																	<MoreHorizontal className="h-3.5 w-3.5" />
																)}
																<span className="sr-only">
																	{t("more_options") || "More options"}
																</span>
															</Button>
														</DropdownMenuTrigger>
														<DropdownMenuContent align="end" side="right" className="w-40">
															{note.actions.map((action, actionIndex) => {
																const ActionIcon = actionIconMap[action.icon] || FileText;
																const isDeleteAction = action.name.toLowerCase().includes("delete");

																return (
																	<DropdownMenuItem
																		key={`${action.name}-${actionIndex}`}
																		onClick={() => {
																			if (isDeleteAction) {
																				handleDeleteNote(note.id || 0, action.onClick);
																			} else {
																				action.onClick();
																			}
																		}}
																		disabled={isDeletingNote}
																		className={
																			isDeleteAction
																				? "text-destructive focus:text-destructive"
																				: ""
																		}
																	>
																		<ActionIcon className="mr-2 h-4 w-4" />
																		<span>
																			{isDeletingNote && isDeleteAction
																				? t("deleting") || "Deleting..."
																				: action.name}
																		</span>
																	</DropdownMenuItem>
																);
															})}
														</DropdownMenuContent>
													</DropdownMenu>
												</div>
											)}
										</SidebarMenuItem>
									);
								})
							) : (
								<SidebarMenuItem>
									{onAddNote ? (
										<SidebarMenuButton
											onClick={onAddNote}
											className="text-muted-foreground hover:text-sidebar-foreground text-xs"
										>
											<Plus className="h-4 w-4" />
											<span>{t("create_new_note") || "Create a new note"}</span>
										</SidebarMenuButton>
									) : (
										<SidebarMenuButton disabled className="text-muted-foreground text-xs">
											<FileText className="h-4 w-4" />
											<span>{t("no_notes") || "No notes yet"}</span>
										</SidebarMenuButton>
									)}
								</SidebarMenuItem>
							)}
						</SidebarMenu>
					</SidebarGroupContent>
				</CollapsibleContent>
			</Collapsible>

			{/* All Notes Sheet */}
			{searchSpaceId && (
				<AllNotesSidebar
					open={isAllNotesSidebarOpen}
					onOpenChange={setIsAllNotesSidebarOpen}
					searchSpaceId={searchSpaceId}
					onAddNote={onAddNote}
				/>
			)}
		</SidebarGroup>
	);
}
