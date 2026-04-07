"use client";

import { RotateCcw } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Accelerator ↔ display helpers
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
		<span className={cn("inline-flex items-center gap-1", className)}>
			{keys.map((key) => (
				<kbd
					key={key}
					className={cn(
						"inline-flex h-7 min-w-7 items-center justify-center rounded-md border bg-muted px-1.5 font-mono text-xs font-medium text-muted-foreground shadow-sm",
						key.length > 3 && "px-2"
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
		<div className="flex items-center justify-between gap-4 rounded-lg border bg-background p-3">
			<div className="flex items-center gap-3 min-w-0">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
					<Icon className="size-4" />
				</div>
				<div className="min-w-0">
					<p className="text-sm font-medium leading-none">{label}</p>
					<p className="mt-1 text-xs text-muted-foreground truncate">{description}</p>
				</div>
			</div>

			<div className="flex items-center gap-2 shrink-0">
				{!isDefault && (
					<Button
						variant="ghost"
						size="icon"
						className="size-7"
						onClick={onReset}
						title="Reset to default"
					>
						<RotateCcw />
					</Button>
				)}
				<button
					ref={inputRef}
					type="button"
					onClick={() => setRecording(true)}
					onKeyDown={handleKeyDown}
					onBlur={() => setRecording(false)}
					className={cn(
						"flex h-9 items-center gap-1 rounded-md border px-3 text-sm transition-all focus:outline-none",
						recording
							? "border-primary bg-primary/5 ring-2 ring-primary/20"
							: "border-input bg-muted/50 hover:bg-muted"
					)}
				>
					{recording ? (
						<span className="text-xs text-primary animate-pulse">Press keys...</span>
					) : (
						<Kbd keys={displayKeys} />
					)}
				</button>
			</div>
		</div>
	);
}
