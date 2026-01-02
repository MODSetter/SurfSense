"use client";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { logsApiService } from "@/lib/apis/logs-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type LogStatus = "IN_PROGRESS" | "SUCCESS" | "FAILED";

export interface Log {
	id: number;
	level: LogLevel;
	status: LogStatus;
	message: string;
	source?: string;
	log_metadata?: Record<string, any>;
	created_at: string;
	search_space_id: number;
}

export interface LogFilters {
	search_space_id?: number;
	level?: LogLevel;
	status?: LogStatus;
	source?: string;
	start_date?: string;
	end_date?: string;
}

export interface LogSummary {
	total_logs: number;
	time_window_hours: number;
	by_status: Record<string, number>;
	by_level: Record<string, number>;
	by_source: Record<string, number>;
	active_tasks: Array<{
		id: number;
		task_name: string;
		message: string;
		started_at: string;
		source?: string;
		document_id?: number;
	}>;
	recent_failures: Array<{
		id: number;
		task_name: string;
		message: string;
		failed_at: string;
		source?: string;
		error_details?: string;
	}>;
}

export function useLogs(searchSpaceId?: number, filters: LogFilters = {}) {
	// Memoize filters to prevent infinite re-renders
	const memoizedFilters = useMemo(() => filters, [JSON.stringify(filters)]);

	const buildQueryParams = useCallback(
		(customFilters: LogFilters = {}) => {
			const params: Record<string, string> = {};

			const allFilters = { ...memoizedFilters, ...customFilters };

			if (allFilters.search_space_id) {
				params["search_space_id"] = allFilters.search_space_id.toString();
			}
			if (allFilters.level) {
				params["level"] = allFilters.level;
			}
			if (allFilters.status) {
				params["status"] = allFilters.status;
			}
			if (allFilters.source) {
				params["source"] = allFilters.source;
			}
			if (allFilters.start_date) {
				params["start_date"] = allFilters.start_date;
			}
			if (allFilters.end_date) {
				params["end_date"] = allFilters.end_date;
			}

			return params;
		},
		[memoizedFilters]
	);

	const {
		data: logs,
		isLoading: loading,
		error,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.logs.withQueryParams({
			search_space_id: searchSpaceId,
			...buildQueryParams(filters ?? {}),
		}),
		queryFn: () =>
			logsApiService.getLogs({
				queryParams: {
					search_space_id: searchSpaceId,
					...buildQueryParams(filters ?? {}),
				},
			}),
		enabled: !!searchSpaceId,
		staleTime: 3 * 60 * 1000,
	});

	return {
		logs: logs ?? [],
		loading,
		error,
		refreshLogs: refetch,
	};
}

// Separate hook for log summary with smart polling support for document processing indicator UI
// Polling only happens when there are active tasks, otherwise it stops to save resources
export function useLogsSummary(
	searchSpaceId: number,
	hours: number = 24,
	options: { refetchInterval?: number; enablePolling?: boolean } = {}
) {
	const { enablePolling = false, refetchInterval = 10000 } = options;

	const {
		data: summary,
		isLoading: loading,
		error,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.logs.summary(searchSpaceId),
		queryFn: () =>
			logsApiService.getLogSummary({
				search_space_id: searchSpaceId,
				hours: hours,
			}),
		enabled: !!searchSpaceId,
		staleTime: 3 * 60 * 1000,
		// Always refetch on mount to show fresh processing tasks when navigating to the page
		refetchOnMount: "always",
		// Smart polling: only poll when there are active tasks and polling is enabled
		// This prevents unnecessary API calls when nothing is being processed
		refetchInterval: enablePolling
			? (query) => {
					const data = query.state.data;
					// Only continue polling if there are active tasks
					if (data?.active_tasks && data.active_tasks.length > 0) {
						return refetchInterval;
					}
					// No active tasks - stop polling but check again after a longer interval
					// to catch any newly started tasks
					return 30000; // Check every 30 seconds when idle
				}
			: undefined,
	});

	return { summary, loading, error, refreshSummary: refetch };
}
