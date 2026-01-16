"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { GoogleDriveFolderTree } from "@/components/connectors/google-drive-folder-tree";
import { Alert, AlertDescription } from "@/components/ui/alert";
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

const MAX_FILES_OPTIONS = [
	{ value: "100", label: "100 files" },
	{ value: "250", label: "250 files" },
	{ value: "500", label: "500 files (default)" },
	{ value: "1000", label: "1,000 files" },
	{ value: "2500", label: "2,500 files" },
];

export const GoogleDriveConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	// Initialize with existing selected folders and files from connector config
	const existingFolders =
		(connector.config?.selected_folders as SelectedFolder[] | undefined) || [];
	const existingFiles = (connector.config?.selected_files as SelectedFolder[] | undefined) || [];
	const [selectedFolders, setSelectedFolders] = useState<SelectedFolder[]>(existingFolders);
	const [selectedFiles, setSelectedFiles] = useState<SelectedFolder[]>(existingFiles);
	const [showFolderSelector, setShowFolderSelector] = useState(false);

	// Indexing options state
	const [maxFiles, setMaxFiles] = useState<string>(
		(connector.config?.max_files as string | undefined) || "500"
	);
	const [useDeltaSync, setUseDeltaSync] = useState<boolean>(
		connector.config?.use_delta_sync !== false // Default to true
	);
	const [includeSubfolders, setIncludeSubfolders] = useState<boolean>(
		(connector.config?.include_subfolders as boolean | undefined) || false
	);

	// Update selected folders, files, and indexing options when connector config changes
	useEffect(() => {
		const folders = (connector.config?.selected_folders as SelectedFolder[] | undefined) || [];
		const files = (connector.config?.selected_files as SelectedFolder[] | undefined) || [];
		setSelectedFolders(folders);
		setSelectedFiles(files);
		setMaxFiles((connector.config?.max_files as string | undefined) || "500");
		setUseDeltaSync(connector.config?.use_delta_sync !== false);
		setIncludeSubfolders((connector.config?.include_subfolders as boolean | undefined) || false);
	}, [connector.config]);

	// Helper to update config with all current values
	const updateConfig = (updates: Record<string, unknown>) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				selected_folders: selectedFolders,
				selected_files: selectedFiles,
				max_files: maxFiles,
				use_delta_sync: useDeltaSync,
				include_subfolders: includeSubfolders,
				...updates,
			});
		}
	};

	const handleSelectFolders = (folders: SelectedFolder[]) => {
		setSelectedFolders(folders);
		updateConfig({ selected_folders: folders });
	};

	const handleSelectFiles = (files: SelectedFolder[]) => {
		setSelectedFiles(files);
		updateConfig({ selected_files: files });
	};

	const handleMaxFilesChange = (value: string) => {
		setMaxFiles(value);
		updateConfig({ max_files: value });
	};

	const handleDeltaSyncChange = (checked: boolean) => {
		setUseDeltaSync(checked);
		updateConfig({ use_delta_sync: checked });
	};

	const handleIncludeSubfoldersChange = (checked: boolean) => {
		setIncludeSubfolders(checked);
		updateConfig({ include_subfolders: checked });
	};

	const totalSelected = selectedFolders.length + selectedFiles.length;

	return (
		<>
		<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
			<div className="space-y-1 sm:space-y-2">
				<h3 className="font-medium text-sm sm:text-base">Folder & File Selection</h3>
				<p className="text-xs sm:text-sm text-muted-foreground">
					Select specific folders and/or individual files to index. Only files directly in each
					folder will be processed—subfolders must be selected separately.
				</p>
			</div>

			{totalSelected > 0 && (
				<div className="p-2 sm:p-3 bg-muted rounded-lg text-xs sm:text-sm space-y-1 sm:space-y-2">
					<p className="font-medium">
						Selected {totalSelected} item{totalSelected > 1 ? "s" : ""}:
						{selectedFolders.length > 0 &&
							` ${selectedFolders.length} folder${selectedFolders.length > 1 ? "s" : ""}`}
						{selectedFiles.length > 0 &&
							` ${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""}`}
					</p>
					<div className="max-h-20 sm:max-h-24 overflow-y-auto space-y-1">
						{selectedFolders.map((folder) => (
							<p
								key={folder.id}
								className="text-xs sm:text-sm text-muted-foreground truncate"
								title={folder.name}
							>
								📁 {folder.name}
							</p>
						))}
						{selectedFiles.map((file) => (
							<p
								key={file.id}
								className="text-xs sm:text-sm text-muted-foreground truncate"
								title={file.name}
							>
								📄 {file.name}
							</p>
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

			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center gap-2 [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0" />
				<AlertDescription className="text-[10px] sm:text-xs !pl-0">
					Folder and file selection is used when indexing. You can change this selection when you
					start indexing.
				</AlertDescription>
			</Alert>
		</div>

		{/* Indexing Options Section */}
		<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
			<div className="space-y-1 sm:space-y-2">
				<h3 className="font-medium text-sm sm:text-base">Indexing Options</h3>
				<p className="text-xs sm:text-sm text-muted-foreground">
					Configure how files are indexed from your Google Drive.
				</p>
			</div>

			{/* Max Files */}
			<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4">
				<div className="space-y-0.5">
					<Label className="text-xs sm:text-sm font-medium">Max files per folder</Label>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Maximum number of files to index from each folder
					</p>
				</div>
				<Select value={maxFiles} onValueChange={handleMaxFilesChange}>
					<SelectTrigger className="w-full sm:w-[160px] h-8 sm:h-9 text-xs sm:text-sm bg-slate-400/5 dark:bg-white/5 border-slate-400/20">
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{MAX_FILES_OPTIONS.map((option) => (
							<SelectItem key={option.value} value={option.value} className="text-xs sm:text-sm">
								{option.label}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>

			{/* Delta Sync Toggle */}
			<div className="flex items-center justify-between gap-4">
				<div className="space-y-0.5">
					<Label className="text-xs sm:text-sm font-medium">Incremental sync</Label>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Only sync changes since last index (faster). Disable for a full re-index.
					</p>
				</div>
				<Switch checked={useDeltaSync} onCheckedChange={handleDeltaSyncChange} />
			</div>

			{/* Include Subfolders Toggle */}
			<div className="flex items-center justify-between gap-4">
				<div className="space-y-0.5">
					<Label className="text-xs sm:text-sm font-medium">Include subfolders</Label>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Recursively index files in subfolders of selected folders
					</p>
				</div>
				<Switch checked={includeSubfolders} onCheckedChange={handleIncludeSubfoldersChange} />
			</div>
		</div>
		</>
	);
};
