"use client";

import type { FC } from "react";
import { useState } from "react";
import { FolderSync } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export const LocalFolderConfig: FC<ConnectorConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const isElectron = typeof window !== "undefined" && !!window.electronAPI;

	const [folderPath, setFolderPath] = useState<string>(
		(connector.config?.folder_path as string) || ""
	);
	const [folderName, setFolderName] = useState<string>(
		(connector.config?.folder_name as string) || ""
	);
	const [excludePatterns, setExcludePatterns] = useState<string>(() => {
		const patterns = connector.config?.exclude_patterns;
		if (Array.isArray(patterns)) {
			return patterns.join(", ");
		}
		return (patterns as string) || "node_modules, .git, .DS_Store";
	});
	const [fileExtensions, setFileExtensions] = useState<string>(() => {
		const exts = connector.config?.file_extensions;
		if (Array.isArray(exts)) {
			return exts.join(", ");
		}
		return (exts as string) || "";
	});
	const [name, setName] = useState<string>(connector.name || "");

	const handleFolderPathChange = (value: string) => {
		setFolderPath(value);
		onConfigChange?.({ ...connector.config, folder_path: value });
	};

	const handleFolderNameChange = (value: string) => {
		setFolderName(value);
		onConfigChange?.({ ...connector.config, folder_name: value });
	};

	const handleExcludePatternsChange = (value: string) => {
		setExcludePatterns(value);
		const arr = value
			.split(",")
			.map((p) => p.trim())
			.filter(Boolean);
		onConfigChange?.({ ...connector.config, exclude_patterns: arr });
	};

	const handleFileExtensionsChange = (value: string) => {
		setFileExtensions(value);
		const arr = value
			? value
					.split(",")
					.map((e) => {
						const ext = e.trim();
						return ext.startsWith(".") ? ext : `.${ext}`;
					})
					.filter(Boolean)
			: null;
		onConfigChange?.({ ...connector.config, file_extensions: arr });
	};

	const handleNameChange = (value: string) => {
		setName(value);
		onNameChange?.(value);
	};

	const handleBrowse = async () => {
		if (!isElectron) return;
		const selected = await window.electronAPI!.selectFolder();
		if (selected) {
			handleFolderPathChange(selected);
			const autoName = selected.split(/[\\/]/).pop() || "folder";
			if (!folderName) handleFolderNameChange(autoName);
		}
	};

	return (
		<div className="space-y-6">
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="Local Folder"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
				</div>
			</div>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<h3 className="font-medium text-sm sm:text-base">Folder Configuration</h3>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Folder Path</Label>
						<div className="flex gap-2">
							<Input
								value={folderPath}
								onChange={(e) => handleFolderPathChange(e.target.value)}
								placeholder="/path/to/your/folder"
								className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono flex-1"
							/>
							{isElectron && (
								<Button type="button" variant="outline" size="sm" onClick={handleBrowse} className="shrink-0">
									<FolderSync className="h-4 w-4 mr-1" />
									Browse
								</Button>
							)}
						</div>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Display Name</Label>
						<Input
							value={folderName}
							onChange={(e) => handleFolderNameChange(e.target.value)}
							placeholder="My Notes"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Exclude Patterns</Label>
						<Input
							value={excludePatterns}
							onChange={(e) => handleExcludePatternsChange(e.target.value)}
							placeholder="node_modules, .git, .DS_Store"
							className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Comma-separated patterns of directories/files to exclude.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">File Extensions (optional)</Label>
						<Input
							value={fileExtensions}
							onChange={(e) => handleFileExtensionsChange(e.target.value)}
							placeholder=".md, .txt, .rst"
							className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Leave empty to index all supported files.
						</p>
					</div>
				</div>
			</div>
		</div>
	);
};
