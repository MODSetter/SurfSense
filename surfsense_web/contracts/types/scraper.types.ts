import { z } from "zod";

/**
 * A platform-native scraper verb and its input/output JSON schemas. Both are
 * arbitrary JSON Schema (pydantic ``model_json_schema()``): the input schema is
 * consumed by the playground's generic form renderer, the output schema by the
 * API reference docs — so they are intentionally untyped here.
 */
/** One live per-item rate a verb charges on, e.g. 3500 micro-USD per place. */
export const scraperPricingMeter = z.object({
	unit: z.string(),
	micros_per_unit: z.number(),
});

export const scraperCapability = z.object({
	name: z.string(),
	description: z.string(),
	input_schema: z.record(z.string(), z.unknown()),
	// Optional so a backend that predates output schemas degrades to just not
	// showing the output-schema block instead of failing the whole fetch.
	output_schema: z.record(z.string(), z.unknown()).optional(),
	// Optional for the same backward-compat reason; empty array = free.
	pricing: z.array(scraperPricingMeter).optional(),
});

export const listCapabilitiesResponse = z.array(scraperCapability);

/**
 * Run origin: ``ui`` (in-app), ``api`` (PAT/public API), ``agent`` (chat tools).
 */
export const scraperRunSummary = z.object({
	id: z.string(),
	capability: z.string(),
	origin: z.string(),
	status: z.string(),
	item_count: z.number(),
	char_count: z.number(),
	duration_ms: z.number().nullable(),
	cost_micros: z.number().nullable(),
	error: z.string().nullable(),
	created_at: z.string(),
});

export const scraperRunDetail = scraperRunSummary.extend({
	thread_id: z.string().nullable(),
	input: z.record(z.string(), z.unknown()).nullable(),
	output_text: z.string().nullable(),
	// Coarse progress log captured during the run (nullable/absent for older or
	// zero-progress runs). Each entry is a ``run.progress`` event object.
	progress: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
});

export const listRunsResponse = z.array(scraperRunSummary);

/** Response of an async run start (``POST ...?mode=async`` -> 202). */
export const startAsyncRunResponse = z.object({
	run_id: z.string(),
	status: z.string(),
});

export type ScraperPricingMeter = z.infer<typeof scraperPricingMeter>;
export type ScraperCapability = z.infer<typeof scraperCapability>;
export type ScraperRunSummary = z.infer<typeof scraperRunSummary>;
export type ScraperRunDetail = z.infer<typeof scraperRunDetail>;
export type StartAsyncRunResponse = z.infer<typeof startAsyncRunResponse>;

export interface ListScraperRunsParams {
	limit?: number;
	offset?: number;
	capability?: string;
	status?: string;
}

/**
 * A live progress event streamed from ``GET .../runs/{run_id}/events`` (SSE).
 * One flexible shape mirrors the backend: lifecycle events (``run.started`` /
 * ``run.finished`` / ``run.heartbeat``) and fine-grained ``run.progress``.
 */
export interface ScraperRunEvent {
	type: string;
	ts?: number;
	run_id?: string;
	status?: string;
	capability?: string;
	phase?: string;
	message?: string;
	current?: number;
	total?: number;
	unit?: string;
	item_count?: number;
	error?: string | null;
	detail?: Record<string, unknown>;
}
