"use client";

import { useSetAtom } from "jotai";
import { MoreHorizontal, PenLine, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
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
	const openEditorPanel = useSetAtom(openEditorPanelAtom);

	const isEditable = EDITABLE_DOCUMENT_TYPES.includes(
		document.document_type as (typeof EDITABLE_DOCUMENT_TYPES)[number]
	);

	const isBeingProcessed =
		document.status?.state === "pending" || document.status?.state === "processing";

	const shouldShowDelete = !NON_DELETABLE_DOCUMENT_TYPES.includes(
		document.document_type as (typeof NON_DELETABLE_DOCUMENT_TYPES)[number]
	);

	const isEditDisabled = isBeingProcessed;
	const isDeleteDisabled = isBeingProcessed;

	const handleDelete = async () => {
		setIsDeleting(true);
		try {
			const ok = await deleteDocument(document.id);
			if (!ok) toast.error("Failed to delete document");
			// Note: Success toast is handled by the mutation atom's onSuccess callback
			// Cache is updated optimistically by the mutation, no need to refresh
		} catch (error: unknown) {
			console.error("Error deleting document:", error);
			// Check for 409 Conflict (document started processing after UI loaded)
			const status =
				(error as { response?: { status?: number } })?.response?.status ??
				(error as { status?: number })?.status;
			if (status === 409) {
				toast.error("Document is now being processed. Please try again later.");
			} else {
				toast.error("Failed to delete document");
			}
		} finally {
			setIsDeleting(false);
			setIsDeleteOpen(false);
		}
	};

	const handleEdit = () => {
		openEditorPanel({
			documentId: document.id,
			searchSpaceId: Number(searchSpaceId),
			title: document.title,
		});
	};

	return (
		<>
			{/* Desktop Actions */}
			<div className="hidden md:inline-flex items-center justify-center">
				{isEditable ? (
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/80"
							>
								<MoreHorizontal className="h-4 w-4" />
								<span className="sr-only">Open menu</span>
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							<DropdownMenuItem
								onClick={() => !isEditDisabled && handleEdit()}
								disabled={isEditDisabled}
								className={
									isEditDisabled ? "text-muted-foreground cursor-not-allowed opacity-50" : ""
								}
							>
								<PenLine className="mr-2 h-4 w-4" />
								<span>Edit</span>
							</DropdownMenuItem>
							{shouldShowDelete && (
								<DropdownMenuItem
									onClick={() => !isDeleteDisabled && setIsDeleteOpen(true)}
									disabled={isDeleteDisabled}
									className={
										isDeleteDisabled ? "text-muted-foreground cursor-not-allowed opacity-50" : ""
									}
								>
									<Trash2 className="mr-2 h-4 w-4" />
									<span>Delete</span>
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					shouldShowDelete && (
						<Button
							variant="ghost"
							size="icon"
							className={`h-8 w-8 ${isDeleteDisabled ? "text-muted-foreground cursor-not-allowed" : "text-muted-foreground hover:text-foreground"}`}
							onClick={() => !isDeleteDisabled && setIsDeleteOpen(true)}
							disabled={isDeleting || isDeleteDisabled}
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
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground">
								<MoreHorizontal className="h-4 w-4" />
								<span className="sr-only">Open menu</span>
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							<DropdownMenuItem
								onClick={() => !isEditDisabled && handleEdit()}
								disabled={isEditDisabled}
								className={
									isEditDisabled ? "text-muted-foreground cursor-not-allowed opacity-50" : ""
								}
							>
								<PenLine className="mr-2 h-4 w-4" />
								<span>Edit</span>
							</DropdownMenuItem>
							{shouldShowDelete && (
								<DropdownMenuItem
									onClick={() => !isDeleteDisabled && setIsDeleteOpen(true)}
									disabled={isDeleteDisabled}
									className={
										isDeleteDisabled ? "text-muted-foreground cursor-not-allowed opacity-50" : ""
									}
								>
									<Trash2 className="mr-2 h-4 w-4" />
									<span>Delete</span>
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					shouldShowDelete && (
						<Button
							variant="ghost"
							size="icon"
							className={`h-8 w-8 ${isDeleteDisabled ? "text-muted-foreground cursor-not-allowed" : "text-muted-foreground hover:text-foreground"}`}
							onClick={() => !isDeleteDisabled && setIsDeleteOpen(true)}
							disabled={isDeleting || isDeleteDisabled}
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
						<AlertDialogTitle>Delete document?</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone. This will permanently delete this document from your
							search space.
						</AlertDialogDescription>
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
