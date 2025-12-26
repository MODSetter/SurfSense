"use client";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { logsApiService } from "@/lib/apis/logs-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
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
			skip: 0,
			limit: 5,
			...buildQueryParams(filters ?? {}),
		}),
		queryFn: () =>
			logsApiService.getLogs({
				queryParams: {
					search_space_id: searchSpaceId,
					skip: 0,
					limit: 5,
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

// Separate hook for log summary
export function useLogsSummary(searchSpaceId: number, hours: number = 24) {
	const [summary, setSummary] = useState<LogSummary | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchSummary = useCallback(async () => {
		if (!searchSpaceId) return;

		try {
			setLoading(true);
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs/search-space/${searchSpaceId}/summary?hours=${hours}`,
				{ method: "GET" }
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch logs summary");
			}

			const data = await response.json();
			setSummary(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch logs summary");
			console.error("Error fetching logs summary:", err);
			throw err;
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId, hours]);

	useEffect(() => {
		fetchSummary();
	}, [fetchSummary]);

	const refreshSummary = useCallback(() => {
		return fetchSummary();
	}, [fetchSummary]);

	return { summary, loading, error, refreshSummary };
}
