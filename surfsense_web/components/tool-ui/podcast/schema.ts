import { z } from "zod";
import type { PodcastSpec } from "@/contracts/types/podcast.types";

/**
 * Tool-call contract for `generate_podcast`.
 *
 * The tool prepares a podcast and returns immediately with the row awaiting
 * brief review; the card then follows the lifecycle by push. Legacy status
 * values are accepted so old saved chats still render something sensible.
 */

export const generatePodcastArgsSchema = z.object({
	source_content: z.string(),
	podcast_title: z.string().nullish(),
	user_prompt: z.string().nullish(),
});
export type GeneratePodcastArgs = z.infer<typeof generatePodcastArgsSchema>;

export const generatePodcastResultSchema = z.object({
	status: z.string(),
	podcast_id: z.number().nullish(),
	task_id: z.string().nullish(), // legacy Celery id from old saved chats
	title: z.string().nullish(),
	message: z.string().nullish(),
	error: z.string().nullish(),
});
export type GeneratePodcastResult = z.infer<typeof generatePodcastResultSchema>;

/** Display name for the speaker bound to `slot`, falling back to a number. */
export function speakerLabel(spec: PodcastSpec | null | undefined, slot: number): string {
	const speaker = spec?.speakers.find((s) => s.slot === slot);
	return speaker?.name ?? `Speaker ${slot + 1}`;
}
