import { z } from "zod";
import { searchSourceConnectorTypeEnum } from "./connector.types";

/**
 * Notification type enum - matches backend notification types
 */
export const notificationTypeEnum = z.enum([
	"connector_indexing",
	"document_processed",
]);

/**
 * Notification status enum - used in metadata
 */
export const notificationStatusEnum = z.enum([
	"in_progress",
	"completed",
	"failed",
]);

/**
 * Base metadata schema shared across notification types
 */
export const baseNotificationMetadata = z.object({
	operation_id: z.string().optional(),
	status: notificationStatusEnum.optional(),
	started_at: z.string().optional(),
	completed_at: z.string().optional(),
});

/**
 * Connector indexing metadata schema
 */
export const connectorIndexingMetadata = baseNotificationMetadata.extend({
	connector_id: z.number(),
	connector_name: z.string(),
	connector_type: searchSourceConnectorTypeEnum,
	start_date: z.string().nullable().optional(),
	end_date: z.string().nullable().optional(),
	indexed_count: z.number(),
	total_count: z.number().optional(),
	progress_percent: z.number().optional(),
	error_message: z.string().nullable().optional(),
	// Google Drive specific fields
	folder_count: z.number().optional(),
	file_count: z.number().optional(),
	folder_names: z.array(z.string()).optional(),
	file_names: z.array(z.string()).optional(),
});

/**
 * Document processed metadata schema
 */
export const documentProcessedMetadata = baseNotificationMetadata.extend({
	document_id: z.number(),
	status: z.string(),
});

/**
 * Union of all notification metadata types
 * Use this when the notification type is unknown
 */
export const notificationMetadata = z.union([
	connectorIndexingMetadata,
	documentProcessedMetadata,
	baseNotificationMetadata,
]);

/**
 * Main notification schema
 */
export const notification = z.object({
	id: z.number(),
	user_id: z.string(),
	search_space_id: z.number().nullable(),
	type: notificationTypeEnum,
	title: z.string(),
	message: z.string(),
	read: z.boolean(),
	metadata: z.record(z.string(), z.unknown()),
	created_at: z.string(),
	updated_at: z.string().nullable(),
});

/**
 * Typed notification schemas for specific notification types
 */
export const connectorIndexingNotification = notification.extend({
	type: z.literal("connector_indexing"),
	metadata: connectorIndexingMetadata,
});

export const documentProcessedNotification = notification.extend({
	type: z.literal("document_processed"),
	metadata: documentProcessedMetadata,
});

// Inferred types
export type NotificationTypeEnum = z.infer<typeof notificationTypeEnum>;
export type NotificationStatusEnum = z.infer<typeof notificationStatusEnum>;
export type BaseNotificationMetadata = z.infer<typeof baseNotificationMetadata>;
export type ConnectorIndexingMetadata = z.infer<typeof connectorIndexingMetadata>;
export type DocumentProcessedMetadata = z.infer<typeof documentProcessedMetadata>;
export type NotificationMetadata = z.infer<typeof notificationMetadata>;
export type Notification = z.infer<typeof notification>;
export type ConnectorIndexingNotification = z.infer<typeof connectorIndexingNotification>;
export type DocumentProcessedNotification = z.infer<typeof documentProcessedNotification>;

