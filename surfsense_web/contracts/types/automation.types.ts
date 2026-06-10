import { z } from "zod";

// =============================================================================
// Enums — mirror app/automations/persistence/enums/*
// =============================================================================

export const automationStatus = z.enum(["active", "paused", "archived"]);
export type AutomationStatus = z.infer<typeof automationStatus>;

export const triggerType = z.enum(["schedule", "manual", "event"]);
export type TriggerType = z.infer<typeof triggerType>;

export const runStatus = z.enum([
	"pending",
	"running",
	"succeeded",
	"failed",
	"cancelled",
	"timed_out",
]);
export type RunStatus = z.infer<typeof runStatus>;

// =============================================================================
// Definition envelope — mirror app/automations/schemas/definition/*
// =============================================================================

export const planStep = z.object({
	step_id: z.string().min(1),
	action: z.string().min(1),
	when: z.string().nullable().optional(),
	params: z.record(z.string(), z.any()).default({}),
	output_as: z.string().nullable().optional(),
	max_retries: z.number().int().min(0).nullable().optional(),
	timeout_seconds: z.number().int().positive().nullable().optional(),
});
export type PlanStep = z.infer<typeof planStep>;

export const definitionTriggerSpec = z.object({
	type: z.string().min(1),
	params: z.record(z.string(), z.any()).default({}),
});
export type DefinitionTriggerSpec = z.infer<typeof definitionTriggerSpec>;

export const execution = z.object({
	timeout_seconds: z.number().int().positive().default(600),
	max_retries: z.number().int().min(0).default(2),
	retry_backoff: z.enum(["exponential", "linear", "none"]).default("exponential"),
	concurrency: z.enum(["drop_if_running", "queue", "always"]).default("drop_if_running"),
	on_failure: z.array(planStep).default([]),
});
export type Execution = z.infer<typeof execution>;

// Backend ``Metadata`` is ``extra="allow"`` — keep ``tags`` typed, accept arbitrary keys.
export const metadata = z.object({ tags: z.array(z.string()).default([]) }).catchall(z.any());
export type Metadata = z.infer<typeof metadata>;

// Backend ``Inputs`` serializes its ``schema_`` field as ``schema`` (alias).
export const inputs = z.object({
	schema: z.record(z.string(), z.any()),
});
export type Inputs = z.infer<typeof inputs>;

// Captured model snapshot (server-managed). Set at create time and preserved
// across edits so runs are insulated from later chat/search-space model changes.
export const automationModels = z.object({
	chat_model_id: z.number().int().default(0),
	image_gen_model_id: z.number().int().default(0),
	vision_model_id: z.number().int().default(0),
});
export type AutomationModels = z.infer<typeof automationModels>;

export const automationDefinition = z.object({
	schema_version: z.string().default("1.0"),
	name: z.string().min(1).max(200),
	goal: z.string().nullable().optional(),
	inputs: inputs.nullable().optional(),
	triggers: z.array(definitionTriggerSpec).default([]),
	plan: z.array(planStep).min(1),
	execution: execution.default(execution.parse({})),
	metadata: metadata.default(metadata.parse({})),
	models: automationModels.nullable().optional(),
});
export type AutomationDefinition = z.infer<typeof automationDefinition>;

// =============================================================================
// Triggers (sub-resource) — mirror app/automations/schemas/api/trigger.py
// =============================================================================

export const triggerCreateRequest = z.object({
	type: triggerType,
	params: z.record(z.string(), z.any()).default({}),
	static_inputs: z.record(z.string(), z.any()).default({}),
	enabled: z.boolean().default(true),
});
export type TriggerCreateRequest = z.infer<typeof triggerCreateRequest>;

export const triggerUpdateRequest = z.object({
	enabled: z.boolean().nullable().optional(),
	params: z.record(z.string(), z.any()).nullable().optional(),
	static_inputs: z.record(z.string(), z.any()).nullable().optional(),
});
export type TriggerUpdateRequest = z.infer<typeof triggerUpdateRequest>;

export const trigger = z.object({
	id: z.number(),
	type: triggerType,
	params: z.record(z.string(), z.any()),
	static_inputs: z.record(z.string(), z.any()),
	enabled: z.boolean(),
	last_fired_at: z.string().nullable().optional(),
	next_fire_at: z.string().nullable().optional(),
	created_at: z.string(),
});
export type Trigger = z.infer<typeof trigger>;

// =============================================================================
// Automations — mirror app/automations/schemas/api/automation.py
// =============================================================================

export const automationCreateRequest = z.object({
	search_space_id: z.number(),
	name: z.string().min(1).max(200),
	description: z.string().nullable().optional(),
	definition: automationDefinition,
	triggers: z.array(triggerCreateRequest).default([]),
});
export type AutomationCreateRequest = z.infer<typeof automationCreateRequest>;

export const automationUpdateRequest = z.object({
	name: z.string().min(1).max(200).nullable().optional(),
	description: z.string().nullable().optional(),
	status: automationStatus.nullable().optional(),
	definition: automationDefinition.nullable().optional(),
});
export type AutomationUpdateRequest = z.infer<typeof automationUpdateRequest>;

export const automationSummary = z.object({
	id: z.number(),
	search_space_id: z.number(),
	name: z.string(),
	description: z.string().nullable().optional(),
	status: automationStatus,
	version: z.number(),
	created_at: z.string(),
	updated_at: z.string(),
});
export type AutomationSummary = z.infer<typeof automationSummary>;

export const automation = automationSummary.extend({
	definition: automationDefinition,
	triggers: z.array(trigger).default([]),
});
export type Automation = z.infer<typeof automation>;

export const automationListResponse = z.object({
	items: z.array(automationSummary),
	total: z.number(),
});
export type AutomationListResponse = z.infer<typeof automationListResponse>;

export const automationListParams = z.object({
	search_space_id: z.number(),
	limit: z.number().int().min(1).max(200).default(50),
	offset: z.number().int().min(0).default(0),
});
export type AutomationListParams = z.infer<typeof automationListParams>;

// =============================================================================
// Runs (sub-resource) — mirror app/automations/schemas/api/run.py
// =============================================================================

export const runSummary = z.object({
	id: z.number(),
	automation_id: z.number(),
	trigger_id: z.number().nullable().optional(),
	status: runStatus,
	started_at: z.string().nullable().optional(),
	finished_at: z.string().nullable().optional(),
	created_at: z.string(),
});
export type RunSummary = z.infer<typeof runSummary>;

export const run = runSummary.extend({
	definition_snapshot: z.record(z.string(), z.any()),
	inputs: z.record(z.string(), z.any()),
	step_results: z.array(z.record(z.string(), z.any())),
	output: z.record(z.string(), z.any()).nullable().optional(),
	artifacts: z.array(z.record(z.string(), z.any())),
	error: z.record(z.string(), z.any()).nullable().optional(),
});
export type Run = z.infer<typeof run>;

/**
 * Typed view over a single entry in {@link Run.step_results}. The Zod schema
 * keeps step results as opaque records (the backend emits action-specific
 * payloads), so this interface exists purely for safe field access in the UI
 * and does not perform runtime validation.
 *
 * Mirrors `_result()` in
 * `surfsense_backend/app/automations/runtime/step.py`. For the `agent_task`
 * action, `result` carries the markdown `final_message` produced by the agent.
 */
export interface RunStepResult {
	step_id: string;
	action: string;
	status: "succeeded" | "failed" | "skipped" | string;
	started_at?: string;
	finished_at?: string;
	attempts?: number;
	result?: {
		final_message?: string;
		agent_session_id?: string;
		resumes?: unknown;
	} & Record<string, unknown>;
	error?: { message?: string; type?: string };
}

export const runListResponse = z.object({
	items: z.array(runSummary),
	total: z.number(),
});
export type RunListResponse = z.infer<typeof runListResponse>;

export const runListParams = z.object({
	limit: z.number().int().min(1).max(200).default(50),
	offset: z.number().int().min(0).default(0),
});
export type RunListParams = z.infer<typeof runListParams>;

// =============================================================================
// Model eligibility — mirror app/automations/api/automation.py (ModelEligibility)
// =============================================================================

export const modelEligibilityKind = z.enum(["llm", "image", "vision"]);
export type ModelEligibilityKind = z.infer<typeof modelEligibilityKind>;

export const modelEligibilityViolation = z.object({
	kind: modelEligibilityKind,
	config_id: z.number().nullable(),
	reason: z.string(),
});
export type ModelEligibilityViolation = z.infer<typeof modelEligibilityViolation>;

export const modelEligibility = z.object({
	allowed: z.boolean(),
	violations: z.array(modelEligibilityViolation),
});
export type ModelEligibility = z.infer<typeof modelEligibility>;
