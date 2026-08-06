import type { ModelPreviewRead, ModelRead } from "@/contracts/types/model-connections.types";

export type ModelCapabilityFilter = "chat" | "vision" | "image_gen";

export const MODEL_CAPABILITY_FILTERS: { key: ModelCapabilityFilter; label: string }[] = [
	{ key: "chat", label: "Chat" },
	{ key: "vision", label: "Vision" },
	{ key: "image_gen", label: "Image" },
];

const CAPABILITY_FIELDS = {
	chat: "supports_chat",
	vision: "supports_image_input",
	image_gen: "supports_image_generation",
} as const;

export type SelectableModel = (ModelRead | ModelPreviewRead) & {
	id?: number | string;
	connection_id?: number;
};

export function modelLabel(model: SelectableModel) {
	return model.display_name || model.model_id;
}

export function capability(model: SelectableModel, key: ModelCapabilityFilter) {
	const field = CAPABILITY_FIELDS[key];
	const overrides = "capabilities_override" in model ? model.capabilities_override : undefined;

	if (overrides && field in overrides) return Boolean(overrides[field]);
	if (overrides && key in overrides) return Boolean(overrides[key]);
	return Boolean(model[field]);
}

function positiveInteger(value: unknown) {
	return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}

/**
 * The context length the model itself reports, read from the raw discovery
 * payload. Shown as a hint next to the max input tokens field: it is what the
 * model supports, not what the host loaded it with, so it is an upper bound to
 * aim at rather than a value to apply.
 */
export function reportedContextLength(model: SelectableModel) {
	const payload = ("catalog" in model ? model.catalog : model.metadata) ?? {};
	const modelInfo = (payload.model_info ?? {}) as Record<string, unknown>;
	const architecture = modelInfo["general.architecture"];
	const details = (payload.details ?? {}) as Record<string, unknown>;

	return (
		positiveInteger(
			typeof architecture === "string" ? modelInfo[`${architecture}.context_length`] : null
		) ??
		positiveInteger(details.context_length) ??
		positiveInteger(payload.max_context_length)
	);
}

export function capabilityLabels(model: SelectableModel) {
	return MODEL_CAPABILITY_FILTERS.filter((filter) => capability(model, filter.key))
		.map((filter) => filter.label.toLowerCase())
		.join(", ");
}
