"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

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
	const [logs, setLogs] = useState<Log[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// Memoize filters to prevent infinite re-renders
	const memoizedFilters = useMemo(() => filters, [JSON.stringify(filters)]);

	const buildQueryParams = useCallback(
		(customFilters: LogFilters = {}) => {
			const params = new URLSearchParams();

			const allFilters = { ...memoizedFilters, ...customFilters };

			if (allFilters.search_space_id) {
				params.append("search_space_id", allFilters.search_space_id.toString());
			}
			if (allFilters.level) {
				params.append("level", allFilters.level);
			}
			if (allFilters.status) {
				params.append("status", allFilters.status);
			}
			if (allFilters.source) {
				params.append("source", allFilters.source);
			}
			if (allFilters.start_date) {
				params.append("start_date", allFilters.start_date);
			}
			if (allFilters.end_date) {
				params.append("end_date", allFilters.end_date);
			}

			return params.toString();
		},
		[memoizedFilters]
	);

	const fetchLogs = useCallback(
		async (customFilters: LogFilters = {}, options: { skip?: number; limit?: number } = {}) => {
			try {
				setLoading(true);

				const params = new URLSearchParams(buildQueryParams(customFilters));
				if (options.skip !== undefined) params.append("skip", options.skip.toString());
				if (options.limit !== undefined) params.append("limit", options.limit.toString());

				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs?${params}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "GET",
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to fetch logs");
				}

				const data = await response.json();
				setLogs(data);
				setError(null);
				return data;
			} catch (err: any) {
				setError(err.message || "Failed to fetch logs");
				console.error("Error fetching logs:", err);
				throw err;
			} finally {
				setLoading(false);
			}
		},
		[buildQueryParams]
	);

	// Initial fetch
	useEffect(() => {
		const initialFilters = searchSpaceId
			? { ...memoizedFilters, search_space_id: searchSpaceId }
			: memoizedFilters;
		fetchLogs(initialFilters);
	}, [searchSpaceId, fetchLogs, memoizedFilters]);

	// Function to refresh the logs list
	const refreshLogs = useCallback(
		async (customFilters: LogFilters = {}) => {
			const finalFilters = searchSpaceId
				? { ...customFilters, search_space_id: searchSpaceId }
				: customFilters;
			return await fetchLogs(finalFilters);
		},
		[searchSpaceId, fetchLogs]
	);

	// Function to create a new log
	const createLog = useCallback(async (logData: Omit<Log, "id" | "created_at">) => {
		try {
			const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs`, {
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
				},
				method: "POST",
				body: JSON.stringify(logData),
			});

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to create log");
			}

			const newLog = await response.json();
			setLogs((prevLogs) => [newLog, ...prevLogs]);
			toast.success("Log created successfully");
			return newLog;
		} catch (err: any) {
			toast.error(err.message || "Failed to create log");
			console.error("Error creating log:", err);
			throw err;
		}
	}, []);

	// Function to update a log
	const updateLog = useCallback(
		async (
			logId: number,
			updateData: Partial<Omit<Log, "id" | "created_at" | "search_space_id">>
		) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs/${logId}`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "PUT",
						body: JSON.stringify(updateData),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to update log");
				}

				const updatedLog = await response.json();
				setLogs((prevLogs) => prevLogs.map((log) => (log.id === logId ? updatedLog : log)));
				toast.success("Log updated successfully");
				return updatedLog;
			} catch (err: any) {
				toast.error(err.message || "Failed to update log");
				console.error("Error updating log:", err);
				throw err;
			}
		},
		[]
	);

	// Function to delete a log
	const deleteLog = useCallback(async (logId: number) => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs/${logId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "DELETE",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to delete log");
			}

			setLogs((prevLogs) => prevLogs.filter((log) => log.id !== logId));
			toast.success("Log deleted successfully");
			return true;
		} catch (err: any) {
			toast.error(err.message || "Failed to delete log");
			console.error("Error deleting log:", err);
			return false;
		}
	}, []);

	// Function to get a single log
	const getLog = useCallback(async (logId: number) => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs/${logId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch log");
			}

			return await response.json();
		} catch (err: any) {
			toast.error(err.message || "Failed to fetch log");
			console.error("Error fetching log:", err);
			throw err;
		}
	}, []);

	return {
		logs,
		loading,
		error,
		refreshLogs,
		createLog,
		updateLog,
		deleteLog,
		getLog,
		fetchLogs,
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
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/logs/search-space/${searchSpaceId}/summary?hours=${hours}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
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
