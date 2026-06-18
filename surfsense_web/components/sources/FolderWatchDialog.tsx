"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useRuntimeConfig } from "@/components/providers/runtime-config";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { type FolderSyncProgress, uploadFolderScan } from "@/lib/folder-sync-upload";
import { getSupportedExtensionsSet } from "@/lib/supported-extensions";

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
	const [submitting, setSubmitting] = useState(false);
	const [progress, setProgress] = useState<FolderSyncProgress | null>(null);
	const abortRef = useRef<AbortController | null>(null);
	const { etlService } = useRuntimeConfig();

	useEffect(() => {
		if (open && initialFolder) {
			setSelectedFolder(initialFolder);
		}
	}, [open, initialFolder]);

	const supportedExtensions = useMemo(
		() => Array.from(getSupportedExtensionsSet(undefined, etlService)),
		[etlService]
	);

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
	}, [selectedFolder, searchSpaceId, supportedExtensions, onOpenChange, onSuccess]);

	const handleOpenChange = useCallback(
		(nextOpen: boolean) => {
			if (!nextOpen && !submitting) {
				setSelectedFolder(null);
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
			<DialogContent className="sm:max-w-md select-none p-0 gap-0 overflow-hidden [&>button]:opacity-80 [&>button]:hover:opacity-100 [&>button]:hover:bg-accent [&>button]:hover:text-accent-foreground">
				<DialogHeader className="px-4 sm:px-6 pt-5 sm:pt-6 pb-3">
					<DialogTitle className="text-lg sm:text-xl font-semibold tracking-tight">
						Watch Local Folder
					</DialogTitle>
					<DialogDescription className="text-xs sm:text-sm text-muted-foreground/80">
						Select a folder to sync and watch for changes
					</DialogDescription>
				</DialogHeader>

				<div className="flex flex-col gap-3 px-4 sm:px-6 pb-4 sm:pb-6 min-h-[17rem]">
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
						<Button
							variant="ghost"
							type="button"
							onClick={handleSelectFolder}
							className="h-auto flex-1 w-full gap-2 rounded-lg border-2 border-dashed border-muted-foreground/30 bg-transparent text-sm text-muted-foreground transition-colors hover:border-foreground/50 hover:bg-transparent hover:text-accent-foreground"
						>
							Browse for a folder
						</Button>
					)}

					{selectedFolder && (
						<>
							{progressLabel && (
								<div className="rounded-lg bg-slate-400/5 dark:bg-white/5 px-3 py-2">
									<p className="text-xs text-muted-foreground">{progressLabel}</p>
									{progress && progress.phase === "uploading" && progress.total > 0 && (
										<div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden">
											<div
												className="h-full bg-primary rounded-full transition-[width] duration-300"
												style={{
													width: `${Math.round((progress.uploaded / progress.total) * 100)}%`,
												}}
											/>
										</div>
									)}
								</div>
							)}

							<div className="flex gap-2 mt-auto">
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
