import { z } from "zod";
import { paginationQueryParams } from ".";

export const podcastTranscriptEntry = z.object({
	speaker_id: z.number(),
	dialog: z.string(),
});

export const podcast = z.object({
	id: z.number(),
	title: z.string(),
	created_at: z.string(),
	file_location: z.string(),
	podcast_transcript: z.array(podcastTranscriptEntry),
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

export const getPodcastByChaIdResponse = podcast.nullish();

export const deletePodcastRequest = z.object({
	id: z.number(),
});

export const deletePodcastResponse = z.object({
	message: z.literal("Podcast deleted successfully"),
});

export const loadPodcastRequest = z.object({
	id: z.number(),
});

export const getPodcastsRequest = z.object({
	queryParams: paginationQueryParams.nullish(),
});

export type PodcastTranscriptEntry = z.infer<typeof podcastTranscriptEntry>;
export type GeneratePodcastRequest = z.infer<typeof generatePodcastRequest>;
export type GetPodcastByChatIdRequest = z.infer<typeof getPodcastByChatIdRequest>;
export type GetPodcastByChatIdResponse = z.infer<typeof getPodcastByChaIdResponse>;
export type DeletePodcastRequest = z.infer<typeof deletePodcastRequest>;
export type DeletePodcastResponse = z.infer<typeof deletePodcastResponse>;
export type LoadPodcastRequest = z.infer<typeof loadPodcastRequest>;
export type Podcast = z.infer<typeof podcast>;
export type GetPodcastsRequest = z.infer<typeof getPodcastsRequest>;
