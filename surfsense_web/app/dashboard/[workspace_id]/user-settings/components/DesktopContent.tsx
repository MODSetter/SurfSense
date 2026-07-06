"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import type { SearchSpace } from "@/contracts/types/workspace.types";
import { useElectronAPI } from "@/hooks/use-platform";
import { searchSpacesApiService } from "@/lib/apis/workspaces-api.service";

export function DesktopContent() {
	const api = useElectronAPI();
	const [loading, setLoading] = useState(true);

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
			api.getActiveSearchSpace?.() ?? Promise.resolve(null),
			searchSpacesApiService.getSearchSpaces(),
			hasAutoLaunchApi ? api.getAutoLaunch() : Promise.resolve(null),
		])
			.then(([spaceId, spaces, autoLaunch]) => {
				if (!mounted) return;
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
			<div className="flex flex-col gap-4 md:gap-6">
				<section>
					<div className="flex flex-col gap-2 pb-2 md:pb-3">
						<Skeleton className="h-6 w-48 bg-accent" />
						<Skeleton className="h-4 w-full max-w-2xl bg-accent" />
					</div>
					<Skeleton className="h-10 w-full bg-accent" />
				</section>

				<Separator className="bg-border" />

				<section>
					<div className="flex flex-col gap-2 pb-2 md:pb-3">
						<Skeleton className="h-6 w-44 bg-accent" />
						<Skeleton className="h-4 w-full max-w-3xl bg-accent" />
					</div>
					<div className="flex flex-col gap-3">
						<Skeleton className="h-20 w-full bg-accent" />
						<Skeleton className="h-20 w-full bg-accent" />
					</div>
				</section>
			</div>
		);
	}

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
		<div className="flex flex-col gap-4 md:gap-6">
			<section>
				<div className="pb-2 md:pb-3">
					<h2 className="text-base md:text-lg font-semibold">Default Search Space</h2>
					<p className="text-xs md:text-sm text-muted-foreground">
						Choose which search space General Assist, Screenshot Assist, and Quick Assist use by
						default.
					</p>
				</div>
				<div>
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
				</div>
			</section>

			<Separator className="bg-border" />

			<section>
				<div className="pb-2 md:pb-3">
					<h2 className="text-base md:text-lg font-semibold flex items-center gap-2">
						Launch on Startup
					</h2>
					<p className="text-xs md:text-sm text-muted-foreground">
						Automatically start SurfSense when you sign in to your computer so global shortcuts and
						folder sync are always available.
					</p>
				</div>
				<div className="flex flex-col gap-3">
					<div className="flex items-center justify-between rounded-lg bg-accent p-4">
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
					<div className="flex items-center justify-between rounded-lg bg-accent p-4">
						<div className="space-y-0.5">
							<Label
								htmlFor="auto-launch-hidden-toggle"
								className="text-sm font-medium cursor-pointer"
							>
								Start minimized to tray
							</Label>
							<p className="text-xs text-muted-foreground">
								Skip the main window on boot. SurfSense lives in the system tray until you need it.
							</p>
						</div>
						<Switch
							id="auto-launch-hidden-toggle"
							checked={autoLaunchHidden}
							onCheckedChange={handleAutoLaunchHiddenToggle}
							disabled={!autoLaunchSupported || !autoLaunchEnabled}
						/>
					</div>
				</div>
			</section>
		</div>
	);
}
