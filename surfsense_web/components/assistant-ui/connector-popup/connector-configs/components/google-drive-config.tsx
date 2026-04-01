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
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
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
import { type PickerResult, useGooglePicker } from "@/hooks/use-google-picker";
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

const DEFAULT_INDEXING_OPTIONS: IndexingOptions = {
	max_files_per_folder: 100,
	incremental_sync: true,
	include_subfolders: true,
};

function getFileIconFromName(fileName: string, className: string = "size-3.5 shrink-0") {
	const lowerName = fileName.toLowerCase();
	if (
		lowerName.endsWith(".xlsx") ||
		lowerName.endsWith(".xls") ||
		lowerName.endsWith(".csv") ||
		lowerName.includes("spreadsheet")
	) {
		return <FileSpreadsheet className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".pptx") ||
		lowerName.endsWith(".ppt") ||
		lowerName.includes("presentation")
	) {
		return <Presentation className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".docx") ||
		lowerName.endsWith(".doc") ||
		lowerName.endsWith(".txt") ||
		lowerName.includes("document") ||
		lowerName.includes("word") ||
		lowerName.includes("text")
	) {
		return <FileText className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".png") ||
		lowerName.endsWith(".jpg") ||
		lowerName.endsWith(".jpeg") ||
		lowerName.endsWith(".gif") ||
		lowerName.endsWith(".webp") ||
		lowerName.endsWith(".svg")
	) {
		return <Image className={`${className} text-muted-foreground`} />;
	}
	return <File className={`${className} text-muted-foreground`} />;
}

export const GoogleDriveConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	const existingFolders = (connector.config?.selected_folders as SelectedItem[] | undefined) || [];
	const existingFiles = (connector.config?.selected_files as SelectedItem[] | undefined) || [];
	const existingIndexingOptions =
		(connector.config?.indexing_options as IndexingOptions | undefined) || DEFAULT_INDEXING_OPTIONS;

	const [selectedFolders, setSelectedFolders] = useState<SelectedItem[]>(existingFolders);
	const [selectedFiles, setSelectedFiles] = useState<SelectedItem[]>(existingFiles);
	const [indexingOptions, setIndexingOptions] = useState<IndexingOptions>(existingIndexingOptions);

	const updateConfig = (
		folders: SelectedItem[],
		files: SelectedItem[],
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

	const handlePicked = useCallback(
		(result: PickerResult) => {
			const folders = result.folders.map((f) => ({ id: f.id, name: f.name }));
			const files = result.files.map((f) => ({ id: f.id, name: f.name }));
			setSelectedFolders(folders);
			setSelectedFiles(files);
			updateConfig(folders, files, indexingOptions);
		},
		// eslint-disable-next-line react-hooks/exhaustive-deps
		[indexingOptions, connector.config]
	);

	const {
		openPicker,
		loading: pickerLoading,
		error: pickerError,
	} = useGooglePicker({
		connectorId: connector.id,
		onPicked: handlePicked,
	});

	const isAuthExpired =
		connector.config?.auth_expired === true ||
		(!!pickerError && pickerError.toLowerCase().includes("authentication expired"));

	const handleIndexingOptionChange = (key: keyof IndexingOptions, value: number | boolean) => {
		const newOptions = { ...indexingOptions, [key]: value };
		setIndexingOptions(newOptions);
		updateConfig(selectedFolders, selectedFiles, newOptions);
	};

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
									<FolderClosed className="size-3.5 shrink-0 text-muted-foreground" />
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

				<Button
					type="button"
					variant="outline"
					onClick={openPicker}
					disabled={pickerLoading || isAuthExpired}
					className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-white/10 text-xs sm:text-sm h-8 sm:h-9"
				>
					{pickerLoading && <Spinner size="xs" className="mr-1.5" />}
					{totalSelected > 0 ? "Change Selection" : "Select from Google Drive"}
				</Button>

				{isAuthExpired && (
					<p className="text-xs text-amber-600 dark:text-amber-500">
						Your Google Drive authentication has expired. Please re-authenticate using the button
						below.
					</p>
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
