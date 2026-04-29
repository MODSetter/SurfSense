"use client";

import { FindReplacePlugin } from "@platejs/find-replace";
import type { AnyPluginConfig } from "platejs";
import { TrailingBlockPlugin } from "platejs";

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
import { SearchHighlightLeaf } from "@/components/ui/search-highlight-node";

/**
 * Citation-jump highlighter. Re-uses Plate's built-in `FindReplacePlugin`
 * (decorate-only, no editing surface) to drive the "scroll-to-cited-text"
 * UX in `EditorPanelContent`. We register it in every preset because:
 *   - Decorate is a no-op when `search` is empty (single getOptions() check
 *     per block), so cost is effectively zero for non-citation viewers.
 *   - Keeping it preset-agnostic means citations work whether the doc is
 *     opened in editable (`full`) or pure-viewer (`readonly`) modes.
 *
 * The parent component drives `setOption(FindReplacePlugin, 'search', ...)`
 * + `editor.api.redecorate()` to trigger highlights, then queries the
 * editor DOM for `.citation-highlight-leaf` to scroll the first match
 * into view. (We can't use a `data-*` attribute here — Plate's
 * `PlateLeaf` runs props through `useNodeAttributes`, which only forwards
 * `attributes`, `className`, `ref`, `style`; arbitrary `data-*` props are
 * silently dropped.) See `components/ui/search-highlight-node.tsx` for
 * the leaf component and `CITATION_HIGHLIGHT_CLASS` constant.
 */
const CitationFindReplacePlugin = FindReplacePlugin.configure({
	options: { search: "" },
	render: { node: SearchHighlightLeaf },
});

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
	TrailingBlockPlugin,
	CitationFindReplacePlugin,
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
	...AutoformatKit,
	TrailingBlockPlugin,
	CitationFindReplacePlugin,
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
	CitationFindReplacePlugin,
];

/** All available preset names */
export type EditorPreset = "full" | "minimal" | "readonly";

/** Map from preset name to plugin array */
export const presetMap: Record<EditorPreset, AnyPluginConfig[]> = {
	full: fullPreset,
	minimal: minimalPreset,
	readonly: readonlyPreset,
};
