"use client";

import { FileText, Pencil, Trash2 } from "lucide-react";
import { motion } from "motion/react";
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
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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
	const [isDeleteOpen, setIsDeleteOpen] = useState(false);
	const [isMetadataOpen, setIsMetadataOpen] = useState(false);
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
			setIsDeleteOpen(false);
		}
	};

	const handleEdit = () => {
		router.push(`/dashboard/${searchSpaceId}/editor/${document.id}`);
	};

	return (
		<div className="flex items-center justify-end gap-1">
			{/* Edit Button */}
			<Tooltip>
				<TooltipTrigger asChild>
					<motion.div
						whileHover={{ scale: 1.1 }}
						whileTap={{ scale: 0.95 }}
						transition={{ type: "spring", stiffness: 400, damping: 17 }}
					>
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/80"
							onClick={handleEdit}
						>
							<Pencil className="h-4 w-4" />
							<span className="sr-only">Edit Document</span>
						</Button>
					</motion.div>
				</TooltipTrigger>
				<TooltipContent side="top">
					<p>Edit Document</p>
				</TooltipContent>
			</Tooltip>

			{/* View Metadata Button */}
			<Tooltip>
				<TooltipTrigger asChild>
					<motion.div
						whileHover={{ scale: 1.1 }}
						whileTap={{ scale: 0.95 }}
						transition={{ type: "spring", stiffness: 400, damping: 17 }}
					>
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/80"
							onClick={() => setIsMetadataOpen(true)}
						>
							<FileText className="h-4 w-4" />
							<span className="sr-only">View Metadata</span>
						</Button>
					</motion.div>
				</TooltipTrigger>
				<TooltipContent side="top">
					<p>View Metadata</p>
				</TooltipContent>
			</Tooltip>
			<JsonMetadataViewer
				title={document.title}
				metadata={document.document_metadata}
				open={isMetadataOpen}
				onOpenChange={setIsMetadataOpen}
			/>

			{/* Delete Button */}
			<Tooltip>
				<TooltipTrigger asChild>
					<motion.div
						whileHover={{ scale: 1.1 }}
						whileTap={{ scale: 0.95 }}
						transition={{ type: "spring", stiffness: 400, damping: 17 }}
					>
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
					</motion.div>
				</TooltipTrigger>
				<TooltipContent side="top">
					<p>Delete</p>
				</TooltipContent>
			</Tooltip>
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
							{isDeleting ? "Deleting..." : "Delete"}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
