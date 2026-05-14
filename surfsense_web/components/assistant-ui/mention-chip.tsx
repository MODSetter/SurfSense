"use client";

import type { MouseEventHandler, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * A single, minimal chip-button used in two places:
 *
 * 1. User-message mention chips (rendered for every `@`-mention the user
 *    inserted in the composer).
 * 2. AI-answer file/folder paths (rendered when the assistant emits
 *    `/documents/.../file.xml` or `/<mount>/.../file.ext`).
 *
 * Both contexts want the same visual language: a compact, button-styled
 * chip with an icon, a truncated label, and an optional tooltip. Sharing
 * one component keeps the chat surface visually coherent and means a UX
 * tweak (radius, hover, icon size) lands in both places at once.
 *
 * Styling rules (per shadcn skill):
 * - Semantic tokens only (`border`, `bg-background`, `bg-accent`,
 *   `text-foreground`, `text-muted-foreground`). No raw colors.
 * - Layout via `gap-*`, never `space-x-*`.
 * - `cn()` for conditional classes.
 * - No manual `z-index` — the tooltip handles its own stacking.
 */
export interface MentionChipProps {
	/**
	 * Visual prefix. Keep this small (e.g. `size-3.5`); the chip controls
	 * its own height and oversized icons will push the label out of place.
	 */
	icon: ReactNode;
	/** Label shown inside the chip; truncated with `…` past the max width. */
	label: string;
	/**
	 * Full title or path shown on hover. Omit to suppress the tooltip
	 * entirely (e.g. when the label already conveys the full identity).
	 */
	tooltip?: ReactNode;
	/**
	 * When provided, the chip behaves like a button (focusable, hover
	 * effect, pointer cursor). Omit for a purely decorative chip.
	 */
	onClick?: MouseEventHandler<HTMLButtonElement>;
	disabled?: boolean;
	className?: string;
	/** Optional override for the accessible name; defaults to `label`. */
	ariaLabel?: string;
}

export function MentionChip({
	icon,
	label,
	tooltip,
	onClick,
	disabled,
	className,
	ariaLabel,
}: MentionChipProps) {
	const isInteractive = Boolean(onClick) && !disabled;

	const chip = (
		<Button
			variant="ghost"
			type="button"
			onClick={onClick}
			disabled={disabled}
			aria-label={ariaLabel ?? label}
			className={cn(
				"h-auto max-w-[220px] justify-start gap-1.5 rounded-md border bg-background px-2 py-0.5 align-middle text-xs leading-5 text-foreground shadow-none transition-colors focus-visible:ring-1 focus-visible:ring-ring",
				isInteractive
					? "cursor-pointer hover:bg-accent hover:text-accent-foreground"
					: "cursor-default",
				disabled && "opacity-60",
				className
			)}
		>
			<span className="inline-flex shrink-0 text-muted-foreground">{icon}</span>
			<span className="truncate">{label}</span>
		</Button>
	);

	if (!tooltip) return chip;

	return (
		<Tooltip>
			<TooltipTrigger asChild>{chip}</TooltipTrigger>
			<TooltipContent side="top" className="max-w-xs break-all">
				{tooltip}
			</TooltipContent>
		</Tooltip>
	);
}
