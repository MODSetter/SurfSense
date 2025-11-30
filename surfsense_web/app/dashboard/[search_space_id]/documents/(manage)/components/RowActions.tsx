"use client";

import { FileText, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
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
	searchSpaceId,
}: {
	document: Document;
	deleteDocument: (id: number) => Promise<boolean>;
	refreshDocuments: () => Promise<void>;
	searchSpaceId: string;
}) {
	const [isOpen, setIsOpen] = useState(false);
	const [isDeleting, setIsDeleting] = useState(false);
	const router = useRouter();

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

	const handleEdit = () => {
		router.push(`/dashboard/${searchSpaceId}/editor/${document.id}`);
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
					<DropdownMenuItem onClick={handleEdit}>
						<Pencil className="mr-0 h-4 w-4" />
						Edit Document
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<JsonMetadataViewer
						title={document.title}
						metadata={document.document_metadata}
						trigger={
							<DropdownMenuItem onSelect={(e) => e.preventDefault()}>
								<FileText className="mr-0 h-4 w-4" />
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
								<Trash2 className="mr-0 h-4 w-4 text-destructive" />
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
