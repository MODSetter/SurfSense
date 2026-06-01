"use client";
import { useQuery } from "@tanstack/react-query";
import type { Run, RunListResponse } from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const DEFAULT_LIMIT = 50;
const DEFAULT_OFFSET = 0;

export interface UseAutomationRunsOptions {
	limit?: number;
	offset?: number;
	enabled?: boolean;
}

/** Paginated run history for one automation. Newest-first per backend. */
export function useAutomationRuns(
	automationId: number | undefined,
	{ limit = DEFAULT_LIMIT, offset = DEFAULT_OFFSET, enabled = true }: UseAutomationRunsOptions = {}
) {
	return useQuery<RunListResponse, Error>({
		queryKey: cacheKeys.automations.runs(automationId ?? 0, limit, offset),
		queryFn: () => automationsApiService.listRuns(automationId as number, { limit, offset }),
		enabled: enabled && !!automationId,
		staleTime: 30_000,
	});
}

/** Single run with the full snapshot, step results, output and artifacts. */
export function useAutomationRun(
	automationId: number | undefined,
	runId: number | undefined,
	options: { enabled?: boolean } = {}
) {
	const { enabled = true } = options;
	return useQuery<Run, Error>({
		queryKey: cacheKeys.automations.run(automationId ?? 0, runId ?? 0),
		queryFn: () => automationsApiService.getRun(automationId as number, runId as number),
		enabled: enabled && !!automationId && !!runId,
		staleTime: 30_000,
	});
}
