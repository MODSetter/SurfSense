import { z } from "zod";

export const author = z.object({
	id: z.string().uuid(),
	display_name: z.string().nullable(),
	avatar_url: z.string().nullable(),
	email: z.string(),
});

export const commentReply = z.object({
	id: z.number(),
	content: z.string(),
	content_rendered: z.string(),
	author: author.nullable(),
	created_at: z.string(),
	updated_at: z.string(),
	is_edited: z.boolean(),
	can_edit: z.boolean(),
	can_delete: z.boolean(),
});

export const comment = z.object({
	id: z.number(),
	message_id: z.number(),
	content: z.string(),
	content_rendered: z.string(),
	author: author.nullable(),
	created_at: z.string(),
	updated_at: z.string(),
	is_edited: z.boolean(),
	can_edit: z.boolean(),
	can_delete: z.boolean(),
	reply_count: z.number(),
	replies: z.array(commentReply),
});

export const mentionContext = z.object({
	thread_id: z.number(),
	thread_title: z.string(),
	message_id: z.number(),
	search_space_id: z.number(),
	search_space_name: z.string(),
});

export const mentionComment = z.object({
	id: z.number(),
	content_preview: z.string(),
	author: author.nullable(),
	created_at: z.string(),
});

export const mention = z.object({
	id: z.number(),
	read: z.boolean(),
	created_at: z.string(),
	comment: mentionComment,
	context: mentionContext,
});

/**
 * Get comments for a message
 */
export const getCommentsRequest = z.object({
	message_id: z.number(),
});

export const getCommentsResponse = z.object({
	comments: z.array(comment),
	total_count: z.number(),
});

/**
 * Create comment
 */
export const createCommentRequest = z.object({
	message_id: z.number(),
	content: z.string().min(1).max(5000),
});

export const createCommentResponse = comment;

/**
 * Create reply
 */
export const createReplyRequest = z.object({
	comment_id: z.number(),
	content: z.string().min(1).max(5000),
});

export const createReplyResponse = commentReply;

/**
 * Update comment
 */
export const updateCommentRequest = z.object({
	comment_id: z.number(),
	content: z.string().min(1).max(5000),
});

export const updateCommentResponse = commentReply;

/**
 * Delete comment
 */
export const deleteCommentRequest = z.object({
	comment_id: z.number(),
});

export const deleteCommentResponse = z.object({
	message: z.string(),
	comment_id: z.number(),
});

/**
 * Get mentions
 */
export const getMentionsRequest = z.object({
	search_space_id: z.number().optional(),
	unread_only: z.boolean().optional(),
});

export const getMentionsResponse = z.object({
	mentions: z.array(mention),
	unread_count: z.number(),
});

/**
 * Mark mention as read
 */
export const markMentionReadRequest = z.object({
	mention_id: z.number(),
});

export const markMentionReadResponse = z.object({
	mention_id: z.number(),
	read: z.boolean(),
});

/**
 * Mark all mentions as read
 */
export const markAllMentionsReadResponse = z.object({
	message: z.string(),
	count: z.number(),
});

export type Author = z.infer<typeof author>;
export type CommentReply = z.infer<typeof commentReply>;
export type Comment = z.infer<typeof comment>;
export type MentionContext = z.infer<typeof mentionContext>;
export type MentionComment = z.infer<typeof mentionComment>;
export type Mention = z.infer<typeof mention>;
export type GetCommentsRequest = z.infer<typeof getCommentsRequest>;
export type GetCommentsResponse = z.infer<typeof getCommentsResponse>;
export type CreateCommentRequest = z.infer<typeof createCommentRequest>;
export type CreateCommentResponse = z.infer<typeof createCommentResponse>;
export type CreateReplyRequest = z.infer<typeof createReplyRequest>;
export type CreateReplyResponse = z.infer<typeof createReplyResponse>;
export type UpdateCommentRequest = z.infer<typeof updateCommentRequest>;
export type UpdateCommentResponse = z.infer<typeof updateCommentResponse>;
export type DeleteCommentRequest = z.infer<typeof deleteCommentRequest>;
export type DeleteCommentResponse = z.infer<typeof deleteCommentResponse>;
export type GetMentionsRequest = z.infer<typeof getMentionsRequest>;
export type GetMentionsResponse = z.infer<typeof getMentionsResponse>;
export type MarkMentionReadRequest = z.infer<typeof markMentionReadRequest>;
export type MarkMentionReadResponse = z.infer<typeof markMentionReadResponse>;
export type MarkAllMentionsReadResponse = z.infer<typeof markAllMentionsReadResponse>;
