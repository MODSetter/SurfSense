import { z } from "zod";

export const podcast = z.object({
	id: z.number(),
	title: z.string(),
	created_at: z.string(),
	file_location: z.string(),
	podcast_transcript: z.array(z.any()),
	search_space_id: z.number(),
	chat_state_version: z.number().nullable(),
});

export const generatePodcastRequest = z.object({
	type: z.enum(["CHAT", "DOCUMENT"]),
	ids: z.array(z.number()),
	search_space_id: z.number(),
	podcast_title: z.string().optional(),
	user_prompt: z.string().optional(),
});

export const getPodcastByChatIdRequest = z.object({
	chat_id: z.number(),
});

export type GeneratePodcastRequest = z.infer<typeof generatePodcastRequest>;
export type GetPodcastByChatIdRequest = z.infer<typeof getPodcastByChatIdRequest>;
export type Podcast = z.infer<typeof podcast>;
