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
import { FlashcardProgressResponseSchema } from "./flashcards-schema";
import type { ArtifactManifest } from "./model";
import { useResetFlashcardProgress } from "./use-flashcard-progress";

export function FlashcardResetButton({
	workspaceId,
	artifactId,
	manifest,
}: {
	workspaceId: number;
	artifactId: number;
	manifest: ArtifactManifest;
}) {
	const reset = useResetFlashcardProgress(workspaceId, artifactId, manifest.generation);
	const parsedProgress = FlashcardProgressResponseSchema.safeParse(manifest.flashcard_progress);
	const hasProgress = parsedProgress.success && Object.keys(parsedProgress.data.marks).length > 0;
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
