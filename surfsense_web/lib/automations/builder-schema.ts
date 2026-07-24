/**
 * The form builder's own data model plus the mappers that bridge it to the
 * backend contract (``automation.types.ts``).
 *
 * The builder deliberately exposes a *subset* of the full automation
 * definition: a name, one or more natural-language agent tasks, a single
 * schedule, and a few execution knobs. Anything richer (goal, per-step
 * ``when`` predicates, ``inputs`` schema, ``on_failure`` steps, multiple or
 * non-schedule triggers, custom metadata) is not representable here, so on
 * edit we detect it and bounce the user to raw-JSON mode rather than silently
 * dropping their data. ``goal`` is the one exception: it is carried through
 * invisibly so the common drafter-produced automation stays form-editable.
 */

import { z } from "zod";
import type { MentionedDocumentInfo } from "@/atoms/chat/mentioned-documents.atom";
import {
	type Automation,
	type AutomationCreateRequest,
	type AutomationDefinition,
	type AutomationUpdateRequest,
	execution as executionContract,
	type TriggerCreateRequest,
} from "@/contracts/types/automation.types";
import { DEFAULT_SCHEDULE, fromCron, type ScheduleModel, toCron } from "./schedule-builder";

const EXECUTION_DEFAULTS = executionContract.parse({});

// ---------------------------------------------------------------------------
// Form model
// ---------------------------------------------------------------------------

export const builderTaskSchema = z.object({
	/** Client-side identity for stable React keys across reorder; not persisted. */
	id: z.string(),
	query: z.string().trim().min(1, "Describe what the agent should do"),
	/**
	 * Files / folders / connectors @-mentioned in the query. Mirrors the chat
	 * composer's mention list and is forwarded to the run as step params so the
	 * agent scopes retrieval to them. The query text already carries ``@Title``
	 * for each; this is the structured side-channel of IDs.
	 */
	mentions: z.array(z.custom<MentionedDocumentInfo>()),
	maxRetries: z.number().int().min(0).max(10).nullable(),
	timeoutSeconds: z.number().int().positive().max(86_400).nullable(),
});
export type BuilderTask = z.infer<typeof builderTaskSchema>;

export const builderScheduleSchema = z.discriminatedUnion("mode", [
	z.object({
		mode: z.literal("preset"),
		model: z.custom<ScheduleModel>(),
	}),
	z.object({
		mode: z.literal("cron"),
		cron: z.string().trim().min(1, "Enter a schedule expression"),
	}),
]);
export type BuilderSchedule = z.infer<typeof builderScheduleSchema>;

export const builderExecutionSchema = z.object({
	timeoutSeconds: z.number().int().positive().max(86_400),
	maxRetries: z.number().int().min(0).max(10),
	retryBackoff: z.enum(["exponential", "linear", "none"]),
	concurrency: z.enum(["drop_if_running", "queue", "always"]),
});
export type BuilderExecution = z.infer<typeof builderExecutionSchema>;

/**
 * Per-automation model selection. ``0`` means "unset" — the builder resolves it
 * to the eligible default during render, and the resolved (non-zero) ids are
 * written onto ``definition.models`` at submit so the run is insulated from
 * later chat/workspace model changes.
 */
export const builderModelsSchema = z.object({
	chatModelId: z.number().int(),
	imageConfigId: z.number().int(),
	visionConfigId: z.number().int(),
});
export type BuilderModels = z.infer<typeof builderModelsSchema>;

export const builderFormSchema = z.object({
	name: z.string().trim().min(1, "Give your automation a name").max(200),
	description: z.string().trim().max(2000).nullable(),
	tasks: z.array(builderTaskSchema).min(1, "Add at least one task"),
	unattended: z.boolean(),
	schedule: builderScheduleSchema.nullable(),
	timezone: z.string().min(1),
	execution: builderExecutionSchema,
	tags: z.array(z.string()),
	/** Carried through from an edited definition so we don't drop it. */
	goal: z.string().nullable(),
	/** Selected chat/image/vision models (``0`` = use the eligible default). */
	models: builderModelsSchema,
});
export type BuilderForm = z.infer<typeof builderFormSchema>;

// ---------------------------------------------------------------------------
// Defaults / construction
// ---------------------------------------------------------------------------

export function getDefaultTimezone(): string {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
	} catch {
		return "UTC";
	}
}

export function getTimezones(): string[] {
	try {
		const supported = (
			Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
		).supportedValuesOf?.("timeZone");
		if (supported && supported.length > 0) return supported;
	} catch {
		// fall through
	}
	return ["UTC", getDefaultTimezone()];
}

function newId(): string {
	try {
		return crypto.randomUUID();
	} catch {
		return `task_${Math.random().toString(36).slice(2)}`;
	}
}

export function emptyTask(): BuilderTask {
	return { id: newId(), query: "", mentions: [], maxRetries: null, timeoutSeconds: null };
}

export function createEmptyForm(): BuilderForm {
	return {
		name: "",
		description: null,
		tasks: [emptyTask()],
		unattended: true,
		schedule: { mode: "preset", model: { ...DEFAULT_SCHEDULE } },
		timezone: getDefaultTimezone(),
		execution: {
			timeoutSeconds: EXECUTION_DEFAULTS.timeout_seconds,
			maxRetries: EXECUTION_DEFAULTS.max_retries,
			retryBackoff: EXECUTION_DEFAULTS.retry_backoff,
			concurrency: EXECUTION_DEFAULTS.concurrency,
		},
		tags: [],
		goal: null,
		models: { chatModelId: 0, imageConfigId: 0, visionConfigId: 0 },
	};
}

/** The cron string a schedule resolves to, regardless of preset/raw mode. */
export function scheduleToCron(schedule: BuilderSchedule): string {
	return schedule.mode === "preset" ? toCron(schedule.model) : schedule.cron.trim();
}

// ---------------------------------------------------------------------------
// Form -> contract payloads
// ---------------------------------------------------------------------------

/**
 * Project a task's @-mentions into the ``agent_task`` param fields the backend
 * understands (the same names the chat ``new_chat`` request uses, minus
 * SurfSense docs). Returns an empty object when there are no mentions so the
 * params stay clean.
 *
 * ``mentioned_documents`` carries doc/folder chip metadata (so the run can
 * resolve titles to paths); connectors live only in ``mentioned_connectors`` /
 * ``mentioned_connector_ids`` to avoid duplicating them across buckets.
 */
function mentionParams(mentions: MentionedDocumentInfo[]): Record<string, unknown> {
	if (mentions.length === 0) return {};
	const documentIds: number[] = [];
	const folderIds: number[] = [];
	const connectorIds: number[] = [];
	const documents: MentionedDocumentInfo[] = [];
	const connectors: MentionedDocumentInfo[] = [];
	for (const mention of mentions) {
		if (mention.kind === "folder") {
			folderIds.push(mention.id);
			documents.push(mention);
		} else if (mention.kind === "connector") {
			connectorIds.push(mention.id);
			connectors.push(mention);
		} else {
			documentIds.push(mention.id);
			documents.push(mention);
		}
	}
	const out: Record<string, unknown> = {};
	if (documents.length > 0) out.mentioned_documents = documents;
	if (documentIds.length > 0) out.mentioned_document_ids = documentIds;
	if (folderIds.length > 0) out.mentioned_folder_ids = folderIds;
	if (connectorIds.length > 0) {
		out.mentioned_connector_ids = connectorIds;
		out.mentioned_connectors = connectors;
	}
	return out;
}

function buildPlan(form: BuilderForm) {
	return form.tasks.map((task, index) => {
		const step: Record<string, unknown> = {
			step_id: `step_${index + 1}`,
			action: "agent_task",
			params: {
				query: task.query.trim(),
				auto_approve_all: form.unattended,
				...mentionParams(task.mentions),
			},
		};
		if (task.maxRetries !== null) step.max_retries = task.maxRetries;
		if (task.timeoutSeconds !== null) step.timeout_seconds = task.timeoutSeconds;
		return step;
	});
}

function buildDefinition(form: BuilderForm): AutomationDefinition {
	return {
		schema_version: "1.0",
		name: form.name.trim(),
		goal: form.goal,
		// Triggers are attached at the top level of the create payload, not in
		// the definition; the in-definition list stays empty.
		triggers: [],
		plan: buildPlan(form),
		execution: {
			timeout_seconds: form.execution.timeoutSeconds,
			max_retries: form.execution.maxRetries,
			retry_backoff: form.execution.retryBackoff,
			concurrency: form.execution.concurrency,
			on_failure: [],
		},
		metadata: { tags: form.tags },
		// Only emit models when fully resolved (the builder seeds non-zero
		// defaults before submit). A zero/unset triple is omitted so the
		// backend falls back to the workspace snapshot.
		...(hasResolvedModels(form.models)
			? {
					models: {
						chat_model_id: form.models.chatModelId,
						image_gen_model_id: form.models.imageConfigId,
						vision_model_id: form.models.visionConfigId,
					},
				}
			: {}),
	} as unknown as AutomationDefinition;
}

/** True once every model slot holds a concrete (non-zero) id. */
export function hasResolvedModels(models: BuilderModels): boolean {
	return models.chatModelId !== 0 && models.imageConfigId !== 0 && models.visionConfigId !== 0;
}

/** The desired schedule trigger for this form, or ``null`` if none. */
export function buildScheduleTrigger(form: BuilderForm): TriggerCreateRequest | null {
	if (!form.schedule) return null;
	return {
		type: "schedule",
		params: { cron: scheduleToCron(form.schedule), timezone: form.timezone },
		static_inputs: {},
		enabled: true,
	};
}

export function buildCreatePayload(
	form: BuilderForm,
	workspaceId: number
): AutomationCreateRequest {
	const trigger = buildScheduleTrigger(form);
	return {
		workspace_id: workspaceId,
		name: form.name.trim(),
		description: form.description?.trim() ? form.description.trim() : null,
		definition: buildDefinition(form),
		triggers: trigger ? [trigger] : [],
	};
}

export function buildUpdatePayload(form: BuilderForm): AutomationUpdateRequest {
	return {
		name: form.name.trim(),
		description: form.description?.trim() ? form.description.trim() : null,
		definition: buildDefinition(form),
	};
}

// ---------------------------------------------------------------------------
// Contract -> form (edit hydration with safe fallback)
// ---------------------------------------------------------------------------

export type HydrateResult =
	| { formable: true; form: BuilderForm }
	| { formable: false; reason: string };

/** A trigger as seen by the hydrator: both ``Trigger`` and ``TriggerCreateRequest`` fit. */
export interface HydratableTrigger {
	type: string;
	params: Record<string, unknown>;
}

const BACKOFF_VALUES = ["exponential", "linear", "none"] as const;
const CONCURRENCY_VALUES = ["drop_if_running", "queue", "always"] as const;

function asRecord(value: unknown): Record<string, unknown> {
	return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

/** Best-effort projection of a stored ``mentioned_documents`` entry into a chip. */
function coerceMention(raw: unknown): MentionedDocumentInfo | null {
	const o = asRecord(raw);
	if (typeof o.id !== "number" || typeof o.title !== "string") return null;
	if (o.kind === "folder") {
		return { id: o.id, title: o.title, kind: "folder" };
	}
	if (o.kind === "connector") {
		if (typeof o.connector_type !== "string" || typeof o.account_name !== "string") return null;
		return {
			id: o.id,
			title: o.title,
			kind: "connector",
			connector_type: o.connector_type,
			account_name: o.account_name,
		};
	}
	return {
		id: o.id,
		title: o.title,
		kind: "doc",
		document_type: typeof o.document_type === "string" ? o.document_type : "UNKNOWN",
	};
}

/**
 * Rebuild a task's mention chips from step params. Doc/folder chips come from
 * ``mentioned_documents``; connector chips from ``mentioned_connectors`` (kept
 * in their own bucket). Returns ``null`` when the step carries mention IDs that
 * aren't backed by usable chip metadata (e.g. hand-edited JSON), so the caller
 * can fall back to JSON mode rather than silently dropping those IDs on save.
 */
function mentionsFromParams(params: Record<string, unknown>): MentionedDocumentInfo[] | null {
	const mentions: MentionedDocumentInfo[] = [];
	const docList = Array.isArray(params.mentioned_documents) ? params.mentioned_documents : [];
	for (const raw of docList) {
		const mention = coerceMention(raw);
		// Connectors belong in their own bucket; ignore any that leak in here.
		if (mention && mention.kind !== "connector") mentions.push(mention);
	}
	const connectorList = Array.isArray(params.mentioned_connectors)
		? params.mentioned_connectors
		: [];
	for (const raw of connectorList) {
		const mention = coerceMention(raw);
		if (mention && mention.kind === "connector") mentions.push(mention);
	}

	const haveByKind = {
		doc: new Set(mentions.filter((m) => m.kind === "doc").map((m) => m.id)),
		folder: new Set(mentions.filter((m) => m.kind === "folder").map((m) => m.id)),
		connector: new Set(mentions.filter((m) => m.kind === "connector").map((m) => m.id)),
	};
	const idChecks: Array<[unknown, Set<number>]> = [
		[params.mentioned_document_ids, haveByKind.doc],
		[params.mentioned_folder_ids, haveByKind.folder],
		[params.mentioned_connector_ids, haveByKind.connector],
	];
	for (const [arr, have] of idChecks) {
		if (!Array.isArray(arr)) continue;
		for (const id of arr) {
			if (typeof id === "number" && !have.has(id)) return null;
		}
	}
	return mentions;
}

/**
 * Core projection of a definition + triggers into the builder form. Returns
 * ``formable: false`` whenever something can't be represented, so the caller
 * can drop into raw-JSON mode without losing data. Shared by the edit
 * hydrator and the JSON-mode round-trip.
 *
 * The definition is read defensively (``unknown``) so a partially edited JSON
 * tree can still round-trip into the form; completeness is enforced by the
 * form's own validation at submit time, not here.
 */
export function hydrateForm(
	name: string,
	description: string | null,
	def: unknown,
	triggers: HydratableTrigger[]
): HydrateResult {
	const d = asRecord(def);

	if (d.inputs) {
		return { formable: false, reason: "uses an inputs schema" };
	}

	const exec = asRecord(d.execution);
	const onFailure = Array.isArray(exec.on_failure) ? exec.on_failure : [];
	if (onFailure.length > 0) {
		return { formable: false, reason: "has on-failure steps" };
	}

	const metadata = asRecord(d.metadata);
	const extraMetadataKeys = Object.keys(metadata).filter((key) => key !== "tags");
	if (extraMetadataKeys.length > 0) {
		return { formable: false, reason: "has custom metadata" };
	}

	const plan = Array.isArray(d.plan) ? d.plan : [];
	const tasks: BuilderTask[] = [];
	let unattended = true;
	for (const rawStep of plan) {
		const step = asRecord(rawStep);
		if (step.action !== "agent_task") {
			return { formable: false, reason: `uses the "${String(step.action)}" action` };
		}
		if (step.when) {
			return { formable: false, reason: "uses conditional steps" };
		}
		const params = asRecord(step.params);
		const query = typeof params.query === "string" ? params.query : "";
		// auto_approve_all is a single global toggle in the form; if any step is
		// explicitly false we surface the toggle as off.
		if (params.auto_approve_all === false) unattended = false;
		const mentions = mentionsFromParams(params);
		if (mentions === null) {
			return { formable: false, reason: "references mentions without metadata" };
		}
		tasks.push({
			id: newId(),
			query,
			mentions,
			maxRetries: typeof step.max_retries === "number" ? step.max_retries : null,
			timeoutSeconds: typeof step.timeout_seconds === "number" ? step.timeout_seconds : null,
		});
	}
	if (tasks.length === 0) {
		return { formable: false, reason: "has no steps" };
	}

	if (triggers.length > 1) {
		return { formable: false, reason: "has multiple triggers" };
	}
	const trigger = triggers[0];
	let schedule: BuilderSchedule | null = null;
	let timezone = getDefaultTimezone();
	if (trigger) {
		if (trigger.type !== "schedule") {
			return { formable: false, reason: `has a "${trigger.type}" trigger` };
		}
		const cron = typeof trigger.params?.cron === "string" ? trigger.params.cron : "";
		timezone = typeof trigger.params?.timezone === "string" ? trigger.params.timezone : timezone;
		const model = fromCron(cron);
		schedule = model ? { mode: "preset", model } : { mode: "cron", cron };
	}

	const retryBackoff = BACKOFF_VALUES.includes(exec.retry_backoff as never)
		? (exec.retry_backoff as BuilderExecution["retryBackoff"])
		: EXECUTION_DEFAULTS.retry_backoff;
	const concurrency = CONCURRENCY_VALUES.includes(exec.concurrency as never)
		? (exec.concurrency as BuilderExecution["concurrency"])
		: EXECUTION_DEFAULTS.concurrency;
	const tags = Array.isArray(metadata.tags)
		? metadata.tags.filter((tag): tag is string => typeof tag === "string")
		: [];

	const models = modelsFromDefinition(d.models);

	return {
		formable: true,
		form: {
			name,
			description: description ?? null,
			tasks,
			unattended,
			schedule,
			timezone,
			execution: {
				timeoutSeconds:
					typeof exec.timeout_seconds === "number"
						? exec.timeout_seconds
						: EXECUTION_DEFAULTS.timeout_seconds,
				maxRetries:
					typeof exec.max_retries === "number" ? exec.max_retries : EXECUTION_DEFAULTS.max_retries,
				retryBackoff,
				concurrency,
			},
			tags,
			goal: typeof d.goal === "string" ? d.goal : null,
			models,
		},
	};
}

/** Read a captured ``definition.models`` snapshot into the form's model slots. */
function modelsFromDefinition(raw: unknown): BuilderModels {
	const m = asRecord(raw);
	const num = (value: unknown) => (typeof value === "number" ? value : 0);
	return {
		chatModelId: num(m.chat_model_id),
		imageConfigId: num(m.image_gen_model_id),
		visionConfigId: num(m.vision_model_id),
	};
}

/**
 * Project an existing automation into the builder form for editing.
 */
export function formFromAutomation(automation: Automation): HydrateResult {
	return hydrateForm(
		automation.name,
		automation.description ?? null,
		automation.definition,
		automation.triggers ?? []
	);
}
