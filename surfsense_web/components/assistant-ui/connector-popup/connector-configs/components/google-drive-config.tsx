"use client";

import {
	File,
	FileSpreadsheet,
	FileText,
	FolderClosed,
	Image,
	Presentation,
	X,
} from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { GoogleDriveFolderTree } from "@/components/connectors/google-drive-folder-tree";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { ConnectorConfigProps } from "../index";

interface SelectedFolder {
	id: string;
	name: string;
}

interface IndexingOptions {
	max_files_per_folder: number;
	incremental_sync: boolean;
	include_subfolders: boolean;
}

const DEFAULT_INDEXING_OPTIONS: IndexingOptions = {
	max_files_per_folder: 100,
	incremental_sync: true,
	include_subfolders: true,
};

// Helper to get appropriate icon for file type based on file name
function getFileIconFromName(fileName: string, className: string = "size-3.5 shrink-0") {
	const lowerName = fileName.toLowerCase();
	// Spreadsheets
	if (
		lowerName.endsWith(".xlsx") ||
		lowerName.endsWith(".xls") ||
		lowerName.endsWith(".csv") ||
		lowerName.includes("spreadsheet")
	) {
		return <FileSpreadsheet className={`${className} text-green-500`} />;
	}
	// Presentations
	if (
		lowerName.endsWith(".pptx") ||
		lowerName.endsWith(".ppt") ||
		lowerName.includes("presentation")
	) {
		return <Presentation className={`${className} text-orange-500`} />;
	}
	// Documents (word, text only - not PDF)
	if (
		lowerName.endsWith(".docx") ||
		lowerName.endsWith(".doc") ||
		lowerName.endsWith(".txt") ||
		lowerName.includes("document") ||
		lowerName.includes("word") ||
		lowerName.includes("text")
	) {
		return <FileText className={`${className} text-gray-500`} />;
	}
	// Images
	if (
		lowerName.endsWith(".png") ||
		lowerName.endsWith(".jpg") ||
		lowerName.endsWith(".jpeg") ||
		lowerName.endsWith(".gif") ||
		lowerName.endsWith(".webp") ||
		lowerName.endsWith(".svg")
	) {
		return <Image className={`${className} text-purple-500`} />;
	}
	// Default (including PDF)
	return <File className={`${className} text-gray-500`} />;
}

export const GoogleDriveConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	// Initialize with existing selected folders and files from connector config
	const existingFolders =
		(connector.config?.selected_folders as SelectedFolder[] | undefined) || [];
	const existingFiles = (connector.config?.selected_files as SelectedFolder[] | undefined) || [];
	const existingIndexingOptions =
		(connector.config?.indexing_options as IndexingOptions | undefined) || DEFAULT_INDEXING_OPTIONS;

	const [selectedFolders, setSelectedFolders] = useState<SelectedFolder[]>(existingFolders);
	const [selectedFiles, setSelectedFiles] = useState<SelectedFolder[]>(existingFiles);
	const [showFolderSelector, setShowFolderSelector] = useState(false);
	const [indexingOptions, setIndexingOptions] = useState<IndexingOptions>(existingIndexingOptions);

	// Update selected folders and files when connector config changes
	useEffect(() => {
		const folders = (connector.config?.selected_folders as SelectedFolder[] | undefined) || [];
		const files = (connector.config?.selected_files as SelectedFolder[] | undefined) || [];
		const options =
			(connector.config?.indexing_options as IndexingOptions | undefined) ||
			DEFAULT_INDEXING_OPTIONS;
		setSelectedFolders(folders);
		setSelectedFiles(files);
		setIndexingOptions(options);
	}, [connector.config]);

	const updateConfig = (
		folders: SelectedFolder[],
		files: SelectedFolder[],
		options: IndexingOptions
	) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				selected_folders: folders,
				selected_files: files,
				indexing_options: options,
			});
		}
	};

	const handleSelectFolders = (folders: SelectedFolder[]) => {
		setSelectedFolders(folders);
		updateConfig(folders, selectedFiles, indexingOptions);
	};

	const handleSelectFiles = (files: SelectedFolder[]) => {
		setSelectedFiles(files);
		updateConfig(selectedFolders, files, indexingOptions);
	};

	const handleIndexingOptionChange = (key: keyof IndexingOptions, value: number | boolean) => {
		const newOptions = { ...indexingOptions, [key]: value };
		setIndexingOptions(newOptions);
		updateConfig(selectedFolders, selectedFiles, newOptions);
	};

	const handleRemoveFolder = (folderId: string) => {
		const newFolders = selectedFolders.filter((folder) => folder.id !== folderId);
		setSelectedFolders(newFolders);
		updateConfig(newFolders, selectedFiles, indexingOptions);
	};

	const handleRemoveFile = (fileId: string) => {
		const newFiles = selectedFiles.filter((file) => file.id !== fileId);
		setSelectedFiles(newFiles);
		updateConfig(selectedFolders, newFiles, indexingOptions);
	};

	const totalSelected = selectedFolders.length + selectedFiles.length;

	return (
		<div className="space-y-4">
			{/* Folder & File Selection */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Folder & File Selection</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Select specific folders and/or individual files to index.
					</p>
				</div>

				{totalSelected > 0 && (
					<div className="p-2 sm:p-3 bg-muted rounded-lg text-xs sm:text-sm space-y-1 sm:space-y-2">
						<p className="font-medium">
							Selected {totalSelected} item{totalSelected > 1 ? "s" : ""}: {(() => {
								const parts: string[] = [];
								if (selectedFolders.length > 0) {
									parts.push(
										`${selectedFolders.length} folder${selectedFolders.length > 1 ? "s" : ""}`
									);
								}
								if (selectedFiles.length > 0) {
									parts.push(`${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""}`);
								}
								return parts.length > 0 ? `(${parts.join(", ")})` : "";
							})()}
						</p>
						<div className="max-h-20 sm:max-h-24 overflow-y-auto space-y-1">
							{selectedFolders.map((folder) => (
								<div
									key={folder.id}
									className="text-xs sm:text-sm text-muted-foreground truncate flex items-center gap-1.5"
									title={folder.name}
								>
									<FolderClosed className="size-3.5 shrink-0 text-gray-500" />
									<span className="flex-1 truncate">{folder.name}</span>
									<button
										type="button"
										onClick={() => handleRemoveFolder(folder.id)}
										className="shrink-0 p-0.5 hover:bg-muted-foreground/20 rounded transition-colors"
										aria-label={`Remove ${folder.name}`}
									>
										<X className="size-3.5" />
									</button>
								</div>
							))}
							{selectedFiles.map((file) => (
								<div
									key={file.id}
									className="text-xs sm:text-sm text-muted-foreground truncate flex items-center gap-1.5"
									title={file.name}
								>
									{getFileIconFromName(file.name)}
									<span className="flex-1 truncate">{file.name}</span>
									<button
										type="button"
										onClick={() => handleRemoveFile(file.id)}
										className="shrink-0 p-0.5 hover:bg-muted-foreground/20 rounded transition-colors"
										aria-label={`Remove ${file.name}`}
									>
										<X className="size-3.5" />
									</button>
								</div>
							))}
						</div>
					</div>
				)}

				{showFolderSelector ? (
					<div className="space-y-2 sm:space-y-3">
						<GoogleDriveFolderTree
							connectorId={connector.id}
							selectedFolders={selectedFolders}
							onSelectFolders={handleSelectFolders}
							selectedFiles={selectedFiles}
							onSelectFiles={handleSelectFiles}
						/>
						<Button
							type="button"
							variant="outline"
							size="sm"
							onClick={() => setShowFolderSelector(false)}
							className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-white/10 text-xs sm:text-sm h-8 sm:h-9"
						>
							Done Selecting
						</Button>
					</div>
				) : (
					<Button
						type="button"
						variant="outline"
						onClick={() => setShowFolderSelector(true)}
						className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-white/10 text-xs sm:text-sm h-8 sm:h-9"
					>
						{totalSelected > 0 ? "Change Selection" : "Select Folders & Files"}
					</Button>
				)}
			</div>

			{/* Indexing Options */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">Indexing Options</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Configure how files are indexed from your Google Drive.
					</p>
				</div>

				{/* Max files per folder */}
				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="max-files" className="text-sm font-medium">
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
								id="max-files"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select limit" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="50" className="text-xs sm:text-sm">
									50 files
								</SelectItem>
								<SelectItem value="100" className="text-xs sm:text-sm">
									100 files
								</SelectItem>
								<SelectItem value="250" className="text-xs sm:text-sm">
									250 files
								</SelectItem>
								<SelectItem value="500" className="text-xs sm:text-sm">
									500 files
								</SelectItem>
								<SelectItem value="1000" className="text-xs sm:text-sm">
									1000 files
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* Incremental sync toggle */}
				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="incremental-sync" className="text-sm font-medium">
							Incremental sync
						</Label>
						<p className="text-xs text-muted-foreground">
							Only sync changes since last index (faster). Disable for a full re-index.
						</p>
					</div>
					<Switch
						id="incremental-sync"
						checked={indexingOptions.incremental_sync}
						onCheckedChange={(checked) => handleIndexingOptionChange("incremental_sync", checked)}
					/>
				</div>

				{/* Include subfolders toggle */}
				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="include-subfolders" className="text-sm font-medium">
							Include subfolders
						</Label>
						<p className="text-xs text-muted-foreground">
							Recursively index files in subfolders of selected folders
						</p>
					</div>
					<Switch
						id="include-subfolders"
						checked={indexingOptions.include_subfolders}
						onCheckedChange={(checked) => handleIndexingOptionChange("include_subfolders", checked)}
					/>
				</div>
			</div>
		</div>
	);
};
