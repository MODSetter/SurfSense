"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";
import { type FolderSyncProgress, uploadFolderScan } from "@/lib/folder-sync-upload";

export interface SelectedFolder {
	path: string;
	name: string;
}

interface FolderWatchDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: number;
	onSuccess?: () => void;
	initialFolder?: SelectedFolder | null;
}

export const DEFAULT_EXCLUDE_PATTERNS = [
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
	initialFolder,
}: FolderWatchDialogProps) {
	const [selectedFolder, setSelectedFolder] = useState<SelectedFolder | null>(null);
	const [shouldSummarize, setShouldSummarize] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [progress, setProgress] = useState<FolderSyncProgress | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	useEffect(() => {
		if (open && initialFolder) {
			setSelectedFolder(initialFolder);
		}
	}, [open, initialFolder]);

	const supportedExtensions = useMemo(() => Array.from(getSupportedExtensionsSet()), []);

	const handleSelectFolder = useCallback(async () => {
		const api = window.electronAPI;
		if (!api?.selectFolder) return;

		const folderPath = await api.selectFolder();
		if (!folderPath) return;

		const folderName = folderPath.split(/[/\\]/).pop() || folderPath;
		setSelectedFolder({ path: folderPath, name: folderName });
	}, []);

	const handleCancel = useCallback(() => {
		abortRef.current?.abort();
	}, []);

	const handleSubmit = useCallback(async () => {
		if (!selectedFolder) return;
		const api = window.electronAPI;
		if (!api) return;

		const controller = new AbortController();
		abortRef.current = controller;
		setSubmitting(true);
		setProgress(null);

		try {
			const rootFolderId = await uploadFolderScan({
				folderPath: selectedFolder.path,
				folderName: selectedFolder.name,
				searchSpaceId,
				excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
				fileExtensions: supportedExtensions,
				enableSummary: shouldSummarize,
				onProgress: setProgress,
				signal: controller.signal,
			});

			await api.addWatchedFolder({
				path: selectedFolder.path,
				name: selectedFolder.name,
				excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
				fileExtensions: supportedExtensions,
				rootFolderId: rootFolderId ?? null,
				searchSpaceId,
				active: true,
			});

			toast.success(`Watching folder: ${selectedFolder.name}`);
			setSelectedFolder(null);
			setShouldSummarize(false);
			setProgress(null);
			onOpenChange(false);
			onSuccess?.();
		} catch (err) {
			if ((err as Error)?.name === "AbortError") {
				toast.info("Folder sync cancelled. Partial progress was saved.");
			} else {
				toast.error((err as Error)?.message || "Failed to watch folder");
			}
		} finally {
			abortRef.current = null;
			setSubmitting(false);
			setProgress(null);
		}
	}, [
		selectedFolder,
		searchSpaceId,
		shouldSummarize,
		supportedExtensions,
		onOpenChange,
		onSuccess,
	]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen && !submitting) {
				setSelectedFolder(null);
				setShouldSummarize(false);
				setProgress(null);
			}
			onOpenChange(nextOpen);
		},
		[onOpenChange, submitting]
	);

	const progressLabel = useMemo(() => {
		if (!progress) return null;
		switch (progress.phase) {
			case "listing":
				return "Scanning folder...";
			case "checking":
				return `Checking ${progress.total} file(s)...`;
			case "uploading":
				return `Uploading ${progress.uploaded}/${progress.total} file(s)...`;
			case "finalizing":
				return "Finalizing...";
			case "done":
				return "Done!";
			default:
				return null;
		}
	}, [progress]);

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="sm:max-w-md select-none">
				<DialogHeader>
					<DialogTitle>Watch Local Folder</DialogTitle>
					<DialogDescription>Select a folder to sync and watch for changes.</DialogDescription>
				</DialogHeader>

				<div className="space-y-3 pt-2 min-h-[13rem]">
					{selectedFolder ? (
						<div className="flex items-center gap-2 py-1.5 pl-4 pr-2 rounded-md bg-slate-400/5 dark:bg-white/5 overflow-hidden">
							<div className="min-w-0 flex-1 select-text">
								<p className="text-sm font-medium break-all line-clamp-2">{selectedFolder.name}</p>
								<p className="text-xs text-muted-foreground break-all line-clamp-2">
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
								<Switch checked={shouldSummarize} onCheckedChange={setShouldSummarize} />
							</div>

							{progressLabel && (
								<div className="rounded-lg bg-slate-400/5 dark:bg-white/5 px-3 py-2">
									<p className="text-xs text-muted-foreground">{progressLabel}</p>
									{progress && progress.phase === "uploading" && progress.total > 0 && (
										<div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden">
											<div
												className="h-full bg-primary rounded-full transition-[width] duration-300"
												style={{ width: `${Math.round((progress.uploaded / progress.total) * 100)}%` }}
											/>
										</div>
									)}
								</div>
							)}

							<div className="flex gap-2">
								{submitting ? (
									<>
										<Button variant="secondary" className="flex-1" onClick={handleCancel}>
											Cancel
										</Button>
										<Button className="flex-1 relative" disabled>
											<span className="invisible">Syncing...</span>
											<span className="absolute inset-0 flex items-center justify-center">
												<Spinner size="sm" />
											</span>
										</Button>
									</>
								) : (
									<Button className="w-full" onClick={handleSubmit}>
										Start Folder Sync
									</Button>
								)}
							</div>
						</>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}
