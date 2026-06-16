import { z } from "zod";

// =============================================================================
// Lifecycle — mirror app/podcasts/persistence/enums/podcast_status.py
// =============================================================================

export const podcastStatus = z.enum([
	"pending",
	"awaiting_brief",
	"drafting",
	"awaiting_review",
	"rendering",
	"ready",
	"failed",
	"cancelled",
]);
export type PodcastStatus = z.infer<typeof podcastStatus>;

/**
 * States waiting on user input before the lifecycle can proceed. The brief is
 * the only approval gate; `awaiting_review` survives in the enum for legacy
 * rows but is never entered anymore.
 */
export const GATE_STATUSES: ReadonlySet<PodcastStatus> = new Set(["awaiting_brief"]);

/**
 * States from which no further transition is possible. A `ready` episode is
 * not terminal: it can be sent back to drafting for regeneration.
 */
export const TERMINAL_STATUSES: ReadonlySet<PodcastStatus> = new Set(["failed", "cancelled"]);

// =============================================================================
// Brief (spec) — mirror app/podcasts/schemas/spec.py
// =============================================================================

export const speakerRole = z.enum(["host", "cohost", "guest", "expert", "narrator"]);
export type SpeakerRole = z.infer<typeof speakerRole>;

export const podcastStyle = z.enum([
	"conversational",
	"interview",
	"debate",
	"monologue",
	"narrative",
]);
export type PodcastStyle = z.infer<typeof podcastStyle>;

export const MAX_SPEAKERS = 6;

export const MAX_DURATION_SECONDS = 24 * 60 * 60;
export const MIN_DURATION_SECONDS = 15;
export const DEFAULT_MIN_SECONDS = 20;
export const DEFAULT_MAX_SECONDS = 30;

export const speakerSpec = z.object({
	slot: z.number().int().min(0),
	name: z.string().min(1).max(120),
	role: speakerRole,
	voice_id: z.string().min(1),
});
export type SpeakerSpec = z.infer<typeof speakerSpec>;

export const durationTarget = z.preprocess(
	(raw) => {
		if (
			raw &&
			typeof raw === "object" &&
			"min_minutes" in raw &&
			!("min_seconds" in raw)
		) {
			const legacy = raw as { min_minutes: number; max_minutes: number };
			return {
				min_seconds: legacy.min_minutes * 60,
				max_seconds: legacy.max_minutes * 60,
			};
		}
		return raw;
	},
	z
		.object({
			min_seconds: z
				.number()
				.int()
				.min(MIN_DURATION_SECONDS)
				.max(MAX_DURATION_SECONDS),
			max_seconds: z
				.number()
				.int()
				.min(MIN_DURATION_SECONDS)
				.max(MAX_DURATION_SECONDS),
		})
		.refine((duration) => duration.max_seconds >= duration.min_seconds, {
			message: "Max length must be at least min length",
			path: ["max_seconds"],
		}),
);
export type DurationTarget = z.infer<typeof durationTarget>;

export const podcastSpec = z
	.object({
		language: z.string().min(2),
		style: podcastStyle,
		speakers: z.array(speakerSpec).min(1).max(MAX_SPEAKERS),
		duration: durationTarget,
		focus: z.string().max(2000).nullable().optional(),
	})
	// Mirrors the backend invariant: one voice is what "monologue" means.
	.refine((spec) => spec.style !== "monologue" || spec.speakers.length === 1, {
		message: "A monologue has exactly one speaker",
		path: ["speakers"],
	});
export type PodcastSpec = z.infer<typeof podcastSpec>;

// =============================================================================
// Transcript — mirror app/podcasts/schemas/transcript.py
// =============================================================================

export const transcriptTurn = z.object({
	speaker: z.number().int().min(0),
	text: z.string().min(1),
});
export type TranscriptTurn = z.infer<typeof transcriptTurn>;

export const transcript = z.object({
	turns: z.array(transcriptTurn).min(1),
});
export type Transcript = z.infer<typeof transcript>;

// =============================================================================
// API shapes — mirror app/podcasts/api/schemas.py
// =============================================================================

export const voiceOption = z.object({
	voice_id: z.string(),
	display_name: z.string(),
	language: z.string(),
	gender: z.string(),
});
export type VoiceOption = z.infer<typeof voiceOption>;

export const updateSpecRequest = z.object({
	spec: podcastSpec,
	expected_version: z.number().int().min(1),
});
export type UpdateSpecRequest = z.infer<typeof updateSpecRequest>;

export const podcastDetail = z.object({
	id: z.number(),
	title: z.string(),
	status: podcastStatus,
	spec_version: z.number(),
	spec: podcastSpec.nullable(),
	transcript: transcript.nullable(),
	has_audio: z.boolean(),
	duration_seconds: z.number().nullable(),
	error: z.string().nullable(),
	created_at: z.string(),
	search_space_id: z.number(),
	thread_id: z.number().nullable(),
});
export type PodcastDetail = z.infer<typeof podcastDetail>;
