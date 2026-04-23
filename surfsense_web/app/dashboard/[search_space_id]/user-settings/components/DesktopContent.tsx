"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type { SearchSpace } from "@/contracts/types/search-space.types";
import { useElectronAPI } from "@/hooks/use-platform";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";

export function DesktopContent() {
	const api = useElectronAPI();
	const [loading, setLoading] = useState(true);
	const [enabled, setEnabled] = useState(true);

	const [searchSpaces, setSearchSpaces] = useState<SearchSpace[]>([]);
	const [activeSpaceId, setActiveSpaceId] = useState<string | null>(null);

	const [autoLaunchEnabled, setAutoLaunchEnabled] = useState(false);
	const [autoLaunchHidden, setAutoLaunchHidden] = useState(true);
	const [autoLaunchSupported, setAutoLaunchSupported] = useState(false);

	useEffect(() => {
		if (!api) {
			setLoading(false);
			return;
		}

		let mounted = true;
		const hasAutoLaunchApi =
			typeof api.getAutoLaunch === "function" && typeof api.setAutoLaunch === "function";
		setAutoLaunchSupported(hasAutoLaunchApi);

		Promise.all([
			api.getAutocompleteEnabled(),
			api.getActiveSearchSpace?.() ?? Promise.resolve(null),
			searchSpacesApiService.getSearchSpaces(),
			hasAutoLaunchApi ? api.getAutoLaunch() : Promise.resolve(null),
		])
			.then(([autoEnabled, spaceId, spaces, autoLaunch]) => {
				if (!mounted) return;
				setEnabled(autoEnabled);
				setActiveSpaceId(spaceId);
				if (spaces) setSearchSpaces(spaces);
				if (autoLaunch) {
					setAutoLaunchEnabled(autoLaunch.enabled);
					setAutoLaunchHidden(autoLaunch.openAsHidden);
					setAutoLaunchSupported(autoLaunch.supported);
				}
				setLoading(false);
			})
			.catch(() => {
				if (!mounted) return;
				setLoading(false);
			});

		return () => {
			mounted = false;
		};
	}, [api]);

	if (!api) {
		return (
			<div className="flex flex-col items-center justify-center py-12 text-center">
				<p className="text-sm text-muted-foreground">
					App preferences are only available in the SurfSense desktop app.
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

	const handleAutoLaunchToggle = async (checked: boolean) => {
		if (!autoLaunchSupported || !api.setAutoLaunch) {
			toast.error("Please update the desktop app to configure launch on startup");
			return;
		}
		setAutoLaunchEnabled(checked);
		try {
			const next = await api.setAutoLaunch(checked, autoLaunchHidden);
			if (next) {
				setAutoLaunchEnabled(next.enabled);
				setAutoLaunchHidden(next.openAsHidden);
				setAutoLaunchSupported(next.supported);
			}
			toast.success(checked ? "SurfSense will launch on startup" : "Launch on startup disabled");
		} catch {
			setAutoLaunchEnabled(!checked);
			toast.error("Failed to update launch on startup");
		}
	};

	const handleAutoLaunchHiddenToggle = async (checked: boolean) => {
		if (!autoLaunchSupported || !api.setAutoLaunch) {
			toast.error("Please update the desktop app to configure startup behavior");
			return;
		}
		setAutoLaunchHidden(checked);
		try {
			await api.setAutoLaunch(autoLaunchEnabled, checked);
		} catch {
			setAutoLaunchHidden(!checked);
			toast.error("Failed to update startup behavior");
		}
	};

	const handleSearchSpaceChange = (value: string) => {
		setActiveSpaceId(value);
		api.setActiveSearchSpace?.(value);
		toast.success("Default search space updated");
	};

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Default Search Space */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Default Search Space</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Choose which search space General Assist, Quick Assist, and Extreme Assist operate
						against.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
					{searchSpaces.length > 0 ? (
						<Select value={activeSpaceId ?? undefined} onValueChange={handleSearchSpaceChange}>
							<SelectTrigger className="w-full">
								<SelectValue placeholder="Select a search space" />
							</SelectTrigger>
							<SelectContent>
								{searchSpaces.map((space) => (
									<SelectItem key={space.id} value={String(space.id)}>
										{space.name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					) : (
						<p className="text-sm text-muted-foreground">
							No search spaces found. Create one first.
						</p>
					)}
				</CardContent>
			</Card>

			{/* Launch on Startup */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg flex items-center gap-2">
						Launch on Startup
					</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Automatically start SurfSense when you sign in to your computer so global shortcuts and
						folder sync are always available.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6 space-y-3">
					<div className="flex items-center justify-between rounded-lg border p-4">
						<div className="space-y-0.5">
							<Label htmlFor="auto-launch-toggle" className="text-sm font-medium cursor-pointer">
								Open SurfSense at login
							</Label>
							<p className="text-xs text-muted-foreground">
								{autoLaunchSupported
									? "Adds SurfSense to your system's login items."
									: "Only available in the packaged desktop app."}
							</p>
						</div>
						<Switch
							id="auto-launch-toggle"
							checked={autoLaunchEnabled}
							onCheckedChange={handleAutoLaunchToggle}
							disabled={!autoLaunchSupported}
						/>
					</div>
					<div className="flex items-center justify-between rounded-lg border p-4">
						<div className="space-y-0.5">
							<Label
								htmlFor="auto-launch-hidden-toggle"
								className="text-sm font-medium cursor-pointer"
							>
								Start minimized to tray
							</Label>
							<p className="text-xs text-muted-foreground">
								Skip the main window on boot — SurfSense lives in the system tray until you need it.
							</p>
						</div>
						<Switch
							id="auto-launch-hidden-toggle"
							checked={autoLaunchHidden}
							onCheckedChange={handleAutoLaunchHiddenToggle}
							disabled={!autoLaunchSupported || !autoLaunchEnabled}
						/>
					</div>
				</CardContent>
			</Card>

			{/* Extreme Assist Toggle */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Extreme Assist</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Get inline writing suggestions powered by your knowledge base as you type in any app.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
					<div className="flex items-center justify-between rounded-lg border p-4">
						<div className="space-y-0.5">
							<Label htmlFor="autocomplete-toggle" className="text-sm font-medium cursor-pointer">
								Enable Extreme Assist
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
