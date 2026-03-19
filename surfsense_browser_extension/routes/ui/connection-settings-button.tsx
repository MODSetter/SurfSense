import { GearIcon } from "@radix-ui/react-icons";
import { useEffect, useState } from "react";
import { Button } from "~/routes/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "~/routes/ui/dialog";
import { Label } from "~/routes/ui/label";
import {
	DEFAULT_BACKEND_BASE_URL,
	getCustomBackendBaseUrl,
	normalizeBackendBaseUrl,
	setCustomBackendBaseUrl,
} from "~utils/backend-url";

type ConnectionSettingsButtonProps = {
	onSaved?: (changed: boolean) => void | Promise<void>;
};

export function ConnectionSettingsButton({ onSaved }: ConnectionSettingsButtonProps) {
	const [open, setOpen] = useState(false);
	const [customUrl, setCustomUrl] = useState("");
	const [savedUrl, setSavedUrl] = useState("");

	useEffect(() => {
		if (!open) {
			return;
		}

		const loadSettings = async () => {
			const normalized = await getCustomBackendBaseUrl();
			setCustomUrl(normalized || DEFAULT_BACKEND_BASE_URL);
			setSavedUrl(normalized);
		};

		loadSettings();
	}, [open]);

	const handleSave = async () => {
		const normalizedUrl = normalizeBackendBaseUrl(customUrl);
		const nextUrl = await setCustomBackendBaseUrl(
			normalizedUrl === DEFAULT_BACKEND_BASE_URL ? "" : normalizedUrl
		);
		const changed = nextUrl !== savedUrl;
		setSavedUrl(nextUrl);
		setCustomUrl(nextUrl || DEFAULT_BACKEND_BASE_URL);
		setOpen(false);

		if (onSaved) {
			await onSaved(changed);
		}
	};

	return (
		<>
			<Button
				variant="ghost"
				size="icon"
				onClick={() => setOpen(true)}
				className="rounded-full text-gray-400 hover:bg-gray-800 hover:text-white"
			>
				<GearIcon className="h-4 w-4" />
				<span className="sr-only">Connection settings</span>
			</Button>
			<Dialog open={open} onOpenChange={setOpen}>
				<DialogContent className="max-w-md border-gray-700 bg-gray-800 text-white">
					<DialogHeader>
						<DialogTitle>Connection Settings</DialogTitle>
						<DialogDescription className="text-gray-400">
							Leave blank to use the default NeoNote backend URL.
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-2">
						<Label htmlFor="backendBaseUrl" className="text-gray-300">
							Custom Backend URL
						</Label>
						<input
							id="backendBaseUrl"
							type="url"
							value={customUrl}
							onChange={(event) => setCustomUrl(event.target.value)}
							placeholder={DEFAULT_BACKEND_BASE_URL}
							className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
						/>
						<p className="text-xs text-gray-500">Default: {DEFAULT_BACKEND_BASE_URL}</p>
					</div>

					<DialogFooter className="gap-2">
						<Button
							type="button"
							variant="outline"
							onClick={() => setCustomUrl(DEFAULT_BACKEND_BASE_URL)}
							className="border-gray-700 bg-gray-900 text-gray-200 hover:bg-gray-700"
						>
							Use Default
						</Button>
						<Button
							type="button"
							onClick={handleSave}
							className="bg-teal-600 text-white hover:bg-teal-500"
						>
							Save
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</>
	);
}
