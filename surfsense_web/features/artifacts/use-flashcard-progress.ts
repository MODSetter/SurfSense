"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { artifactManifestQueryKey } from "./artifact-query";
import {
	type FlashcardMark,
	type FlashcardProgress,
	FlashcardProgressResponseSchema,
	normalizeFlashcardProgress,
} from "./flashcards-schema";
import type { ArtifactManifest } from "./model";

export class FlashcardGenerationConflictError extends Error {}

interface MarkVariables {
	cardIndex: number;
	mark: FlashcardMark | null;
	cardCount: number;
}

export function useFlashcardProgress(workspaceId: number, artifactId: number, generation: number) {
	const queryClient = useQueryClient();
	const queryKey = artifactManifestQueryKey(workspaceId, artifactId);

	return useMutation<
		FlashcardProgress,
		Error,
		MarkVariables,
		{ previous: ArtifactManifest | undefined }
	>({
		mutationFn: async ({ cardIndex, mark }) => {
			const response = await authenticatedFetch(
				buildBackendUrl(
					`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/flashcard-progress`
				),
				{
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						generation,
						card_index: cardIndex,
						mark,
					}),
				}
			);
			if (response.status === 409) {
				throw new FlashcardGenerationConflictError("The flashcard deck was revised");
			}
			if (!response.ok) throw new Error("Flashcard progress could not be saved");
			const parsed = FlashcardProgressResponseSchema.safeParse(await response.json());
			if (!parsed.success) throw new Error("Flashcard progress response is invalid");
			return parsed.data;
		},
		onMutate: async ({ cardIndex, mark, cardCount }) => {
			await queryClient.cancelQueries({ queryKey, exact: true });
			const previous = queryClient.getQueryData<ArtifactManifest>(queryKey);
			queryClient.setQueryData<ArtifactManifest>(queryKey, (current) => {
				if (!current || current.generation !== generation) return current;
				const progress = normalizeFlashcardProgress(
					current.flashcard_progress,
					generation,
					cardCount
				);
				const marks = { ...progress.marks };
				if (mark === null) delete marks[String(cardIndex)];
				else marks[String(cardIndex)] = mark;
				return {
					...current,
					flashcard_progress: { generation, marks },
				};
			});
			return { previous };
		},
		onError: (error, _variables, context) => {
			if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
			if (error instanceof FlashcardGenerationConflictError) {
				void queryClient.invalidateQueries({ queryKey, exact: true });
			}
		},
		onSuccess: (progress) => {
			queryClient.setQueryData<ArtifactManifest>(queryKey, (current) =>
				current ? { ...current, flashcard_progress: progress } : current
			);
		},
	});
}
