"use client";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { deleteAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
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
import { Spinner } from "@/components/ui/spinner";

interface DeleteAutomationDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	automationId: number;
	automationName: string;
	searchSpaceId: number;
}

/**
 * Confirm + delete one automation. FK cascade on the backend wipes attached
 * triggers and runs, so we mention it explicitly. List re-fetch is handled
 * by the mutation atom's onSuccess.
 */
export function DeleteAutomationDialog({
	open,
	onOpenChange,
	automationId,
	automationName,
	searchSpaceId,
}: DeleteAutomationDialogProps) {
	const { mutateAsync: deleteAutomation } = useAtomValue(deleteAutomationMutationAtom);
	const [submitting, setSubmitting] = useState(false);

	async function handleConfirm() {
		setSubmitting(true);
		try {
			await deleteAutomation({ automationId, searchSpaceId });
			onOpenChange(false);
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Delete this automation?</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{automationName}</span> and all of its
						triggers and run history will be removed. This cannot be undone.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<AlertDialogFooter>
					<AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						onClick={handleConfirm}
						disabled={submitting}
						className="bg-destructive text-white hover:bg-destructive/90"
					>
						{submitting ? (
							<span className="inline-flex items-center gap-2">
								<Spinner size="xs" />
								Deleting…
							</span>
						) : (
							"Delete"
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
