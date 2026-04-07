"use client";

import { RotateCcw } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Accelerator <-> display helpers
// ---------------------------------------------------------------------------

export function keyEventToAccelerator(e: React.KeyboardEvent): string | null {
	const parts: string[] = [];
	if (e.ctrlKey || e.metaKey) parts.push("CommandOrControl");
	if (e.altKey) parts.push("Alt");
	if (e.shiftKey) parts.push("Shift");

	const key = e.key;
	if (["Control", "Meta", "Alt", "Shift"].includes(key)) return null;

	if (key === " ") parts.push("Space");
	else if (key.length === 1) parts.push(key.toUpperCase());
	else parts.push(key);

	if (parts.length < 2) return null;
	return parts.join("+");
}

export function acceleratorToDisplay(accel: string): string[] {
	if (!accel) return [];
	return accel.split("+").map((part) => {
		if (part === "CommandOrControl") return "Ctrl";
		if (part === "Space") return "Space";
		return part;
	});
}

export const DEFAULT_SHORTCUTS = {
	generalAssist: "CommandOrControl+Shift+S",
	quickAsk: "CommandOrControl+Alt+S",
	autocomplete: "CommandOrControl+Shift+Space",
};

// ---------------------------------------------------------------------------
// Kbd pill component
// ---------------------------------------------------------------------------

export function Kbd({ keys, className }: { keys: string[]; className?: string }) {
	return (
		<span className={cn("inline-flex items-center gap-0.5", className)}>
			{keys.map((key, i) => (
				<kbd
					key={`${key}-${i}`}
					className={cn(
						"inline-flex h-6 min-w-6 items-center justify-center rounded border bg-muted px-1 font-mono text-[11px] font-medium text-muted-foreground",
						key.length > 3 && "px-1.5"
					)}
				>
					{key}
				</kbd>
			))}
		</span>
	);
}

// ---------------------------------------------------------------------------
// Shortcut recorder component
// ---------------------------------------------------------------------------

export function ShortcutRecorder({
	value,
	onChange,
	onReset,
	defaultValue,
	label,
	description,
	icon: Icon,
}: {
	value: string;
	onChange: (accelerator: string) => void;
	onReset: () => void;
	defaultValue: string;
	label: string;
	description: string;
	icon: React.ElementType;
}) {
	const [recording, setRecording] = useState(false);
	const inputRef = useRef<HTMLButtonElement>(null);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (!recording) return;
			e.preventDefault();
			e.stopPropagation();

			if (e.key === "Escape") {
				setRecording(false);
				return;
			}

			const accel = keyEventToAccelerator(e);
			if (accel) {
				onChange(accel);
				setRecording(false);
			}
		},
		[recording, onChange]
	);

	const displayKeys = acceleratorToDisplay(value);
	const isDefault = value === defaultValue;

	return (
		<div className="group flex items-center gap-3 rounded-lg border border-border/60 bg-card px-3 py-2.5 transition-colors hover:border-border">
			{/* Icon */}
			<div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
				<Icon className="size-4" />
			</div>

			{/* Label + description */}
			<div className="min-w-0 flex-1">
				<p className="text-[13px] font-medium leading-none">{label}</p>
				<p className="mt-1 text-[11px] leading-snug text-muted-foreground">{description}</p>
			</div>

			{/* Actions */}
			<div className="flex shrink-0 items-center gap-1">
				{!isDefault && (
					<Button
						variant="ghost"
						size="icon"
						className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
						onClick={onReset}
						title="Reset to default"
					>
						<RotateCcw className="size-3" />
					</Button>
				)}
				<button
					ref={inputRef}
					type="button"
					onClick={() => setRecording(true)}
					onKeyDown={handleKeyDown}
					onBlur={() => setRecording(false)}
					className={cn(
						"flex h-7 items-center gap-0.5 rounded-md border px-2 transition-all focus:outline-none",
						recording
							? "border-primary bg-primary/5 ring-2 ring-primary/20"
							: "border-input bg-muted/40 hover:bg-muted"
					)}
				>
					{recording ? (
						<span className="text-[11px] text-primary animate-pulse whitespace-nowrap">Press keys…</span>
					) : (
						<Kbd keys={displayKeys} />
					)}
				</button>
			</div>
		</div>
	);
}
