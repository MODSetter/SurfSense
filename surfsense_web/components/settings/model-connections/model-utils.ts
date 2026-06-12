import type { ModelRead } from "@/contracts/types/model-connections.types";

export type ModelCapabilityFilter = "chat" | "vision" | "image_gen";

export const MODEL_CAPABILITY_FILTERS: { key: ModelCapabilityFilter; label: string }[] = [
	{ key: "chat", label: "Chat" },
	{ key: "vision", label: "Vision" },
	{ key: "image_gen", label: "Image" },
];

export function modelLabel(model: ModelRead) {
	return model.display_name || model.model_id;
}

export function capability(model: ModelRead, key: ModelCapabilityFilter) {
	if (key === "chat") return Boolean(model.supports_chat);
	if (key === "vision") return Boolean(model.supports_image_input);
	return Boolean(model.supports_image_generation);
}

export function capabilityLabels(model: ModelRead) {
	return MODEL_CAPABILITY_FILTERS.filter((filter) => capability(model, filter.key))
		.map((filter) => filter.label.toLowerCase())
		.join(", ");
}
