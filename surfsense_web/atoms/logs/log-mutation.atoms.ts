import { atomWithMutation } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import type {
	CreateLogRequest,
	DeleteLogRequest,
	UpdateLogRequest,
} from "@/contracts/types/log.types";
import { logsApiService } from "@/lib/apis/logs-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

/**
 * Create Log Mutation
 */
export const createLogMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	return {
		mutationKey: cacheKeys.logs.list(searchSpaceId ?? undefined),
		enabled: !!searchSpaceId,
		mutationFn: async (request: CreateLogRequest) => logsApiService.createLog(request),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list(searchSpaceId ?? undefined) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(searchSpaceId ?? undefined),
			});
		},
	};
});

/**
 * Update Log Mutation
 */
export const updateLogMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	return {
		mutationKey: cacheKeys.logs.list(searchSpaceId ?? undefined),
		enabled: !!searchSpaceId,
		mutationFn: async ({ logId, data }: { logId: number; data: UpdateLogRequest }) =>
			logsApiService.updateLog(logId, data),
		onSuccess: (_data, variables) => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.logs.detail(variables.logId) });
			queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list(searchSpaceId ?? undefined) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(searchSpaceId ?? undefined),
			});
		},
	};
});

/**
 * Delete Log Mutation
 */
export const deleteLogMutationAtom = atomWithMutation((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);
	return {
		mutationKey: cacheKeys.logs.list(searchSpaceId ?? undefined),
		enabled: !!searchSpaceId,
		mutationFn: async (request: DeleteLogRequest) => logsApiService.deleteLog(request),
		onSuccess: (_data, request) => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list(searchSpaceId ?? undefined) });
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(searchSpaceId ?? undefined),
			});
			if (request?.id)
				queryClient.invalidateQueries({ queryKey: cacheKeys.logs.detail(request.id) });
		},
	};
});
