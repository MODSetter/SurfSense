import { z } from "zod";
import { paginationQueryParams } from ".";

/**
 * ENUMS
 */
export const logLevelEnum = z.enum(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]);

export const logStatusEnum = z.enum(["IN_PROGRESS", "SUCCESS", "FAILED"]);

/**
 * Base log schema
 */
export const log = z.object({
	id: z.number(),
	level: logLevelEnum,
	status: logStatusEnum,
	message: z.string(),
	source: z.string().nullable().optional(),
	log_metadata: z.record(z.string(), z.any()).nullable().optional(),
	created_at: z.string(),
	search_space_id: z.number(),
});

export const logBase = log.omit({ id: true, created_at: true });

/**
 * Create log
 */
export const createLogRequest = logBase.extend({ search_space_id: z.number() });
export const createLogResponse = log;

/**
 * Update log
 */
export const updateLogRequest = logBase.partial();
export const updateLogResponse = log;

/**
 * Delete log
 */
export const deleteLogRequest = z.object({ id: z.number() });
export const deleteLogResponse = z.object({
	message: z.string().default("Log deleted successfully"),
});

/**
 * Get logs (list)
 */
export const logFilters = z.object({
	search_space_id: z.number().optional(),
	level: logLevelEnum.optional(),
	status: logStatusEnum.optional(),
	source: z.string().optional(),
	start_date: z.string().optional(),
	end_date: z.string().optional(),
});

export const getLogsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().optional(),
			level: logLevelEnum.optional(),
			status: logStatusEnum.optional(),
			source: z.string().optional(),
			start_date: z.string().optional(),
			end_date: z.string().optional(),
		})
		.nullish(),
});
export const getLogsResponse = z.array(log);

/**
 * Get single log
 */
export const getLogRequest = z.object({ id: z.number() });
export const getLogResponse = log;

/**
 * Log summary (used for summary dashboard)
 */
export const logActiveTask = z.object({
	id: z.number(),
	task_name: z.string(),
	message: z.string(),
	started_at: z.string(),
	source: z.string().nullable().optional(),
	document_id: z.number().nullable().optional(),
	connector_id: z.number().nullable().optional(),
});
export const logFailure = z.object({
	id: z.number(),
	task_name: z.string(),
	message: z.string(),
	failed_at: z.string(),
	source: z.string().nullable().optional(),
	error_details: z.string().nullable().optional(),
});
export const logSummary = z.object({
	total_logs: z.number(),
	time_window_hours: z.number(),
	by_status: z.record(z.string(), z.number()),
	by_level: z.record(z.string(), z.number()),
	by_source: z.record(z.string(), z.number()),
	active_tasks: z.array(logActiveTask),
	recent_failures: z.array(logFailure),
});
export const getLogSummaryRequest = z.object({
	search_space_id: z.number(),
	hours: z.number().optional(),
});
export const getLogSummaryResponse = logSummary;

/**
 * Typescript types
 */
export type Log = z.infer<typeof log>;
export type LogLevelEnum = z.infer<typeof logLevelEnum>;
export type LogStatusEnum = z.infer<typeof logStatusEnum>;
export type LogFilters = z.infer<typeof logFilters>;
export type CreateLogRequest = z.infer<typeof createLogRequest>;
export type CreateLogResponse = z.infer<typeof createLogResponse>;
export type UpdateLogRequest = z.infer<typeof updateLogRequest>;
export type UpdateLogResponse = z.infer<typeof updateLogResponse>;
export type DeleteLogRequest = z.infer<typeof deleteLogRequest>;
export type DeleteLogResponse = z.infer<typeof deleteLogResponse>;
export type GetLogsRequest = z.infer<typeof getLogsRequest>;
export type GetLogsResponse = z.infer<typeof getLogsResponse>;
export type GetLogRequest = z.infer<typeof getLogRequest>;
export type GetLogResponse = z.infer<typeof getLogResponse>;
export type LogSummary = z.infer<typeof logSummary>;
export type LogFailure = z.infer<typeof logFailure>;
export type LogActiveTask = z.infer<typeof logActiveTask>;
export type GetLogSummaryRequest = z.infer<typeof getLogSummaryRequest>;
export type GetLogSummaryResponse = z.infer<typeof getLogSummaryResponse>;
