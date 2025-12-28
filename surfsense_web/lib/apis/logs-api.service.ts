import {
	type CreateLogRequest,
	createLogRequest,
	createLogResponse,
	type DeleteLogRequest,
	deleteLogRequest,
	deleteLogResponse,
	type GetLogRequest,
	type GetLogSummaryRequest,
	type GetLogsRequest,
	getLogRequest,
	getLogResponse,
	getLogSummaryRequest,
	getLogSummaryResponse,
	getLogsRequest,
	getLogsResponse,
	type Log,
	log,
	type UpdateLogRequest,
	updateLogRequest,
	updateLogResponse,
} from "@/contracts/types/log.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class LogsApiService {
	/**
	 * Get a list of logs with optional filtering and pagination
	 */
	getLogs = async (request: GetLogsRequest) => {
		const parsedRequest = getLogsRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => {
						// Handle array values (document_type)
						if (Array.isArray(v)) {
							return [k, v.join(",")];
						}
						return [k, String(v)];
					})
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";
		return baseApiService.get(`/api/v1/logs?${queryParams}`, getLogsResponse);
	};

	/**
	 * Get a single log by ID
	 */
	getLog = async (request: GetLogRequest) => {
		const parsedRequest = getLogRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.get(`/api/v1/logs/${request.id}`, getLogResponse);
	};

	/**
	 * Create a log entry
	 */
	createLog = async (request: CreateLogRequest) => {
		const parsedRequest = createLogRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.post(`/api/v1/logs`, createLogResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Update a log entry
	 */
	updateLog = async (logId: number, request: UpdateLogRequest) => {
		const parsedRequest = updateLogRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.put(`/api/v1/logs/${logId}`, updateLogResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Delete a log entry
	 */
	deleteLog = async (request: DeleteLogRequest) => {
		const parsedRequest = deleteLogRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.delete(`/api/v1/logs/${parsedRequest.data.id}`, deleteLogResponse);
	};

	/**
	 * Get summary for logs by search space
	 */
	getLogSummary = async (request: GetLogSummaryRequest) => {
		const parsedRequest = getLogSummaryRequest.safeParse(request);
		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		const { search_space_id, hours } = parsedRequest.data;
		const url = `/api/v1/logs/search-space/${search_space_id}/summary${hours ? `?hours=${hours}` : ""}`;
		return baseApiService.get(url, getLogSummaryResponse);
	};
}

export const logsApiService = new LogsApiService();
