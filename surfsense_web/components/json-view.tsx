"use client";

import ReactJson, { type InteractionProps } from "@microlink/react-json-view";
import { useTheme } from "next-themes";
import { useCallback, useMemo } from "react";

/**
 * Shared JSON viewer/editor wrapper around @microlink/react-json-view.
 *
 * One component, dual mode: passing ``editable`` + ``onChange`` enables
 * inline value editing, key renaming, add and delete. Omitting them
 * yields a read-only viewer. The underlying library is uncontrolled — it
 * mutates its own internal copy of ``src`` and surfaces the final tree on
 * each interaction via ``updated_src``, which we forward to ``onChange``.
 *
 * Theme follows ``next-themes``: a dark base-16 palette in dark mode, the
 * library's neutral default in light mode. Defaults are tuned for our
 * compact UI surfaces (no data-type labels, no key quotes, triangle icons,
 * tight indent).
 */
export interface JsonViewProps {
	/** The JSON value to display. Primitives are wrapped under ``{ value }``
	 *  because the underlying library requires an object root. */
	src: unknown;
	/** Enables value/key editing + add + delete. Requires ``onChange`` to
	 *  observe the result; without it the toggle is silently a no-op. */
	editable?: boolean;
	/** Called with the full updated tree on every accepted interaction. */
	onChange?: (next: unknown) => void;
	/** Collapse depth. ``true`` collapses everything past the root; a number
	 *  collapses from that depth onward. */
	collapsed?: boolean | number;
	/** Root label. Default ``false`` (no label — saves vertical space). */
	name?: string | false;
	className?: string;
}

const DARK_THEME = "monokai" as const;
const LIGHT_THEME = "rjv-default" as const;

const SHARED_DEFAULTS = {
	iconStyle: "triangle" as const,
	indentWidth: 2,
	enableClipboard: true,
	displayDataTypes: false,
	displayObjectSize: true,
	quotesOnKeys: false,
	collapseStringsAfterLength: 80,
};

export function JsonView({
	src,
	editable = false,
	onChange,
	collapsed = 2,
	name = false,
	className,
}: JsonViewProps) {
	const { resolvedTheme } = useTheme();
	const theme = resolvedTheme === "dark" ? DARK_THEME : LIGHT_THEME;

	// The library throws on non-object roots. Wrap primitives and null/undefined.
	const safeSrc = useMemo(() => {
		if (src && typeof src === "object") return src as object;
		return { value: src };
	}, [src]);

	const handleChange = useCallback(
		(interaction: InteractionProps) => {
			onChange?.(interaction.updated_src);
			return true;
		},
		[onChange]
	);

	const interactive = editable && onChange ? handleChange : (false as const);

	return (
		<div className={className}>
			<ReactJson
				src={safeSrc}
				name={name}
				theme={theme}
				collapsed={collapsed}
				onEdit={interactive}
				onAdd={interactive}
				onDelete={interactive}
				style={{ backgroundColor: "transparent", fontSize: 12, fontFamily: "var(--font-mono)" }}
				{...SHARED_DEFAULTS}
			/>
		</div>
	);
}
