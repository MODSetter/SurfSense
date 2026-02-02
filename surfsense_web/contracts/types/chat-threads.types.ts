import { z } from "zod";

/**
 * Public chat snapshot info
 */
export const publicChatSnapshotInfo = z.object({
	id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	created_at: z.string(),
	message_count: z.number(),
});

/**
 * Create public chat snapshot
 */
export const publicChatSnapshotCreateRequest = z.object({
	thread_id: z.number(),
});

export const publicChatSnapshotCreateResponse = z.object({
	snapshot_id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	is_new: z.boolean(),
});

/**
 * List public chat snapshots for thread
 */
export const publicChatSnapshotListRequest = z.object({
	thread_id: z.number(),
});

export const publicChatSnapshotListResponse = z.object({
	snapshots: z.array(publicChatSnapshotInfo),
});

/**
 * Delete public chat snapshot
 */
export const publicChatSnapshotDeleteRequest = z.object({
	thread_id: z.number(),
	snapshot_id: z.number(),
});

/**
 * Public chat snapshot with thread context
 */
export const publicChatSnapshotDetail = z.object({
	id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	created_at: z.string(),
	message_count: z.number(),
	thread_id: z.number(),
	thread_title: z.string(),
});

/**
 * List public chat snapshots for search space
 */
export const publicChatSnapshotsBySpaceRequest = z.object({
	search_space_id: z.number(),
});

export const publicChatSnapshotsBySpaceResponse = z.object({
	snapshots: z.array(publicChatSnapshotDetail),
});

// Type exports
export type PublicChatSnapshotInfo = z.infer<typeof publicChatSnapshotInfo>;
export type PublicChatSnapshotCreateRequest = z.infer<typeof publicChatSnapshotCreateRequest>;
export type PublicChatSnapshotCreateResponse = z.infer<typeof publicChatSnapshotCreateResponse>;
export type PublicChatSnapshotListRequest = z.infer<typeof publicChatSnapshotListRequest>;
export type PublicChatSnapshotListResponse = z.infer<typeof publicChatSnapshotListResponse>;
export type PublicChatSnapshotDeleteRequest = z.infer<typeof publicChatSnapshotDeleteRequest>;
export type PublicChatSnapshotDetail = z.infer<typeof publicChatSnapshotDetail>;
export type PublicChatSnapshotsBySpaceRequest = z.infer<typeof publicChatSnapshotsBySpaceRequest>;
export type PublicChatSnapshotsBySpaceResponse = z.infer<typeof publicChatSnapshotsBySpaceResponse>;
