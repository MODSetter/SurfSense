"use client";

import type { AnyPluginConfig } from "platejs";

import { AutoformatKit } from "@/components/editor/plugins/autoformat-kit";
import { BasicNodesKit } from "@/components/editor/plugins/basic-nodes-kit";
import { CalloutKit } from "@/components/editor/plugins/callout-kit";
import { CodeBlockKit } from "@/components/editor/plugins/code-block-kit";
import { DndKit } from "@/components/editor/plugins/dnd-kit";
import { FixedToolbarKit } from "@/components/editor/plugins/fixed-toolbar-kit";
import { FloatingToolbarKit } from "@/components/editor/plugins/floating-toolbar-kit";
import { LinkKit } from "@/components/editor/plugins/link-kit";
import { ListKit } from "@/components/editor/plugins/list-kit";
import { MathKit } from "@/components/editor/plugins/math-kit";
import { SelectionKit } from "@/components/editor/plugins/selection-kit";
import { SlashCommandKit } from "@/components/editor/plugins/slash-command-kit";
import { TableKit } from "@/components/editor/plugins/table-kit";
import { ToggleKit } from "@/components/editor/plugins/toggle-kit";

/**
 * Full preset – every plugin kit enabled.
 * Used by the Documents editor and Reports editor (rich editing experience).
 */
export const fullPreset: AnyPluginConfig[] = [
	...BasicNodesKit,
	...TableKit,
	...ListKit,
	...CodeBlockKit,
	...LinkKit,
	...CalloutKit,
	...ToggleKit,
	...MathKit,
	...SelectionKit,
	...SlashCommandKit,
	...FixedToolbarKit,
	...FloatingToolbarKit,
	...AutoformatKit,
	...DndKit,
];

/**
 * Minimal preset – lightweight editing with core formatting only.
 * No fixed toolbar, no slash commands, no DnD, no block selection.
 * Ideal for inline editors like human-in-the-loop agent actions.
 */
export const minimalPreset: AnyPluginConfig[] = [
	...BasicNodesKit,
	...ListKit,
	...CodeBlockKit,
	...LinkKit,
	...FloatingToolbarKit,
	...AutoformatKit,
];

/**
 * Read-only preset – rendering support for all rich content, but no editing UI.
 * No toolbars, no autoformat, no DnD, no slash commands, no block selection.
 * Ideal for pure display / viewer contexts.
 */
export const readonlyPreset: AnyPluginConfig[] = [
	...BasicNodesKit,
	...TableKit,
	...ListKit,
	...CodeBlockKit,
	...LinkKit,
	...CalloutKit,
	...ToggleKit,
	...MathKit,
];

/** All available preset names */
export type EditorPreset = "full" | "minimal" | "readonly";

/** Map from preset name to plugin array */
export const presetMap: Record<EditorPreset, AnyPluginConfig[]> = {
	full: fullPreset,
	minimal: minimalPreset,
	readonly: readonlyPreset,
};
