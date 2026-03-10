import {
	type GetBatchUnreadCountResponse,
	type GetNotificationsRequest,
	type GetNotificationsResponse,
	type GetSourceTypesResponse,
	type GetUnreadCountResponse,
	getBatchUnreadCountResponse,
	getNotificationsRequest,
	getNotificationsResponse,
	getSourceTypesResponse,
	getUnreadCountResponse,
	type InboxItemTypeEnum,
	type MarkAllNotificationsReadResponse,
	type MarkNotificationReadRequest,
	type MarkNotificationReadResponse,
	markAllNotificationsReadResponse,
	markNotificationReadRequest,
	markNotificationReadResponse,
	type NotificationCategory,
} from "@/contracts/types/inbox.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class NotificationsApiService {
	/**
	 * Get notifications with pagination
	 */
	getNotifications = async (
		request: GetNotificationsRequest
	): Promise<GetNotificationsResponse> => {
		const parsedRequest = getNotificationsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { queryParams } = parsedRequest.data;

		// Build query string from params
		const params = new URLSearchParams();

		if (queryParams.search_space_id !== undefined) {
			params.append("search_space_id", String(queryParams.search_space_id));
		}
		if (queryParams.type) {
			params.append("type", queryParams.type);
		}
		if (queryParams.category) {
			params.append("category", queryParams.category);
		}
		if (queryParams.source_type) {
			params.append("source_type", queryParams.source_type);
		}
		if (queryParams.filter) {
			params.append("filter", queryParams.filter);
		}
		if (queryParams.before_date) {
			params.append("before_date", queryParams.before_date);
		}
		if (queryParams.limit !== undefined) {
			params.append("limit", String(queryParams.limit));
		}
		if (queryParams.offset !== undefined) {
			params.append("offset", String(queryParams.offset));
		}
		if (queryParams.search) {
			params.append("search", queryParams.search);
		}

		const queryString = params.toString();

		return baseApiService.get(
			`/api/v1/notifications${queryString ? `?${queryString}` : ""}`,
			getNotificationsResponse
		);
	};

	/**
	 * Mark a single notification as read
	 */
	markAsRead = async (
		request: MarkNotificationReadRequest
	): Promise<MarkNotificationReadResponse> => {
		const parsedRequest = markNotificationReadRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { notificationId } = parsedRequest.data;

		return baseApiService.patch(
			`/api/v1/notifications/${notificationId}/read`,
			markNotificationReadResponse
		);
	};

	/**
	 * Mark all notifications as read
	 */
	markAllAsRead = async (): Promise<MarkAllNotificationsReadResponse> => {
		return baseApiService.patch("/api/v1/notifications/read-all", markAllNotificationsReadResponse);
	};

	/**
	 * Get distinct source types (connector + document types) across all
	 * status notifications. Used to populate the inbox Status tab filter.
	 */
	getSourceTypes = async (searchSpaceId?: number): Promise<GetSourceTypesResponse> => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.append("search_space_id", String(searchSpaceId));
		}
		const queryString = params.toString();

		return baseApiService.get(
			`/api/v1/notifications/source-types${queryString ? `?${queryString}` : ""}`,
			getSourceTypesResponse
		);
	};

	/**
	 * Get unread notification count with split between total and recent
	 * @param searchSpaceId - Optional search space ID to filter by
	 * @param type - Optional notification type to filter by (type-safe enum)
	 * @param category - Optional category filter ('comments' or 'status')
	 */
	getUnreadCount = async (
		searchSpaceId?: number,
		type?: InboxItemTypeEnum,
		category?: NotificationCategory
	): Promise<GetUnreadCountResponse> => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.append("search_space_id", String(searchSpaceId));
		}
		if (type) {
			params.append("type", type);
		}
		if (category) {
			params.append("category", category);
		}
		const queryString = params.toString();

		return baseApiService.get(
			`/api/v1/notifications/unread-count${queryString ? `?${queryString}` : ""}`,
			getUnreadCountResponse
		);
	};

	/**
	 * Get unread counts for all categories in a single request.
	 * Replaces 2 separate getUnreadCount calls (comments + status).
	 */
	getBatchUnreadCounts = async (searchSpaceId?: number): Promise<GetBatchUnreadCountResponse> => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.append("search_space_id", String(searchSpaceId));
		}
		const queryString = params.toString();

		return baseApiService.get(
			`/api/v1/notifications/unread-counts-batch${queryString ? `?${queryString}` : ""}`,
			getBatchUnreadCountResponse
		);
	};
}

export const notificationsApiService = new NotificationsApiService();
