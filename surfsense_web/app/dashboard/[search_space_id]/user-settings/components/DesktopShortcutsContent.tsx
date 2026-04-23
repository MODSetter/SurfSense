"use client";

import { BrainCog, Info, Rocket, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { DEFAULT_SHORTCUTS, ShortcutRecorder } from "@/components/desktop/shortcut-recorder";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";

export function DesktopShortcutsContent() {
	const api = useElectronAPI();
	const [shortcuts, setShortcuts] = useState(DEFAULT_SHORTCUTS);
	const [shortcutsLoaded, setShortcutsLoaded] = useState(false);

	useEffect(() => {
		if (!api) {
			setShortcutsLoaded(true);
			return;
		}

		let mounted = true;
		(api.getShortcuts?.() ?? Promise.resolve(null))
			.then((config) => {
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

	const resetShortcut = (key: "generalAssist" | "quickAsk" | "autocomplete") => {
		updateShortcut(key, DEFAULT_SHORTCUTS[key]);
	};

	return (
		shortcutsLoaded ? (
			<div className="flex flex-col gap-3">
				<Alert className="bg-muted/50 py-3 md:py-4">
					<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
					<AlertDescription className="text-xs md:text-sm">
						<p>Click a shortcut and press a new key combination to change it.</p>
					</AlertDescription>
				</Alert>
				<ShortcutRecorder
					value={shortcuts.generalAssist}
					onChange={(accel) => updateShortcut("generalAssist", accel)}
					onReset={() => resetShortcut("generalAssist")}
					defaultValue={DEFAULT_SHORTCUTS.generalAssist}
					label="General Assist"
					description="Launch SurfSense instantly from any application"
					icon={Rocket}
				/>
				<ShortcutRecorder
					value={shortcuts.quickAsk}
					onChange={(accel) => updateShortcut("quickAsk", accel)}
					onReset={() => resetShortcut("quickAsk")}
					defaultValue={DEFAULT_SHORTCUTS.quickAsk}
					label="Quick Assist"
					description="Select text anywhere, then ask AI to explain, rewrite, or act on it"
					icon={Zap}
				/>
				<ShortcutRecorder
					value={shortcuts.autocomplete}
					onChange={(accel) => updateShortcut("autocomplete", accel)}
					onReset={() => resetShortcut("autocomplete")}
					defaultValue={DEFAULT_SHORTCUTS.autocomplete}
					label="Extreme Assist"
					description="AI drafts text using your screen context and knowledge base"
					icon={BrainCog}
				/>
			</div>
		) : (
			<div className="flex justify-center py-4">
				<Spinner size="sm" />
			</div>
		)
	);
}
