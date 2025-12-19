import type { Message } from "@ai-sdk/react";
import { z } from "zod";
import { paginationQueryParams } from ".";

export const chatTypeEnum = z.enum(["QNA"]);

export const chatSummary = z.object({
	created_at: z.string(),
	id: z.number(),
	type: chatTypeEnum,
	title: z.string(),
	search_space_id: z.number(),
	state_version: z.number(),
});

export const chatDetails = chatSummary.extend({
	initial_connectors: z.array(z.string()).nullable().optional(),
	messages: z.array(z.any()),
});

export const getChatDetailsRequest = chatSummary.pick({ id: true });

export const getChatsRequest = z.object({
	queryParams: paginationQueryParams
		.extend({
			search_space_id: z.number().or(z.string()).optional(),
		})
		.nullish(),
});

export const deleteChatResponse = z.object({
	message: z.literal("Chat deleted successfully"),
});

export const deleteChatRequest = chatSummary.pick({ id: true });

export const createChatRequest = chatDetails.omit({
	created_at: true,
	id: true,
	state_version: true,
});

export const updateChatRequest = chatDetails.omit({
	created_at: true,
	state_version: true,
});

export type ChatSummary = z.infer<typeof chatSummary>;
export type ChatDetails = z.infer<typeof chatDetails> & { messages: Message[] };
export type GetChatDetailsRequest = z.infer<typeof getChatDetailsRequest>;
export type GetChatsRequest = z.infer<typeof getChatsRequest>;
export type DeleteChatResponse = z.infer<typeof deleteChatResponse>;
export type DeleteChatRequest = z.infer<typeof deleteChatRequest>;
export type CreateChatRequest = z.infer<typeof createChatRequest>;
export type UpdateChatRequest = z.infer<typeof updateChatRequest>;
