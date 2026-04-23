"use client";

import { ArrowBigUp, BrainCog, Command, Option, Rocket, RotateCcw, Zap } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { DEFAULT_SHORTCUTS, keyEventToAccelerator } from "@/components/desktop/shortcut-recorder";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";

type ShortcutKey = "generalAssist" | "quickAsk" | "autocomplete";
type ShortcutMap = typeof DEFAULT_SHORTCUTS;

const HOTKEY_ROWS: Array<{ key: ShortcutKey; label: string; icon: React.ElementType }> = [
	{ key: "generalAssist", label: "General Assist", icon: Rocket },
	{ key: "quickAsk", label: "Quick Assist", icon: Zap },
	{ key: "autocomplete", label: "Extreme Assist", icon: BrainCog },
];

type ShortcutToken =
	| { kind: "text"; value: string }
	| { kind: "icon"; value: "command" | "option" | "shift" };

function acceleratorToTokens(accel: string, isMac: boolean): ShortcutToken[] {
	if (!accel) return [];
	return accel.split("+").map((part) => {
		if (part === "CommandOrControl") {
			return isMac ? { kind: "icon", value: "command" as const } : { kind: "text", value: "Ctrl" };
		}
		if (part === "Alt") {
			return isMac ? { kind: "icon", value: "option" as const } : { kind: "text", value: "Alt" };
		}
		if (part === "Shift") {
			return isMac ? { kind: "icon", value: "shift" as const } : { kind: "text", value: "Shift" };
		}
		if (part === "Space") return { kind: "text", value: "Space" };
		return { kind: "text", value: part.length === 1 ? part.toUpperCase() : part };
	});
}

function HotkeyRow({
	label,
	value,
	defaultValue,
	icon: Icon,
	isMac,
	onChange,
	onReset,
}: {
	label: string;
	value: string;
	defaultValue: string;
	icon: React.ElementType;
	isMac: boolean;
	onChange: (accelerator: string) => void;
	onReset: () => void;
}) {
	const [recording, setRecording] = useState(false);
	const inputRef = useRef<HTMLButtonElement>(null);
	const isDefault = value === defaultValue;
	const displayTokens = useMemo(() => acceleratorToTokens(value, isMac), [value, isMac]);

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
		[onChange, recording]
	);

	return (
		<div className="flex items-center justify-between gap-2.5 border-border/60 border-b py-3 last:border-b-0">
			<div className="flex items-center gap-2.5 min-w-0">
				<div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
					<Icon className="size-3.5" />
				</div>
				<p className="text-sm text-foreground truncate">{label}</p>
			</div>
			<div className="flex shrink-0 items-center gap-1">
				{!isDefault && (
					<Button
						variant="ghost"
						size="icon"
						className="size-7 text-muted-foreground hover:text-foreground"
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
					className={
						recording
							? "flex h-7 items-center rounded-md border border-primary bg-primary/5 ring-2 ring-primary/20"
							: "flex h-7 items-center rounded-md border border-input bg-muted/50 hover:bg-muted"
					}
				>
					{recording ? (
						<span className="px-2 text-[9px] text-primary whitespace-nowrap">
							Press hotkeys...
						</span>
					) : (
						<>
							{displayTokens.map((token, idx) => (
								<span
									key={`${token.kind}-${idx}`}
									className="inline-flex h-full min-w-7 items-center justify-center border-border/60 border-r px-1.5 text-[11px] font-medium text-muted-foreground"
								>
									{token.kind === "text" ? (
										token.value
									) : token.value === "command" ? (
										<Command className="size-3" />
									) : token.value === "option" ? (
										<Option className="size-3" />
									) : (
										<ArrowBigUp className="size-3" />
									)}
								</span>
							))}
						</>
					)}
				</button>
			</div>
		</div>
	);
}

export function DesktopShortcutsContent() {
	const api = useElectronAPI();
	const [shortcuts, setShortcuts] = useState(DEFAULT_SHORTCUTS);
	const [shortcutsLoaded, setShortcutsLoaded] = useState(false);
	const isMac = api?.versions?.platform === "darwin";

	useEffect(() => {
		if (!api) {
			setShortcutsLoaded(true);
			return;
		}

		let mounted = true;
		(api.getShortcuts?.() ?? Promise.resolve(null))
			.then((config: ShortcutMap | null) => {
				if (!mounted) return;
				if (config) setShortcuts(config);
				setShortcutsLoaded(true);
			})
			.catch(() => {
				if (!mounted) return;
				setShortcutsLoaded(true);
			});

		return () => {
			mounted = false;
		};
	}, [api]);

	if (!api) {
		return (
			<div className="flex flex-col items-center justify-center py-12 text-center">
				<p className="text-sm text-muted-foreground">Hotkeys are only available in the SurfSense desktop app.</p>
			</div>
		);
	}

	const updateShortcut = (
		key: "generalAssist" | "quickAsk" | "autocomplete",
		accelerator: string
	) => {
		setShortcuts((prev) => {
			const updated = { ...prev, [key]: accelerator };
			api.setShortcuts?.({ [key]: accelerator }).catch(() => {
				toast.error("Failed to update shortcut");
			});
			return updated;
		});
		toast.success("Shortcut updated");
	};

	const resetShortcut = (key: ShortcutKey) => {
		updateShortcut(key, DEFAULT_SHORTCUTS[key]);
	};

	return (
		shortcutsLoaded ? (
			<div className="flex flex-col gap-3">
				<div>
					{HOTKEY_ROWS.map((row) => (
						<HotkeyRow
							key={row.key}
							label={row.label}
							value={shortcuts[row.key]}
							defaultValue={DEFAULT_SHORTCUTS[row.key]}
							icon={row.icon}
							isMac={isMac}
							onChange={(accel) => updateShortcut(row.key, accel)}
							onReset={() => resetShortcut(row.key)}
						/>
					))}
				</div>
			</div>
		) : (
			<div className="flex justify-center py-4">
				<Spinner size="sm" />
			</div>
		)
	);
}
