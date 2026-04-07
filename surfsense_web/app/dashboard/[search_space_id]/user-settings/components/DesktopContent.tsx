"use client";

import { Clipboard, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { DEFAULT_SHORTCUTS, ShortcutRecorder } from "@/components/desktop/shortcut-recorder";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useElectronAPI } from "@/hooks/use-platform";

export function DesktopContent() {
	const api = useElectronAPI();
	const [loading, setLoading] = useState(true);
	const [enabled, setEnabled] = useState(true);

	const [shortcuts, setShortcuts] = useState(DEFAULT_SHORTCUTS);
	const [shortcutsLoaded, setShortcutsLoaded] = useState(false);

	useEffect(() => {
		if (!api) {
			setLoading(false);
			setShortcutsLoaded(true);
			return;
		}

		let mounted = true;

		Promise.all([api.getAutocompleteEnabled(), api.getShortcuts?.() ?? Promise.resolve(null)])
			.then(([autoEnabled, config]) => {
				if (!mounted) return;
				setEnabled(autoEnabled);
				if (config) setShortcuts(config);
				setLoading(false);
				setShortcutsLoaded(true);
			})
			.catch(() => {
				if (!mounted) return;
				setLoading(false);
				setShortcutsLoaded(true);
			});

		return () => {
			mounted = false;
		};
	}, [api]);

	if (!api) {
		return (
			<div className="flex flex-col items-center justify-center py-12 text-center">
				<p className="text-sm text-muted-foreground">
					Desktop settings are only available in the SurfSense desktop app.
				</p>
			</div>
		);
	}

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	const handleToggle = async (checked: boolean) => {
		setEnabled(checked);
		await api.setAutocompleteEnabled(checked);
	};

	const updateShortcut = (key: "quickAsk" | "autocomplete", accelerator: string) => {
		setShortcuts((prev) => {
			const updated = { ...prev, [key]: accelerator };
			api.setShortcuts?.({ [key]: accelerator }).catch(() => {
				toast.error("Failed to update shortcut");
			});
			return updated;
		});
		toast.success("Shortcut updated");
	};

	const resetShortcut = (key: "quickAsk" | "autocomplete") => {
		updateShortcut(key, DEFAULT_SHORTCUTS[key]);
	};

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Keyboard Shortcuts */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Keyboard Shortcuts</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Customize the global keyboard shortcuts for desktop features.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
					{shortcutsLoaded ? (
						<div className="flex flex-col gap-3">
							<ShortcutRecorder
								value={shortcuts.quickAsk}
								onChange={(accel) => updateShortcut("quickAsk", accel)}
								onReset={() => resetShortcut("quickAsk")}
								defaultValue={DEFAULT_SHORTCUTS.quickAsk}
								label="Quick Ask"
								description="Copy selected text and ask AI about it"
								icon={Clipboard}
							/>
							<ShortcutRecorder
								value={shortcuts.autocomplete}
								onChange={(accel) => updateShortcut("autocomplete", accel)}
								onReset={() => resetShortcut("autocomplete")}
								defaultValue={DEFAULT_SHORTCUTS.autocomplete}
								label="Autocomplete"
								description="Get AI writing suggestions from a screenshot"
								icon={Sparkles}
							/>
							<p className="text-[11px] text-muted-foreground">
								Click a shortcut and press a new key combination to change it.
							</p>
						</div>
					) : (
						<div className="flex justify-center py-4">
							<Spinner size="sm" />
						</div>
					)}
				</CardContent>
			</Card>

			{/* Autocomplete Toggle */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Autocomplete</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Get inline writing suggestions powered by your knowledge base as you type in any app.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
					<div className="flex items-center justify-between rounded-lg border p-4">
						<div className="space-y-0.5">
							<Label htmlFor="autocomplete-toggle" className="text-sm font-medium cursor-pointer">
								Enable autocomplete
							</Label>
							<p className="text-xs text-muted-foreground">
								Show suggestions while typing in other applications.
							</p>
						</div>
						<Switch id="autocomplete-toggle" checked={enabled} onCheckedChange={handleToggle} />
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
