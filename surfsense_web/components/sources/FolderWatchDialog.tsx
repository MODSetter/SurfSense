"use client";

import { FolderOpen, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";

interface SelectedFolder {
	path: string;
	name: string;
}

interface FolderWatchDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: number;
	onSuccess?: () => void;
}

const DEFAULT_EXCLUDE_PATTERNS = [
	".git",
	"node_modules",
	"__pycache__",
	".DS_Store",
	".obsidian",
	".trash",
];

export function FolderWatchDialog({
	open,
	onOpenChange,
	searchSpaceId,
	onSuccess,
}: FolderWatchDialogProps) {
	const [selectedFolder, setSelectedFolder] = useState<SelectedFolder | null>(null);
	const [shouldSummarize, setShouldSummarize] = useState(false);
	const [submitting, setSubmitting] = useState(false);

	const supportedExtensions = useMemo(
		() => Array.from(getSupportedExtensionsSet()),
		[]
	);

	const handleSelectFolder = useCallback(async () => {
		const api = window.electronAPI;
		if (!api?.selectFolder) return;

		const folderPath = await api.selectFolder();
		if (!folderPath) return;

		const folderName =
			folderPath.split("/").pop() || folderPath.split("\\").pop() || folderPath;
		setSelectedFolder({ path: folderPath, name: folderName });
	}, []);

	const handleSubmit = useCallback(async () => {
		if (!selectedFolder) return;
		const api = window.electronAPI;
		if (!api) return;

		setSubmitting(true);
		try {
			const result = await documentsApiService.folderIndex(searchSpaceId, {
				folder_path: selectedFolder.path,
				folder_name: selectedFolder.name,
				search_space_id: searchSpaceId,
				enable_summary: shouldSummarize,
				file_extensions: supportedExtensions,
			});

			const rootFolderId =
				(result as { root_folder_id?: number })?.root_folder_id ?? null;

			await api.addWatchedFolder({
				path: selectedFolder.path,
				name: selectedFolder.name,
				excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
				fileExtensions: supportedExtensions,
				rootFolderId,
				searchSpaceId,
				active: true,
			});

			toast.success(`Watching folder: ${selectedFolder.name}`);
			setSelectedFolder(null);
			setShouldSummarize(false);
			onOpenChange(false);
			onSuccess?.();
		} catch (err) {
			toast.error((err as Error)?.message || "Failed to watch folder");
		} finally {
			setSubmitting(false);
		}
	}, [selectedFolder, searchSpaceId, shouldSummarize, supportedExtensions, onOpenChange, onSuccess]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen && !submitting) {
				setSelectedFolder(null);
				setShouldSummarize(false);
			}
			onOpenChange(nextOpen);
		},
		[onOpenChange, submitting]
	);

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle>Watch Local Folder</DialogTitle>
					<DialogDescription>
						Select a folder to sync and watch for changes.
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-3 pt-2">
					{selectedFolder ? (
						<div className="flex items-center gap-2 py-1.5 px-2 rounded-md bg-slate-400/5 dark:bg-white/5">
							<FolderOpen className="h-4 w-4 text-primary shrink-0" />
							<div className="min-w-0 flex-1">
								<p className="text-sm font-medium truncate">
									{selectedFolder.name}
								</p>
								<p className="text-xs text-muted-foreground truncate">
									{selectedFolder.path}
								</p>
							</div>
							<Button
								variant="ghost"
								size="icon"
								className="h-7 w-7 shrink-0"
								onClick={() => setSelectedFolder(null)}
								disabled={submitting}
							>
								<X className="h-3.5 w-3.5" />
							</Button>
						</div>
					) : (
						<button
							type="button"
							onClick={handleSelectFolder}
							className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/30 py-8 text-sm text-muted-foreground transition-colors hover:border-foreground/50 hover:text-foreground"
						>
							Browse for a folder
						</button>
					)}

					{selectedFolder && (
						<>
							<div className="flex items-center justify-between rounded-lg bg-slate-400/5 dark:bg-white/5 p-3">
								<div className="space-y-0.5">
									<p className="font-medium text-sm">Enable AI Summary</p>
									<p className="text-xs text-muted-foreground">
										Improves search quality but adds latency
									</p>
								</div>
								<Switch
									checked={shouldSummarize}
									onCheckedChange={setShouldSummarize}
								/>
							</div>

							<Button
								className="w-full relative"
								onClick={handleSubmit}
								disabled={submitting}
							>
								<span className={submitting ? "invisible" : ""}>
									Sync &amp; Watch for Changes
								</span>
								{submitting && (
									<span className="absolute inset-0 flex items-center justify-center">
										<Spinner size="sm" />
									</span>
								)}
							</Button>
						</>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}
