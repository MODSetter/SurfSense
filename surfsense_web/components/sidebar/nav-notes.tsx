"use client";

import {
	ChevronRight,
	ExternalLink,
	Eye,
	FileText,
	type LucideIcon,
	MoreHorizontal,
	Plus,
	RefreshCw,
	Share,
	Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState, useRef } from "react";
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
	SidebarMenuAction,
	SidebarMenuButton,
	SidebarMenuItem,
	useSidebar,
} from "@/components/ui/sidebar";
import { AllNotesSidebar } from "./all-notes-sidebar";

// Map of icon names to their components
const actionIconMap: Record<string, LucideIcon> = {
	ExternalLink,
	FileText,
	Share,
	Trash2,
	MoreHorizontal,
	RefreshCw,
};

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
}

export function NavNotes({ notes, onAddNote, defaultOpen = true, searchSpaceId }: NavNotesProps) {
	const t = useTranslations("sidebar");
	const { isMobile } = useSidebar();
	const router = useRouter();
	const [isDeleting, setIsDeleting] = useState<number | null>(null);
	const [isOpen, setIsOpen] = useState(defaultOpen);
	const [isAllNotesSidebarOpen, setIsAllNotesSidebarOpen] = useState(false);
	const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

	// Handle note deletion with loading state
	const handleDeleteNote = useCallback(async (noteId: number, deleteAction: () => void) => {
		setIsDeleting(noteId);
		try {
			await deleteAction();
		} finally {
			setIsDeleting(null);
		}
	}, []);

	// Enhanced note item component
	const NoteItemComponent = useCallback(
		({ note }: { note: NoteItem }) => {
			const isDeletingNote = isDeleting === note.id;

			return (
				<SidebarMenuItem key={note.id ? `note-${note.id}` : `note-${note.name}`}>
					<SidebarMenuButton
						onClick={() => router.push(note.url)}
						disabled={isDeletingNote}
						className={`group/item relative ${isDeletingNote ? "opacity-50" : ""}`}
					>
						<note.icon className="h-4 w-4 shrink-0" />
						<span className={`truncate ${isDeletingNote ? "opacity-50" : ""}`}>{note.name}</span>
					</SidebarMenuButton>

					{note.actions && note.actions.length > 0 && (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<SidebarMenuAction
									showOnHover
									className="opacity-0 group-hover/item:opacity-100 transition-opacity"
								>
									<MoreHorizontal className="h-4 w-4" />
									<span className="sr-only">More</span>
								</SidebarMenuAction>
							</DropdownMenuTrigger>
							<DropdownMenuContent
								className="w-48"
								side={isMobile ? "bottom" : "right"}
								align={isMobile ? "end" : "start"}
							>
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
											className={isDeleteAction ? "text-destructive" : ""}
										>
											<ActionIcon className="mr-2 h-4 w-4" />
											<span>{isDeletingNote && isDeleteAction ? "Deleting..." : action.name}</span>
										</DropdownMenuItem>
									);
								})}
							</DropdownMenuContent>
						</DropdownMenu>
					)}
				</SidebarMenuItem>
			);
		},
		[isDeleting, router, isMobile, handleDeleteNote]
	);

	return (
		<SidebarGroup className="group-data-[collapsible=icon]:hidden relative">
			<Collapsible open={isOpen} onOpenChange={setIsOpen}>
				<div className="flex items-center group/header relative">
					<CollapsibleTrigger asChild>
						<SidebarGroupLabel className="cursor-pointer rounded-md px-2 py-1.5 -mx-2 transition-colors flex items-center gap-1.5">
							<ChevronRight
								className={`h-3.5 w-3.5 text-muted-foreground transition-all duration-200 shrink-0 hover:text-sidebar-foreground ${
									isOpen ? "rotate-90" : ""
								}`}
							/>
							<span>{t("notes") || "Notes"}</span>
						</SidebarGroupLabel>
					</CollapsibleTrigger>
					<div className="absolute top-1.5 right-1 flex items-center gap-0.5 opacity-0 group-hover/header:opacity-100 transition-opacity">
						{searchSpaceId && notes.length > 0 && (
							<button
								type="button"
								onMouseEnter={(e) => {
									e.stopPropagation();
									// Clear any pending close timeout
									if (hoverTimeoutRef.current) {
										clearTimeout(hoverTimeoutRef.current);
										hoverTimeoutRef.current = null;
									}
									setIsAllNotesSidebarOpen(true);
								}}
								onMouseLeave={(e) => {
									e.stopPropagation();
									// Add a small delay before closing to allow moving to the sidebar
									hoverTimeoutRef.current = setTimeout(() => {
										setIsAllNotesSidebarOpen(false);
									}, 200);
								}}
								aria-label="View all notes"
								className="text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex aspect-square w-5 items-center justify-center rounded-md p-0 outline-hidden transition-transform focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0 after:absolute after:-inset-2 md:after:hidden relative"
							>
								<Eye className="h-4 w-4" />
							</button>
						)}
						{onAddNote && (
							<button
								type="button"
								onClick={(e) => {
									e.stopPropagation();
									onAddNote();
								}}
								aria-label="Add note"
								className="text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex aspect-square w-5 items-center justify-center rounded-md p-0 outline-hidden transition-transform focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0 after:absolute after:-inset-2 md:after:hidden relative"
							>
								<Plus className="h-4 w-4" />
							</button>
						)}
					</div>
				</div>
				<CollapsibleContent>
					<SidebarGroupContent>
						<SidebarMenu>
							{/* Note Items */}
							{notes.length > 0 ? (
								notes.map((note) => <NoteItemComponent key={note.id || note.name} note={note} />)
							) : (
								/* Empty state with create button */
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
			{searchSpaceId && (
				<AllNotesSidebar
					open={isAllNotesSidebarOpen}
					onOpenChange={setIsAllNotesSidebarOpen}
					searchSpaceId={searchSpaceId}
					onAddNote={onAddNote}
					hoverTimeoutRef={hoverTimeoutRef}
				/>
			)}
		</SidebarGroup>
	);
}
