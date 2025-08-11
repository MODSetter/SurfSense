"use client";

import { MoreHorizontal } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { JsonMetadataViewer } from "@/components/json-metadata-viewer";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Document } from "./types";

export function RowActions({
	document,
	deleteDocument,
	refreshDocuments,
}: {
	document: Document;
	deleteDocument: (id: number) => Promise<boolean>;
	refreshDocuments: () => Promise<void>;
}) {
	const [isOpen, setIsOpen] = useState(false);
	const [isDeleting, setIsDeleting] = useState(false);

	const handleDelete = async () => {
		setIsDeleting(true);
		try {
			const ok = await deleteDocument(document.id);
			if (ok) toast.success("Document deleted successfully");
			else toast.error("Failed to delete document");
			await refreshDocuments();
		} catch (error) {
			console.error("Error deleting document:", error);
			toast.error("Failed to delete document");
		} finally {
			setIsDeleting(false);
			setIsOpen(false);
		}
	};

	return (
		<div className="flex justify-end">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<MoreHorizontal className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<JsonMetadataViewer
						title={document.title}
						metadata={document.document_metadata}
						trigger={
							<DropdownMenuItem onSelect={(e) => e.preventDefault()}>
								View Metadata
							</DropdownMenuItem>
						}
					/>
					<DropdownMenuSeparator />
					<AlertDialog open={isOpen} onOpenChange={setIsOpen}>
						<AlertDialogTrigger asChild>
							<DropdownMenuItem
								className="text-destructive focus:text-destructive"
								onSelect={(e) => {
									e.preventDefault();
									setIsOpen(true);
								}}
							>
								Delete
							</DropdownMenuItem>
						</AlertDialogTrigger>
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
								>
									{isDeleting ? "Deleting..." : "Delete"}
								</AlertDialogAction>
							</AlertDialogFooter>
						</AlertDialogContent>
					</AlertDialog>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
