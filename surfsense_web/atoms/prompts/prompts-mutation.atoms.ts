import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	PromptCreateRequest,
	PromptRead,
	PromptUpdateRequest,
} from "@/contracts/types/prompts.types";
import { promptsApiService } from "@/lib/apis/prompts-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createPromptMutationAtom = atomWithMutation(() => ({
	mutationKey: ["prompts", "create"],
	mutationFn: async (request: PromptCreateRequest) => {
		return promptsApiService.create(request);
	},
	onSuccess: () => {
		toast.success("Prompt created");
		queryClient.invalidateQueries({ queryKey: cacheKeys.prompts.all() });
	},
	onError: (error: Error) => {
		toast.error(error.message || "Failed to create prompt");
	},
}));

export const updatePromptMutationAtom = atomWithMutation(() => ({
	mutationKey: ["prompts", "update"],
	mutationFn: async ({ id, ...data }: PromptUpdateRequest & { id: number }) => {
		return promptsApiService.update(id, data);
	},
	onSuccess: () => {
		toast.success("Prompt updated");
		queryClient.invalidateQueries({ queryKey: cacheKeys.prompts.all() });
	},
	onError: (error: Error) => {
		toast.error(error.message || "Failed to update prompt");
	},
}));

export const deletePromptMutationAtom = atomWithMutation(() => ({
	mutationKey: ["prompts", "delete"],
	mutationFn: async (id: number) => {
		return promptsApiService.delete(id);
	},
	onSuccess: (_: unknown, id: number) => {
		toast.success("Prompt deleted");
		queryClient.setQueryData(cacheKeys.prompts.all(), (old: PromptRead[] | undefined) => {
			if (!old) return old;
			return old.filter((p) => p.id !== id);
		});
		queryClient.invalidateQueries({ queryKey: cacheKeys.prompts.public() });
	},
	onError: (error: Error) => {
		toast.error(error.message || "Failed to delete prompt");
	},
}));

export const copyPromptMutationAtom = atomWithMutation(() => ({
	mutationKey: ["prompts", "copy"],
	mutationFn: async (promptId: number) => {
		return promptsApiService.copy(promptId);
	},
	onSuccess: () => {
		toast.success("Prompt added to your collection");
		queryClient.invalidateQueries({ queryKey: cacheKeys.prompts.all() });
	},
	onError: (error: Error) => {
		toast.error(error.message || "Failed to copy prompt");
	},
}));
