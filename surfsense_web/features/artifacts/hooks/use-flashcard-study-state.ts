"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { artifactManifestQueryKey } from "@/features/artifacts/api/artifact-queries";
import type { ArtifactManifest } from "@/features/artifacts/model/artifact";
import {
	type FlashcardMark,
	type FlashcardStudyState,
	FlashcardStudyStateSchema,
	normalizeFlashcardStudyState,
} from "@/features/artifacts/rendering/formats/flashcards/study-state";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

export class FlashcardGenerationConflictError extends Error {}

interface MarkVariables {
	cardIndex: number;
	mark: FlashcardMark | null;
	cardCount: number;
}

interface ShuffleVariables {
	order: number[];
	cardCount: number;
}

interface MutationContext {
	previous: ArtifactManifest | undefined;
}

async function readStudyState(response: Response, failureMessage: string) {
	if (response.status === 409) {
		throw new FlashcardGenerationConflictError("The flashcard deck was revised");
	}
	if (!response.ok) throw new Error(failureMessage);
	const parsed = FlashcardStudyStateSchema.safeParse(await response.json());
	if (!parsed.success) throw new Error("Flashcard study-state response is invalid");
	return parsed.data;
}

function useStudyStateMutation<TVariables>({
	workspaceId,
	artifactId,
	generation,
	mutationFn,
	optimistic,
}: {
	workspaceId: number;
	artifactId: number;
	generation: number;
	mutationFn: (variables: TVariables) => Promise<FlashcardStudyState>;
	optimistic: (manifest: ArtifactManifest, variables: TVariables) => ArtifactManifest;
}) {
	const queryClient = useQueryClient();
	const queryKey = artifactManifestQueryKey(workspaceId, artifactId);

	return useMutation<FlashcardStudyState, Error, TVariables, MutationContext>({
		mutationFn,
		onMutate: async (variables) => {
			await queryClient.cancelQueries({ queryKey, exact: true });
			const previous = queryClient.getQueryData<ArtifactManifest>(queryKey);
			queryClient.setQueryData<ArtifactManifest>(queryKey, (current) =>
				current?.generation === generation ? optimistic(current, variables) : current
			);
			return { previous };
		},
		onError: (error, _variables, context) => {
			if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
			if (error instanceof FlashcardGenerationConflictError) {
				void queryClient.invalidateQueries({ queryKey, exact: true });
			}
		},
		onSuccess: (state) => {
			queryClient.setQueryData<ArtifactManifest>(queryKey, (current) =>
				current ? { ...current, flashcard_study_state: state } : current
			);
		},
	});
}

export function useMarkFlashcard(workspaceId: number, artifactId: number, generation: number) {
	return useStudyStateMutation<MarkVariables>({
		workspaceId,
		artifactId,
		generation,
		mutationFn: async ({ cardIndex, mark }) => {
			const response = await authenticatedFetch(
				buildBackendUrl(
					`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/flashcard-progress`
				),
				{
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ generation, card_index: cardIndex, mark }),
				}
			);
			return readStudyState(response, "Flashcard progress could not be saved");
		},
		optimistic: (manifest, { cardIndex, mark, cardCount }) => {
			const state = normalizeFlashcardStudyState(
				manifest.flashcard_study_state,
				generation,
				cardCount
			);
			const marks = { ...state.marks };
			if (mark === null) delete marks[String(cardIndex)];
			else marks[String(cardIndex)] = mark;
			return { ...manifest, flashcard_study_state: { ...state, marks } };
		},
	});
}

export function useResetFlashcardProgress(
	workspaceId: number,
	artifactId: number,
	generation: number
) {
	return useStudyStateMutation<void>({
		workspaceId,
		artifactId,
		generation,
		mutationFn: async () => {
			const response = await authenticatedFetch(
				buildBackendUrl(
					`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/flashcard-progress?generation=${generation}`
				),
				{ method: "DELETE" }
			);
			return readStudyState(response, "Flashcard progress could not be reset");
		},
		optimistic: (manifest) => {
			const parsed = FlashcardStudyStateSchema.safeParse(manifest.flashcard_study_state);
			return parsed.success
				? { ...manifest, flashcard_study_state: { ...parsed.data, marks: {} } }
				: manifest;
		},
	});
}

export function useShuffleFlashcards(workspaceId: number, artifactId: number, generation: number) {
	return useStudyStateMutation<ShuffleVariables>({
		workspaceId,
		artifactId,
		generation,
		mutationFn: async ({ order }) => {
			const response = await authenticatedFetch(
				buildBackendUrl(
					`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/flashcard-order`
				),
				{
					method: "PUT",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ generation, order }),
				}
			);
			return readStudyState(response, "Flashcard order could not be saved");
		},
		optimistic: (manifest, { order, cardCount }) => {
			const state = normalizeFlashcardStudyState(
				manifest.flashcard_study_state,
				generation,
				cardCount
			);
			return { ...manifest, flashcard_study_state: { ...state, order } };
		},
	});
}
