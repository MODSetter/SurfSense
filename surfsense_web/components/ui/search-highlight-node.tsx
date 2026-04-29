"use client";

import type { PlateLeafProps } from "platejs/react";
import { PlateLeaf } from "platejs/react";

/**
 * Stable class name used to identify Plate-rendered citation highlight
 * leaves in the DOM. We can't use a `data-*` attribute here — Plate's
 * `PlateLeaf` runs its props through `useNodeAttributes`, which only
 * forwards `attributes`, `className`, `ref`, and `style` to the rendered
 * element; arbitrary `data-*` props are silently dropped (verified
 * against `@platejs/core/dist/react/index.js` v52). So `className` is
 * the only escape hatch that's guaranteed to survive into the DOM.
 */
export const CITATION_HIGHLIGHT_CLASS = "citation-highlight-leaf";

/**
 * Leaf rendered for ranges decorated by `@platejs/find-replace`'s
 * `FindReplacePlugin`. We re-purpose that plugin to drive the citation-jump
 * highlight: when a citation is staged, the parent sets the plugin's `search`
 * option to a snippet of the chunk text and Plate decorates every match with
 * `searchHighlight: true`. This component renders those decorations as a
 * `<mark>` tagged with `CITATION_HIGHLIGHT_CLASS` so the parent can:
 *   1. Query the first match in DOM order to scroll it into view.
 *   2. Detect the active-highlight state without a separate React ref.
 *
 * The highlight is **persistent** — it does not auto-fade. The parent in
 * `EditorPanelContent` clears it by setting the plugin's `search` option
 * back to "" when one of: (a) the user clicks anywhere inside the editor,
 * (b) the panel switches to a different document, (c) the user toggles
 * into edit mode, (d) another citation jump is staged, (e) the panel
 * unmounts. We use a brief entrance pulse (`citation-flash-in`, see
 * `globals.css`) purely to draw the eye after `scrollIntoView` lands.
 */
export function SearchHighlightLeaf(props: PlateLeafProps) {
	return (
		<PlateLeaf
			{...props}
			as="mark"
			className={`${CITATION_HIGHLIGHT_CLASS} bg-primary/15 ring-1 ring-primary/40 rounded-sm px-0.5 text-inherit animate-[citation-flash-in_400ms_ease-out]`}
		>
			{props.children}
		</PlateLeaf>
	);
}
