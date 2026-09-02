"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { artifactManifestQueryKey } from "@/features/artifacts/api/artifact-queries";
import type { ArtifactManifest } from "@/features/artifacts/model/artifact";
import {
	type QuizRetakeMode,
	type QuizState,
	QuizStateSchema,
} from "@/features/artifacts/rendering/formats/quiz/state";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

export class QuizGenerationConflictError extends Error {}

async function readQuizState(response: Response, failureMessage: string): Promise<QuizState> {
	if (response.status === 409) {
		throw new QuizGenerationConflictError(
			(await response.json().catch(() => null))?.detail ?? failureMessage
		);
	}
	if (!response.ok) throw new Error(failureMessage);
	const parsed = QuizStateSchema.safeParse(await response.json());
	if (!parsed.success) throw new Error("Quiz state response is invalid");
	return parsed.data;
}

function useQuizMutation<TVariables>({
	workspaceId,
	artifactId,
	generation,
	path,
	method,
}: {
	workspaceId: number;
	artifactId: number;
	generation: number;
	path: string;
	method: "PUT" | "POST";
}) {
	const queryClient = useQueryClient();
	const queryKey = artifactManifestQueryKey(workspaceId, artifactId);

	return useMutation<QuizState, Error, TVariables>({
		mutationFn: async (variables) => {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/${path}`),
				{
					method,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ generation, ...variables }),
				}
			);
			return readQuizState(response, "Quiz progress could not be saved");
		},
		onError: (error) => {
			if (error instanceof QuizGenerationConflictError) {
				void queryClient.invalidateQueries({ queryKey, exact: true });
			}
		},
		onSuccess: (state) => {
			queryClient.setQueryData<ArtifactManifest>(queryKey, (current) =>
				current ? { ...current, quiz_state: state } : current
			);
		},
	});
}

export function useSubmitQuizAnswer(workspaceId: number, artifactId: number, generation: number) {
	return useQuizMutation<{ question_index: number; selected_option_index: number }>({
		workspaceId,
		artifactId,
		generation,
		path: "quiz-answer",
		method: "PUT",
	});
}

export function useSkipQuizQuestion(workspaceId: number, artifactId: number, generation: number) {
	return useQuizMutation<{ question_index: number }>({
		workspaceId,
		artifactId,
		generation,
		path: "quiz-skip",
		method: "PUT",
	});
}

export function useRetakeQuiz(workspaceId: number, artifactId: number, generation: number) {
	return useQuizMutation<{ mode: QuizRetakeMode }>({
		workspaceId,
		artifactId,
		generation,
		path: "quiz-retake",
		method: "POST",
	});
}
