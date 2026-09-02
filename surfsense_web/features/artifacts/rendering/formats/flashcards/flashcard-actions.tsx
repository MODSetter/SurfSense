"use client";

import { RotateCcw } from "lucide-react";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useResetFlashcardProgress } from "@/features/artifacts/hooks/use-flashcard-study-state";
import type { ArtifactRendererActionsProps } from "@/features/artifacts/model/renderer";
import { FlashcardStudyStateSchema } from "./study-state";

export default function FlashcardActions({ workspaceId, manifest }: ArtifactRendererActionsProps) {
	const reset = useResetFlashcardProgress(workspaceId, manifest.artifact_id, manifest.generation);
	const parsedState = FlashcardStudyStateSchema.safeParse(manifest.flashcard_study_state);
	const hasProgress = parsedState.success && Object.keys(parsedState.data.marks).length > 0;
	const disabled = !hasProgress || reset.isPending;

	return (
		<AlertDialog>
			<AlertDialogTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					disabled={disabled}
					className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
				>
					<RotateCcw className="size-4" />
					<span className="sr-only">Reset flashcard progress</span>
				</Button>
			</AlertDialogTrigger>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>Reset flashcard progress?</AlertDialogTitle>
					<AlertDialogDescription>
						This clears every “Needs review” and “Got it” mark for this deck.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<AlertDialogFooter>
					<AlertDialogCancel>Cancel</AlertDialogCancel>
					<AlertDialogAction onClick={() => reset.mutate()}>Reset progress</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
