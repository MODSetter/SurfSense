"use client";

import {
	ChevronRight,
	File,
	FileSpreadsheet,
	FileText,
	FolderClosed,
	FolderOpen,
	Image,
	Presentation,
	X,
} from "lucide-react";
import type { FC } from "react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useAuth } from "@/context/AuthContext";
import type { ConnectorConfigProps } from "../index";

interface SelectedItem {
	id: string;
	name: string;
}

interface IndexingOptions {
	max_files_per_folder: number;
	incremental_sync: boolean;
	include_subfolders: boolean;
}

interface OneDriveItem {
	id: string;
	name: string;
	isFolder: boolean;
	size?: number;
	lastModifiedDateTime?: string;
	file?: { mimeType: string };
	folder?: { childCount: number };
	webUrl?: string;
}

const DEFAULT_INDEXING_OPTIONS: IndexingOptions = {
	max_files_per_folder: 100,
	incremental_sync: true,
	include_subfolders: true,
};

function getFileIconFromName(fileName: string, className = "size-3.5 shrink-0") {
	const lowerName = fileName.toLowerCase();
	if (lowerName.endsWith(".xlsx") || lowerName.endsWith(".xls") || lowerName.endsWith(".csv")) {
		return <FileSpreadsheet className={`${className} text-muted-foreground`} />;
	}
	if (lowerName.endsWith(".pptx") || lowerName.endsWith(".ppt")) {
		return <Presentation className={`${className} text-muted-foreground`} />;
	}
	if (lowerName.endsWith(".docx") || lowerName.endsWith(".doc") || lowerName.endsWith(".txt")) {
		return <FileText className={`${className} text-muted-foreground`} />;
	}
	if (/\.(png|jpe?g|gif|webp|svg)$/.test(lowerName)) {
		return <Image className={`${className} text-muted-foreground`} />;
	}
	return <File className={`${className} text-muted-foreground`} />;
}

export const OneDriveConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	const { authenticatedFetch } = useAuth();
	const existingFolders = (connector.config?.selected_folders as SelectedItem[] | undefined) || [];
	const existingFiles = (connector.config?.selected_files as SelectedItem[] | undefined) || [];
	const existingIndexingOptions =
		(connector.config?.indexing_options as IndexingOptions | undefined) || DEFAULT_INDEXING_OPTIONS;

	const [selectedFolders, setSelectedFolders] = useState<SelectedItem[]>(existingFolders);
	const [selectedFiles, setSelectedFiles] = useState<SelectedItem[]>(existingFiles);
	const [indexingOptions, setIndexingOptions] = useState<IndexingOptions>(existingIndexingOptions);

	const [browserOpen, setBrowserOpen] = useState(false);
	const [browseItems, setBrowseItems] = useState<OneDriveItem[]>([]);
	const [browseLoading, setBrowseLoading] = useState(false);
	const [browseError, setBrowseError] = useState<string | null>(null);
	const [breadcrumbs, setBreadcrumbs] = useState<{ id: string; name: string }[]>([
		{ id: "root", name: "My files" },
	]);

	useEffect(() => {
		const folders = (connector.config?.selected_folders as SelectedItem[] | undefined) || [];
		const files = (connector.config?.selected_files as SelectedItem[] | undefined) || [];
		const options =
			(connector.config?.indexing_options as IndexingOptions | undefined) || DEFAULT_INDEXING_OPTIONS;
		setSelectedFolders(folders);
		setSelectedFiles(files);
		setIndexingOptions(options);
	}, [connector.config]);

	const updateConfig = useCallback(
		(folders: SelectedItem[], files: SelectedItem[], options: IndexingOptions) => {
			if (onConfigChange) {
				onConfigChange({
					...connector.config,
					selected_folders: folders,
					selected_files: files,
					indexing_options: options,
				});
			}
		},
		[onConfigChange, connector.config],
	);

	const fetchFolderContents = useCallback(
		async (parentId: string) => {
			setBrowseLoading(true);
			setBrowseError(null);
			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const url = `${backendUrl}/api/v1/connectors/${connector.id}/onedrive/folders?parent_id=${encodeURIComponent(parentId)}`;
				const response = await authenticatedFetch(url);
				if (!response.ok) {
					const data = await response.json().catch(() => ({}));
					throw new Error(data.detail || `Failed to load folder contents (${response.status})`);
				}
				const data = await response.json();
				setBrowseItems(data.items || []);
			} catch (err: unknown) {
				const message = err instanceof Error ? err.message : "Failed to load folder contents";
				setBrowseError(message);
			} finally {
				setBrowseLoading(false);
			}
		},
		[connector.id, authenticatedFetch],
	);

	const handleOpenBrowser = useCallback(() => {
		setBrowserOpen(true);
		setBreadcrumbs([{ id: "root", name: "My files" }]);
		fetchFolderContents("root");
	}, [fetchFolderContents]);

	const handleNavigateFolder = useCallback(
		(folderId: string, folderName: string) => {
			setBreadcrumbs((prev) => [...prev, { id: folderId, name: folderName }]);
			fetchFolderContents(folderId);
		},
		[fetchFolderContents],
	);

	const handleBreadcrumbClick = useCallback(
		(index: number) => {
			const newBreadcrumbs = breadcrumbs.slice(0, index + 1);
			setBreadcrumbs(newBreadcrumbs);
			fetchFolderContents(newBreadcrumbs[newBreadcrumbs.length - 1].id);
		},
		[breadcrumbs, fetchFolderContents],
	);

	const isItemSelected = useCallback(
		(item: OneDriveItem) => {
			if (item.isFolder) {
				return selectedFolders.some((f) => f.id === item.id);
			}
			return selectedFiles.some((f) => f.id === item.id);
		},
		[selectedFolders, selectedFiles],
	);

	const handleToggleItem = useCallback(
		(item: OneDriveItem) => {
			if (item.isFolder) {
				const exists = selectedFolders.some((f) => f.id === item.id);
				const newFolders = exists
					? selectedFolders.filter((f) => f.id !== item.id)
					: [...selectedFolders, { id: item.id, name: item.name }];
				setSelectedFolders(newFolders);
				updateConfig(newFolders, selectedFiles, indexingOptions);
			} else {
				const exists = selectedFiles.some((f) => f.id === item.id);
				const newFiles = exists
					? selectedFiles.filter((f) => f.id !== item.id)
					: [...selectedFiles, { id: item.id, name: item.name }];
				setSelectedFiles(newFiles);
				updateConfig(selectedFolders, newFiles, indexingOptions);
			}
		},
		[selectedFolders, selectedFiles, indexingOptions, updateConfig],
	);

	const handleRemoveFolder = (folderId: string) => {
		const newFolders = selectedFolders.filter((f) => f.id !== folderId);
		setSelectedFolders(newFolders);
		updateConfig(newFolders, selectedFiles, indexingOptions);
	};

	const handleRemoveFile = (fileId: string) => {
		const newFiles = selectedFiles.filter((f) => f.id !== fileId);
		setSelectedFiles(newFiles);
		updateConfig(selectedFolders, newFiles, indexingOptions);
	};

	const handleIndexingOptionChange = (key: keyof IndexingOptions, value: number | boolean) => {
		const newOptions = { ...indexingOptions, [key]: value };
		setIndexingOptions(newOptions);
		updateConfig(selectedFolders, selectedFiles, newOptions);
	};

	const isAuthExpired = connector.config?.auth_expired === true;
	const totalSelected = selectedFolders.length + selectedFiles.length;

	return (
		<div className="space-y-4">
			{/* Folder & File Selection */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Folder & File Selection</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Browse and select specific folders and/or files to index from your OneDrive.
					</p>
				</div>

				{totalSelected > 0 && (
					<div className="p-2 sm:p-3 bg-muted rounded-lg text-xs sm:text-sm space-y-1 sm:space-y-2">
						<p className="font-medium">
							Selected {totalSelected} item{totalSelected > 1 ? "s" : ""}
						</p>
						<div className="max-h-20 sm:max-h-24 overflow-y-auto space-y-1">
							{selectedFolders.map((folder) => (
								<div
									key={folder.id}
									className="text-xs text-muted-foreground truncate flex items-center gap-1.5"
									title={folder.name}
								>
									<FolderClosed className="size-3.5 shrink-0 text-muted-foreground" />
									<span className="flex-1 truncate">{folder.name}</span>
									<button
										type="button"
										onClick={() => handleRemoveFolder(folder.id)}
										className="shrink-0 p-0.5 hover:bg-muted-foreground/20 rounded transition-colors"
									>
										<X className="size-3.5" />
									</button>
								</div>
							))}
							{selectedFiles.map((file) => (
								<div
									key={file.id}
									className="text-xs text-muted-foreground truncate flex items-center gap-1.5"
									title={file.name}
								>
									{getFileIconFromName(file.name)}
									<span className="flex-1 truncate">{file.name}</span>
									<button
										type="button"
										onClick={() => handleRemoveFile(file.id)}
										className="shrink-0 p-0.5 hover:bg-muted-foreground/20 rounded transition-colors"
									>
										<X className="size-3.5" />
									</button>
								</div>
							))}
						</div>
					</div>
				)}

				{!browserOpen ? (
					<Button
						type="button"
						variant="outline"
						onClick={handleOpenBrowser}
						disabled={isAuthExpired}
						className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-white/10 text-xs sm:text-sm h-8 sm:h-9"
					>
						{totalSelected > 0 ? "Change Selection" : "Browse OneDrive"}
					</Button>
				) : (
					<div className="rounded-lg border border-border bg-background">
						{/* Breadcrumbs */}
						<div className="flex items-center gap-1 px-3 py-2 border-b border-border text-xs overflow-x-auto">
							{breadcrumbs.map((crumb, index) => (
								<span key={crumb.id} className="flex items-center gap-1 shrink-0">
									{index > 0 && <ChevronRight className="size-3 text-muted-foreground" />}
									<button
										type="button"
										onClick={() => handleBreadcrumbClick(index)}
										className={`hover:underline ${
											index === breadcrumbs.length - 1
												? "font-medium text-foreground"
												: "text-muted-foreground"
										}`}
									>
										{crumb.name}
									</button>
								</span>
							))}
						</div>

						{/* File list */}
						<div className="max-h-48 overflow-y-auto">
							{browseLoading ? (
								<div className="flex items-center justify-center p-6">
									<Spinner size="sm" />
								</div>
							) : browseError ? (
								<div className="p-3 text-xs text-destructive">{browseError}</div>
							) : browseItems.length === 0 ? (
								<div className="p-3 text-xs text-muted-foreground">This folder is empty</div>
							) : (
								browseItems.map((item) => (
									<div
										key={item.id}
										className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/50 text-xs"
									>
										<Checkbox
											checked={isItemSelected(item)}
											onCheckedChange={() => handleToggleItem(item)}
											className="size-3.5"
										/>
										{item.isFolder ? (
											<button
												type="button"
												className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
												onClick={() => handleNavigateFolder(item.id, item.name)}
											>
												<FolderOpen className="size-3.5 shrink-0 text-muted-foreground" />
												<span className="truncate">{item.name}</span>
											</button>
										) : (
											<div className="flex items-center gap-1.5 flex-1 min-w-0">
												{getFileIconFromName(item.name)}
												<span className="truncate">{item.name}</span>
											</div>
										)}
									</div>
								))
							)}
						</div>

						<div className="px-3 py-2 border-t border-border flex justify-end">
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={() => setBrowserOpen(false)}
								className="text-xs h-7"
							>
								Done
							</Button>
						</div>
					</div>
				)}

				{isAuthExpired && (
					<p className="text-xs text-amber-600 dark:text-amber-500">
						Your OneDrive authentication has expired. Please re-authenticate using the button below.
					</p>
				)}
			</div>

			{/* Indexing Options */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Indexing Options</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Configure how files are indexed from your OneDrive.
					</p>
				</div>

				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="od-max-files" className="text-sm font-medium">
								Max files per folder
							</Label>
							<p className="text-xs text-muted-foreground">
								Maximum number of files to index from each folder
							</p>
						</div>
						<Select
							value={indexingOptions.max_files_per_folder.toString()}
							onValueChange={(value) =>
								handleIndexingOptionChange("max_files_per_folder", parseInt(value, 10))
							}
						>
							<SelectTrigger
								id="od-max-files"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select limit" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="50">50 files</SelectItem>
								<SelectItem value="100">100 files</SelectItem>
								<SelectItem value="250">250 files</SelectItem>
								<SelectItem value="500">500 files</SelectItem>
								<SelectItem value="1000">1000 files</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="od-incremental-sync" className="text-sm font-medium">
							Incremental sync
						</Label>
						<p className="text-xs text-muted-foreground">
							Only sync changes since last index (faster). Disable for a full re-index.
						</p>
					</div>
					<Switch
						id="od-incremental-sync"
						checked={indexingOptions.incremental_sync}
						onCheckedChange={(checked) => handleIndexingOptionChange("incremental_sync", checked)}
					/>
				</div>

				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="od-include-subfolders" className="text-sm font-medium">
							Include subfolders
						</Label>
						<p className="text-xs text-muted-foreground">
							Recursively index files in subfolders of selected folders
						</p>
					</div>
					<Switch
						id="od-include-subfolders"
						checked={indexingOptions.include_subfolders}
						onCheckedChange={(checked) => handleIndexingOptionChange("include_subfolders", checked)}
					/>
				</div>
			</div>
		</div>
	);
};
