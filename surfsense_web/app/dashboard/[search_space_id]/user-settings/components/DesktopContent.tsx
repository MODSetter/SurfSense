"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";

export function DesktopContent() {
	const [isElectron, setIsElectron] = useState(false);
	const [loading, setLoading] = useState(true);
	const [enabled, setEnabled] = useState(true);

	useEffect(() => {
		if (!window.electronAPI) {
			setLoading(false);
			return;
		}
		setIsElectron(true);

		window.electronAPI.getAutocompleteEnabled().then((val) => {
			setEnabled(val);
			setLoading(false);
		});
	}, []);

	if (!isElectron) {
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
		await window.electronAPI!.setAutocompleteEnabled(checked);
	};

	return (
		<div className="space-y-4 md:space-y-6">
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
