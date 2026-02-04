"use client";

import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Document } from "./types";

// Only FILE and NOTE document types can be edited
const EDITABLE_DOCUMENT_TYPES = ["FILE", "NOTE"] as const;

// SURFSENSE_DOCS are system-managed and cannot be deleted
const NON_DELETABLE_DOCUMENT_TYPES = ["SURFSENSE_DOCS"] as const;

export function RowActions({
	document,
	deleteDocument,
	searchSpaceId,
}: {
	document: Document;
	deleteDocument: (id: number) => Promise<boolean>;
	searchSpaceId: string;
}) {
	const [isDeleteOpen, setIsDeleteOpen] = useState(false);
	const [isDeleting, setIsDeleting] = useState(false);
	const router = useRouter();

	const isEditable = EDITABLE_DOCUMENT_TYPES.includes(
		document.document_type as (typeof EDITABLE_DOCUMENT_TYPES)[number]
	);

	const isDeletable = !NON_DELETABLE_DOCUMENT_TYPES.includes(
		document.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
	);

	const handleDelete = async () => {
		setIsDeleting(true);
		try {
			const ok = await deleteDocument(document.id);
			if (!ok) toast.error("Failed to delete document");
			// Note: Success toast is handled by the mutation atom's onSuccess callback
			// Cache is updated optimistically by the mutation, no need to refresh
		} catch (error) {
			console.error("Error deleting document:", error);
			toast.error("Failed to delete document");
		} finally {
			setIsDeleting(false);
			setIsDeleteOpen(false);
		}
	};

	const handleEdit = () => {
		router.push(`/dashboard/${searchSpaceId}/editor/${document.id}`);
	};

	return (
		<>
			{/* Desktop Actions */}
			<div className="hidden md:inline-flex items-center justify-center">
				{isEditable ? (
					// Editable documents: show 3-dot dropdown with edit + delete
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/80">
								<MoreHorizontal className="h-4 w-4" />
								<span className="sr-only">Open menu</span>
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							<DropdownMenuItem onClick={handleEdit}>
								<Pencil className="mr-2 h-4 w-4" />
								<span>Edit</span>
							</DropdownMenuItem>
							{isDeletable && (
								<DropdownMenuItem
									onClick={() => setIsDeleteOpen(true)}
									className="text-destructive focus:text-destructive"
								>
									<Trash2 className="mr-2 h-4 w-4" />
									<span>Delete</span>
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					// Non-editable documents: show only delete button directly
					isDeletable && (
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
							onClick={() => setIsDeleteOpen(true)}
							disabled={isDeleting}
						>
							<Trash2 className="h-4 w-4" />
							<span className="sr-only">Delete</span>
						</Button>
					)
				)}
			</div>

			{/* Mobile Actions Dropdown */}
			<div className="inline-flex md:hidden items-center justify-center">
				{isEditable ? (
					// Editable documents: show 3-dot dropdown
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground">
								<MoreHorizontal className="h-4 w-4" />
								<span className="sr-only">Open menu</span>
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							<DropdownMenuItem onClick={handleEdit}>
								<Pencil className="mr-2 h-4 w-4" />
								<span>Edit</span>
							</DropdownMenuItem>
							{isDeletable && (
								<DropdownMenuItem
									onClick={() => setIsDeleteOpen(true)}
									className="text-destructive focus:text-destructive"
								>
									<Trash2 className="mr-2 h-4 w-4" />
									<span>Delete</span>
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					// Non-editable documents: show only delete button directly
					isDeletable && (
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
							onClick={() => setIsDeleteOpen(true)}
							disabled={isDeleting}
						>
							<Trash2 className="h-4 w-4" />
							<span className="sr-only">Delete</span>
						</Button>
					)
				)}
			</div>

			<AlertDialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Are you sure?</AlertDialogTitle>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleDelete();
							}}
							disabled={isDeleting}
							className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
						>
							{isDeleting ? "Deleting" : "Delete"}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</>
	);
}
