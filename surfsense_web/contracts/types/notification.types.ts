import { z } from "zod";
import { searchSourceConnectorTypeEnum } from "./connector.types";
import { documentTypeEnum } from "./document.types";

/**
 * Notification type enum - matches backend notification types
 */
export const notificationTypeEnum = z.enum([
	"connector_indexing",
	"document_processing",
	"new_mention",
]);

/**
 * Notification status enum - used in metadata
 */
export const notificationStatusEnum = z.enum(["in_progress", "completed", "failed"]);

/**
 * Document processing stage enum
 */
export const documentProcessingStageEnum = z.enum([
	"queued",
	"parsing",
	"chunking",
	"embedding",
	"storing",
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
 * Document processing metadata schema
 */
export const documentProcessingMetadata = baseNotificationMetadata.extend({
	document_type: documentTypeEnum,
	document_name: z.string(),
	processing_stage: documentProcessingStageEnum,
	file_size: z.number().optional(),
	chunks_count: z.number().optional(),
	document_id: z.number().optional(),
	error_message: z.string().nullable().optional(),
});

/**
 * New mention metadata schema
 */
export const newMentionMetadata = z.object({
	mention_id: z.number(),
	comment_id: z.number(),
	message_id: z.number(),
	thread_id: z.number(),
	thread_title: z.string(),
	author_id: z.string(),
	author_name: z.string(),
	content_preview: z.string(),
});

/**
 * Union of all notification metadata types
 * Use this when the notification type is unknown
 */
export const notificationMetadata = z.union([
	connectorIndexingMetadata,
	documentProcessingMetadata,
	newMentionMetadata,
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

export const documentProcessingNotification = notification.extend({
	type: z.literal("document_processing"),
	metadata: documentProcessingMetadata,
});

export const newMentionNotification = notification.extend({
	type: z.literal("new_mention"),
	metadata: newMentionMetadata,
});

// Inferred types
export type NotificationTypeEnum = z.infer<typeof notificationTypeEnum>;
export type NotificationStatusEnum = z.infer<typeof notificationStatusEnum>;
export type DocumentProcessingStageEnum = z.infer<typeof documentProcessingStageEnum>;
export type BaseNotificationMetadata = z.infer<typeof baseNotificationMetadata>;
export type ConnectorIndexingMetadata = z.infer<typeof connectorIndexingMetadata>;
export type DocumentProcessingMetadata = z.infer<typeof documentProcessingMetadata>;
export type NewMentionMetadata = z.infer<typeof newMentionMetadata>;
export type NotificationMetadata = z.infer<typeof notificationMetadata>;
export type Notification = z.infer<typeof notification>;
export type ConnectorIndexingNotification = z.infer<typeof connectorIndexingNotification>;
export type DocumentProcessingNotification = z.infer<typeof documentProcessingNotification>;
export type NewMentionNotification = z.infer<typeof newMentionNotification>;
