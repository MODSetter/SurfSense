import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
  CreateLogRequest,
  DeleteLogRequest,
  UpdateLogRequest,
  GetLogSummaryRequest,
} from "@/contracts/types/log.types";
import { logsApiService } from "@/lib/apis/logs-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

/**
 * Create Log Mutation
 */
export const createLogMutationAtom = atomWithMutation(() => ({
  mutationKey: cacheKeys.logs.create(),
  mutationFn: async (request: CreateLogRequest) => logsApiService.createLog(request),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list() });
  },
}));

/**
 * Update Log Mutation
 */
export const updateLogMutationAtom = atomWithMutation(() => ({
  mutationKey: cacheKeys.logs.update(),
  mutationFn: async ({ logId, data }: { logId: number; data: UpdateLogRequest }) =>
    logsApiService.updateLog(logId, data),
  onSuccess: (_data, variables) => {
    queryClient.invalidateQueries({ queryKey: cacheKeys.logs.detail(variables.logId) });
    queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list() });
  },
}));

/**
 * Delete Log Mutation
 */
export const deleteLogMutationAtom = atomWithMutation(() => ({
  mutationKey: cacheKeys.logs.delete(),
  mutationFn: async (request: DeleteLogRequest) => logsApiService.deleteLog(request),
  onSuccess: (_data, request) => {
    queryClient.invalidateQueries({ queryKey: cacheKeys.logs.list() });
    if (request?.id) queryClient.invalidateQueries({ queryKey: cacheKeys.logs.detail(request.id) });
  },
}));

