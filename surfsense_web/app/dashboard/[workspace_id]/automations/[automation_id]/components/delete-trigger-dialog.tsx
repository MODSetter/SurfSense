"use client";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { removeTriggerMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
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

interface DeleteTriggerDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	automationId: number;
	triggerId: number;
	triggerLabel: string;
}

/**
 * Confirm + detach one trigger from its automation. The automation itself
 * is untouched; only this trigger row is removed. The mutation atom
 * invalidates the parent automation detail so the page rerenders.
 */
export function DeleteTriggerDialog({
	open,
	onOpenChange,
	automationId,
	triggerId,
	triggerLabel,
}: DeleteTriggerDialogProps) {
	const { mutateAsync: removeTrigger } = useAtomValue(removeTriggerMutationAtom);
	const [submitting, setSubmitting] = useState(false);

	async function handleConfirm() {
		setSubmitting(true);
		try {
			await removeTrigger({ automationId, triggerId });
			onOpenChange(false);
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Remove this trigger?</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{triggerLabel}</span> will be detached.
						The automation itself stays, but it won't fire on this trigger anymore.
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
								Removing…
							</span>
						) : (
							"Remove"
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
