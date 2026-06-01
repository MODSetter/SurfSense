"use client";

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import {
	globalImageGenConfigsAtom,
	imageGenConfigsAtom,
} from "@/atoms/image-gen-config/image-gen-config-query.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import {
	globalVisionLLMConfigsAtom,
	visionLLMConfigsAtom,
} from "@/atoms/vision-llm-config/vision-llm-config-query.atoms";

/**
 * A single model the user may pick for an automation slot.
 */
export interface EligibleModelOption {
	id: number;
	name: string;
	/** Underlying model identifier (e.g. `gpt-4o`); shown as secondary text. */
	modelName: string;
	provider: string;
	/** `true` for user BYOK configs (positive ids), `false` for premium globals. */
	isBYOK: boolean;
}

export interface EligibleModelKind {
	options: EligibleModelOption[];
	/** Default selection: the search-space pref when eligible, else first option. */
	defaultId: number | null;
	/** O(1) id → option lookup for trigger labels (avoids per-render `.find()`). */
	byId: Map<number, EligibleModelOption>;
}

export interface AutomationEligibleModels {
	llm: EligibleModelKind;
	image: EligibleModelKind;
	vision: EligibleModelKind;
	isLoading: boolean;
}

interface GlobalConfigLike {
	id: number;
	name: string;
	model_name: string;
	provider: string;
	is_premium?: boolean;
	is_auto_mode?: boolean;
}

interface UserConfigLike {
	id: number;
	name: string;
	model_name: string;
	provider: string;
}

/**
 * Build the eligible option list for one model kind: premium globals
 * (`is_premium === true`, never Auto mode) followed by all BYOK configs.
 */
function buildKind(
	globals: GlobalConfigLike[] | undefined,
	byok: UserConfigLike[] | undefined,
	prefId: number | null | undefined
): EligibleModelKind {
	const premiumGlobals: EligibleModelOption[] = (globals ?? [])
		.filter((c) => c.is_premium === true && !c.is_auto_mode)
		.map((c) => ({
			id: c.id,
			name: c.name,
			modelName: c.model_name,
			provider: c.provider,
			isBYOK: false,
		}));

	const byokOptions: EligibleModelOption[] = (byok ?? []).map((c) => ({
		id: c.id,
		name: c.name,
		modelName: c.model_name,
		provider: c.provider,
		isBYOK: true,
	}));

	const options = [...premiumGlobals, ...byokOptions];
	const byId = new Map<number, EligibleModelOption>(options.map((o) => [o.id, o]));

	let defaultId: number | null = null;
	if (prefId != null && byId.has(prefId)) {
		defaultId = prefId;
	} else if (options.length > 0) {
		defaultId = options[0].id;
	}

	return { options, defaultId, byId };
}

/**
 * Lists the LLM / image / vision models that are eligible for automations
 * (premium globals + user BYOK — never free globals or Auto mode), with a
 * default selection seeded from the search space's role preferences.
 *
 * Everything is derived during render from the existing config query atoms;
 * there are no effects, so option lists/maps keep stable references.
 */
export function useAutomationEligibleModels(): AutomationEligibleModels {
	const { data: llmUserConfigs, isLoading: llmUserLoading } = useAtomValue(newLLMConfigsAtom);
	const { data: llmGlobalConfigs, isLoading: llmGlobalLoading } =
		useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences, isLoading: prefsLoading } = useAtomValue(llmPreferencesAtom);
	const { data: imageGlobalConfigs, isLoading: imageGlobalLoading } =
		useAtomValue(globalImageGenConfigsAtom);
	const { data: imageUserConfigs, isLoading: imageUserLoading } = useAtomValue(imageGenConfigsAtom);
	const { data: visionGlobalConfigs, isLoading: visionGlobalLoading } = useAtomValue(
		globalVisionLLMConfigsAtom
	);
	const { data: visionUserConfigs, isLoading: visionUserLoading } =
		useAtomValue(visionLLMConfigsAtom);

	const llm = useMemo(
		() => buildKind(llmGlobalConfigs, llmUserConfigs, preferences?.agent_llm_id),
		[llmGlobalConfigs, llmUserConfigs, preferences?.agent_llm_id]
	);

	const image = useMemo(
		() => buildKind(imageGlobalConfigs, imageUserConfigs, preferences?.image_generation_config_id),
		[imageGlobalConfigs, imageUserConfigs, preferences?.image_generation_config_id]
	);

	const vision = useMemo(
		() => buildKind(visionGlobalConfigs, visionUserConfigs, preferences?.vision_llm_config_id),
		[visionGlobalConfigs, visionUserConfigs, preferences?.vision_llm_config_id]
	);

	const isLoading =
		llmUserLoading ||
		llmGlobalLoading ||
		prefsLoading ||
		imageGlobalLoading ||
		imageUserLoading ||
		visionGlobalLoading ||
		visionUserLoading;

	return useMemo(() => ({ llm, image, vision, isLoading }), [llm, image, vision, isLoading]);
}
