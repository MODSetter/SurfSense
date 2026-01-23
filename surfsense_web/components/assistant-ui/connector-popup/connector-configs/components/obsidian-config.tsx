"use client";

import { FolderOpen } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { ConnectorConfigProps } from "../index";

export interface ObsidianConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const ObsidianConfig: FC<ObsidianConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const [vaultPath, setVaultPath] = useState<string>(
		(connector.config?.vault_path as string) || ""
	);
	const [vaultName, setVaultName] = useState<string>(
		(connector.config?.vault_name as string) || ""
	);
	const [excludeFolders, setExcludeFolders] = useState<string>(() => {
		const folders = connector.config?.exclude_folders;
		if (Array.isArray(folders)) {
			return folders.join(", ");
		}
		return (folders as string) || ".obsidian, .trash";
	});
	const [includeAttachments, setIncludeAttachments] = useState<boolean>(
		(connector.config?.include_attachments as boolean) || false
	);
	const [name, setName] = useState<string>(connector.name || "");

	// Update values when connector changes
	useEffect(() => {
		const path = (connector.config?.vault_path as string) || "";
		const vName = (connector.config?.vault_name as string) || "";
		const folders = connector.config?.exclude_folders;
		const attachments = (connector.config?.include_attachments as boolean) || false;

		setVaultPath(path);
		setVaultName(vName);
		setIncludeAttachments(attachments);
		setName(connector.name || "");

		if (Array.isArray(folders)) {
			setExcludeFolders(folders.join(", "));
		} else if (typeof folders === "string") {
			setExcludeFolders(folders);
		}
	}, [connector.config, connector.name]);

	const handleVaultPathChange = (value: string) => {
		setVaultPath(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				vault_path: value,
			});
		}
	};

	const handleVaultNameChange = (value: string) => {
		setVaultName(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				vault_name: value,
			});
		}
	};

	const handleExcludeFoldersChange = (value: string) => {
		setExcludeFolders(value);
		const foldersArray = value
			.split(",")
			.map((f) => f.trim())
			.filter(Boolean);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				exclude_folders: foldersArray,
			});
		}
	};

	const handleIncludeAttachmentsChange = (value: boolean) => {
		setIncludeAttachments(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				include_attachments: value,
			});
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My Obsidian Vault"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						A friendly name to identify this connector.
					</p>
				</div>
			</div>

			{/* Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
						<FolderOpen className="h-4 w-4 text-purple-500" />
						Vault Configuration
					</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Vault Path</Label>
						<Input
							value={vaultPath}
							onChange={(e) => handleVaultPathChange(e.target.value)}
							placeholder="/path/to/your/obsidian/vault"
							className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							The absolute path to your Obsidian vault on the server.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Vault Name</Label>
						<Input
							value={vaultName}
							onChange={(e) => handleVaultNameChange(e.target.value)}
							placeholder="My Knowledge Base"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							A display name for your vault in search results.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Exclude Folders</Label>
						<Input
							value={excludeFolders}
							onChange={(e) => handleExcludeFoldersChange(e.target.value)}
							placeholder=".obsidian, .trash, templates"
							className="border-slate-400/20 focus-visible:border-slate-400/40 font-mono"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Comma-separated list of folder names to exclude from indexing.
						</p>
					</div>

					<div className="flex items-center justify-between rounded-lg border border-slate-400/20 p-3">
						<div className="space-y-0.5">
							<Label className="text-xs sm:text-sm">Include Attachments</Label>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Index attachment folders and embedded files
							</p>
						</div>
						<Switch checked={includeAttachments} onCheckedChange={handleIncludeAttachmentsChange} />
					</div>
				</div>
			</div>
		</div>
	);
};
