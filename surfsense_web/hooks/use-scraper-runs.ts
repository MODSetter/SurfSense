"use client";
import { useQuery } from "@tanstack/react-query";
import type {
	ListScraperRunsParams,
	ScraperRunDetail,
	ScraperRunSummary,
} from "@/contracts/types/scraper.types";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

/** Paginated scraper-run history for a workspace, newest-first. */
export function useScraperRuns(workspaceId: number | string, params: ListScraperRunsParams = {}) {
	return useQuery<ScraperRunSummary[], Error>({
		queryKey: [...cacheKeys.scrapers.runs(workspaceId), params],
		queryFn: () => scrapersApiService.listRuns(workspaceId, params),
		staleTime: 10_000,
	});
}

/** Full run record (input + stored output) — fetched lazily on row expand. */
export function useScraperRun(
	workspaceId: number | string,
	runId: string | undefined,
	options: { enabled?: boolean } = {}
) {
	const { enabled = true } = options;
	return useQuery<ScraperRunDetail, Error>({
		queryKey: cacheKeys.scrapers.run(workspaceId, runId ?? ""),
		queryFn: () => scrapersApiService.getRun(workspaceId, runId as string),
		enabled: enabled && !!runId,
		staleTime: 30_000,
	});
}
