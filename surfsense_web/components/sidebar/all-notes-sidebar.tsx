"use client";

import { FileText, type LucideIcon, MoreHorizontal, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { notesApiService } from "@/lib/apis/notes-api.service";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarMenu,
	SidebarMenuAction,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// Map of icon names to their components
const actionIconMap: Record<string, LucideIcon> = {
	FileText,
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

interface AllNotesSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
	onAddNote?: () => void;
	hoverTimeoutRef?: React.MutableRefObject<NodeJS.Timeout | null>;
}

export function AllNotesSidebar({
	open,
	onOpenChange,
	searchSpaceId,
	onAddNote,
	hoverTimeoutRef,
}: AllNotesSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const [isDeleting, setIsDeleting] = useState<number | null>(null);
	const sidebarRef = useRef<HTMLElement>(null);
	const [sidebarLeft, setSidebarLeft] = useState(0); // Position from left edge of viewport

	// Calculate the sidebar's right edge position
	useEffect(() => {
		if (typeof window === "undefined") return;

		const updatePosition = () => {
			// Find the actual sidebar element (the fixed positioned one)
			const sidebarElement = document.querySelector(
				'[data-slot="sidebar"][data-sidebar="sidebar"]'
			) as HTMLElement;

			if (sidebarElement) {
				const rect = sidebarElement.getBoundingClientRect();
				// Set the left position to be the right edge of the sidebar
				setSidebarLeft(rect.right);
			} else {
				// Fallback: try to find any sidebar element
				const fallbackSidebar = document.querySelector('[data-slot="sidebar"]') as HTMLElement;
				if (fallbackSidebar) {
					const rect = fallbackSidebar.getBoundingClientRect();
					setSidebarLeft(rect.right);
				} else {
					// Final fallback: use CSS variable
					const sidebarWidth = getComputedStyle(document.documentElement)
						.getPropertyValue("--sidebar-width")
						.trim();
					if (sidebarWidth) {
						const remValue = parseFloat(sidebarWidth);
						setSidebarLeft(remValue * 16); // Convert rem to px
					} else {
						setSidebarLeft(256); // Default 16rem
					}
				}
			}
		};

		updatePosition();
		// Update on window resize and scroll
		window.addEventListener("resize", updatePosition);
		window.addEventListener("scroll", updatePosition, true);

		// Use MutationObserver to watch for sidebar state changes
		const observer = new MutationObserver(updatePosition);
		const sidebarWrapper = document.querySelector('[data-slot="sidebar-wrapper"]');
		if (sidebarWrapper) {
			observer.observe(sidebarWrapper, {
				attributes: true,
				attributeFilter: ["data-state", "class"],
				childList: true,
				subtree: true,
			});
		}

		// Also observe the sidebar element directly if it exists
		const sidebarElement = document.querySelector('[data-slot="sidebar"]');
		if (sidebarElement) {
			observer.observe(sidebarElement, {
				attributes: true,
				attributeFilter: ["data-state", "class"],
				childList: false,
				subtree: false,
			});
		}

		return () => {
			window.removeEventListener("resize", updatePosition);
			window.removeEventListener("scroll", updatePosition, true);
			observer.disconnect();
		};
	}, []);

	// Handle Escape key to close sidebar
	useEffect(() => {
		if (!open) return;

		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				onOpenChange(false);
			}
		};

		window.addEventListener("keydown", handleEscape);
		return () => window.removeEventListener("keydown", handleEscape);
	}, [open, onOpenChange]);

	// Fetch all notes
	const {
		data: notesData,
		error: notesError,
		isLoading: isLoadingNotes,
		refetch: refetchNotes,
	} = useQuery({
		queryKey: ["all-notes", searchSpaceId],
		queryFn: () =>
			notesApiService.getNotes({
				search_space_id: Number(searchSpaceId),
				page_size: 1000, // Get all notes
			}),
		enabled: !!searchSpaceId && open, // Only fetch when sidebar is open
	});

	// Handle note deletion with loading state
	const handleDeleteNote = useCallback(
		async (noteId: number, deleteAction: () => void) => {
			setIsDeleting(noteId);
			try {
				await deleteAction();
				refetchNotes();
			} finally {
				setIsDeleting(null);
			}
		},
		[refetchNotes]
	);

	// Transform notes to the format expected by the component
	const allNotes = useMemo(() => {
		return notesData?.items
			? notesData.items.map((note) => ({
					name: note.title,
					url: `/dashboard/${note.search_space_id}/editor/${note.id}`,
					icon: FileText as LucideIcon,
					id: note.id,
					search_space_id: note.search_space_id,
					actions: [
						{
							name: "Delete",
							icon: "Trash2",
							onClick: async () => {
								try {
									await notesApiService.deleteNote({
										search_space_id: note.search_space_id,
										note_id: note.id,
									});
								} catch (error) {
									console.error("Error deleting note:", error);
								}
							},
						},
					],
				}))
			: [];
	}, [notesData]);

	// Enhanced note item component
	const NoteItemComponent = useCallback(
		({ note }: { note: NoteItem }) => {
			const isDeletingNote = isDeleting === note.id;

			return (
				<SidebarMenuItem key={note.id ? `note-${note.id}` : `note-${note.name}`}>
					<SidebarMenuButton
						onClick={() => {
							router.push(note.url);
							onOpenChange(false); // Close sidebar when navigating
						}}
						disabled={isDeletingNote}
						className={cn("group/item relative", isDeletingNote && "opacity-50")}
					>
						<note.icon className="h-4 w-4 shrink-0" />
						<span className={cn("truncate", isDeletingNote && "opacity-50")}>{note.name}</span>
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
							<DropdownMenuContent className="w-48" side="left" align="start">
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
		[isDeleting, router, onOpenChange, handleDeleteNote]
	);

	const sidebarContent = (
		<section
			ref={sidebarRef}
			aria-label="All notes sidebar"
			className={cn(
				"fixed top-0 bottom-0 z-[100] w-80 bg-sidebar text-sidebar-foreground shadow-xl",
				"transition-all duration-300 ease-out",
				!open && "pointer-events-none"
			)}
			style={{
				// Position it to slide from the right edge of the main sidebar
				left: `${sidebarLeft}px`,
				transform: open ? `scaleX(1)` : `scaleX(0)`,
				transformOrigin: "left",
				opacity: open ? 1 : 0,
			}}
			onMouseEnter={() => {
				// Clear any pending close timeout when hovering over sidebar
				if (hoverTimeoutRef?.current) {
					clearTimeout(hoverTimeoutRef.current);
					hoverTimeoutRef.current = null;
				}
			}}
			onMouseLeave={() => {
				// Close sidebar when mouse leaves
				if (hoverTimeoutRef) {
					hoverTimeoutRef.current = setTimeout(() => {
						onOpenChange(false);
					}, 200);
				} else {
					onOpenChange(false);
				}
			}}
		>
			<div className="flex h-full flex-col">
				{/* Header */}
				<div className="flex h-16 shrink-0 items-center justify-between px-4 border-b border-sidebar">
					<h2 className="text-sm font-semibold">{t("all_notes") || "All Notes"}</h2>
				</div>

				{/* Content */}
				<ScrollArea className="flex-1">
					<div className="p-2">
						<SidebarGroup>
							<SidebarGroupContent>
								{isLoadingNotes ? (
									<SidebarMenuItem>
										<SidebarMenuButton disabled>
											<span className="text-xs text-muted-foreground">
												{t("loading") || "Loading..."}
											</span>
										</SidebarMenuButton>
									</SidebarMenuItem>
								) : notesError ? (
									<SidebarMenuItem>
										<SidebarMenuButton disabled>
											<span className="text-xs text-destructive">
												{t("error_loading_notes") || "Error loading notes"}
											</span>
										</SidebarMenuButton>
									</SidebarMenuItem>
								) : allNotes.length > 0 ? (
									<SidebarMenu className="list-none">
										{allNotes.map((note) => (
											<NoteItemComponent key={note.id || note.name} note={note} />
										))}
									</SidebarMenu>
								) : (
									<SidebarMenuItem className="list-none">
										{onAddNote ? (
											<SidebarMenuButton
												onClick={() => {
													onAddNote();
													onOpenChange(false);
												}}
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
							</SidebarGroupContent>
						</SidebarGroup>
					</div>
				</ScrollArea>

				{/* Footer with Add Note button */}
				{onAddNote && (
					<div className="p-2">
						<Button
							onClick={() => {
								onAddNote();
								onOpenChange(false);
							}}
							className="w-full"
							size="sm"
						>
							<Plus className="mr-2 h-4 w-4" />
							{t("create_new_note") || "Create a new note"}
						</Button>
					</div>
				)}
			</div>
		</section>
	);

	// Render sidebar via portal to avoid stacking context issues
	if (typeof window === "undefined") {
		return null;
	}

	return createPortal(sidebarContent, document.body);
}
