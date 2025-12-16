"use client";

import {
	ChevronRight,
	ExternalLink,
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
import { useCallback, useState } from "react";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
}

export function NavNotes({ notes, onAddNote, defaultOpen = true }: NavNotesProps) {
	const t = useTranslations("sidebar");
	const { isMobile } = useSidebar();
	const router = useRouter();
	const [isDeleting, setIsDeleting] = useState<number | null>(null);
	const [isOpen, setIsOpen] = useState(defaultOpen);

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
						size="sm"
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
		<SidebarGroup className="group-data-[collapsible=icon]:hidden">
			<Collapsible open={isOpen} onOpenChange={setIsOpen}>
				<div className="flex items-center justify-between group/header">
					<CollapsibleTrigger asChild>
						<SidebarGroupLabel className="cursor-pointer rounded-md px-2 py-1.5 -mx-2 transition-colors flex items-center gap-1.5">
							<ChevronRight
								className={`h-3.5 w-3.5 text-muted-foreground transition-all duration-200 shrink-0 hover:text-sidebar-foreground ${
									isOpen ? "rotate-90" : ""
								}`}
							/>
							<span className="text-xs font-medium text-sidebar-foreground/70">
								{t("notes") || "Notes"}
							</span>
						</SidebarGroupLabel>
					</CollapsibleTrigger>
					{onAddNote && (
						<button
							type="button"
							onClick={(e) => {
								e.stopPropagation();
								onAddNote();
							}}
							className="opacity-0 group-hover/header:opacity-100 transition-opacity p-1 hover:bg-sidebar-accent rounded-md -mr-2 shrink-0"
							aria-label="Add note"
						>
							<Plus className="h-3.5 w-3.5 text-muted-foreground" />
						</button>
					)}
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
											size="sm"
										>
											<Plus className="h-4 w-4" />
											<span>{t("create_new_note") || "Create a new note"}</span>
										</SidebarMenuButton>
									) : (
										<SidebarMenuButton disabled className="text-muted-foreground text-xs" size="sm">
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
		</SidebarGroup>
	);
}

