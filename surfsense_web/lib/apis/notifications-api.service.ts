import {
	type GetNotificationsRequest,
	type GetNotificationsResponse,
	type GetUnreadCountResponse,
	getNotificationsRequest,
	getNotificationsResponse,
	getUnreadCountResponse,
	type InboxItemTypeEnum,
	type MarkAllNotificationsReadResponse,
	type MarkNotificationReadRequest,
	type MarkNotificationReadResponse,
	markAllNotificationsReadResponse,
	markNotificationReadRequest,
	markNotificationReadResponse,
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
		if (queryParams.before_date) {
			params.append("before_date", queryParams.before_date);
		}
		if (queryParams.limit !== undefined) {
			params.append("limit", String(queryParams.limit));
		}
		if (queryParams.offset !== undefined) {
			params.append("offset", String(queryParams.offset));
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
	 * Get unread notification count with split between total and recent
	 * - total_unread: All unread notifications
	 * - recent_unread: Unread within sync window (last 14 days)
	 * @param searchSpaceId - Optional search space ID to filter by
	 * @param type - Optional notification type to filter by (type-safe enum)
	 */
	getUnreadCount = async (
		searchSpaceId?: number,
		type?: InboxItemTypeEnum
	): Promise<GetUnreadCountResponse> => {
		const params = new URLSearchParams();
		if (searchSpaceId !== undefined) {
			params.append("search_space_id", String(searchSpaceId));
		}
		if (type) {
			params.append("type", type);
		}
		const queryString = params.toString();

		return baseApiService.get(
			`/api/v1/notifications/unread-count${queryString ? `?${queryString}` : ""}`,
			getUnreadCountResponse
		);
	};
}

export const notificationsApiService = new NotificationsApiService();
