import { z } from "zod";

/**
 * Snapshot info
 */
export const snapshotInfo = z.object({
	id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	created_at: z.string(),
	message_count: z.number(),
});

/**
 * Create snapshot
 */
export const createSnapshotRequest = z.object({
	thread_id: z.number(),
});

export const createSnapshotResponse = z.object({
	snapshot_id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	is_new: z.boolean(),
});

/**
 * List snapshots
 */
export const listSnapshotsRequest = z.object({
	thread_id: z.number(),
});

export const listSnapshotsResponse = z.object({
	snapshots: z.array(snapshotInfo),
});

/**
 * Delete snapshot
 */
export const deleteSnapshotRequest = z.object({
	thread_id: z.number(),
	snapshot_id: z.number(),
});

/**
 * Search space snapshot info (includes thread context)
 */
export const searchSpaceSnapshotInfo = z.object({
	id: z.number(),
	share_token: z.string(),
	public_url: z.string(),
	created_at: z.string(),
	message_count: z.number(),
	thread_id: z.number(),
	thread_title: z.string(),
});

/**
 * List snapshots for search space
 */
export const listSearchSpaceSnapshotsRequest = z.object({
	search_space_id: z.number(),
});

export const listSearchSpaceSnapshotsResponse = z.object({
	snapshots: z.array(searchSpaceSnapshotInfo),
});

// Type exports
export type SnapshotInfo = z.infer<typeof snapshotInfo>;
export type CreateSnapshotRequest = z.infer<typeof createSnapshotRequest>;
export type CreateSnapshotResponse = z.infer<typeof createSnapshotResponse>;
export type ListSnapshotsRequest = z.infer<typeof listSnapshotsRequest>;
export type ListSnapshotsResponse = z.infer<typeof listSnapshotsResponse>;
export type DeleteSnapshotRequest = z.infer<typeof deleteSnapshotRequest>;
export type SearchSpaceSnapshotInfo = z.infer<typeof searchSpaceSnapshotInfo>;
export type ListSearchSpaceSnapshotsRequest = z.infer<typeof listSearchSpaceSnapshotsRequest>;
export type ListSearchSpaceSnapshotsResponse = z.infer<typeof listSearchSpaceSnapshotsResponse>;
