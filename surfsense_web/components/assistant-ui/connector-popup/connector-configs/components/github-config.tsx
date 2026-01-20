"use client";

import { KeyRound } from "lucide-react";
import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface GithubConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

// Helper functions moved outside component to avoid useEffect dependency issues
const stringToArray = (arr: string[] | string | undefined): string[] => {
	if (Array.isArray(arr)) return arr;
	if (typeof arr === "string") {
		return arr
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
	}
	return [];
};

const arrayToString = (arr: string[]): string => {
	return arr.join(", ");
};

export const GithubConfig: FC<GithubConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	// Track internal changes to prevent useEffect from overwriting user input
	const isInternalChange = useRef(false);

	const [githubPat, setGithubPat] = useState<string>(
		(connector.config?.GITHUB_PAT as string) || ""
	);
	const [repoFullNames, setRepoFullNames] = useState<string>(
		arrayToString(stringToArray(connector.config?.repo_full_names))
	);
	const [name, setName] = useState<string>(connector.name || "");

	// Update values when connector changes externally (not from our own input)
	useEffect(() => {
		// Skip if this is our own internal change
		if (isInternalChange.current) {
			isInternalChange.current = false;
			return;
		}
		const pat = (connector.config?.GITHUB_PAT as string) || "";
		const repos = arrayToString(stringToArray(connector.config?.repo_full_names));
		setGithubPat(pat);
		setRepoFullNames(repos);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const handleGithubPatChange = (value: string) => {
		isInternalChange.current = true;
		setGithubPat(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				GITHUB_PAT: value,
			});
		}
	};

	const handleRepoFullNamesChange = (value: string) => {
		isInternalChange.current = true;
		setRepoFullNames(value);
		const repoList = stringToArray(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				repo_full_names: repoList,
			});
		}
	};

	const handleNameChange = (value: string) => {
		isInternalChange.current = true;
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
						placeholder="My GitHub Connector"
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
					<h3 className="font-medium text-sm sm:text-base">Configuration</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" />
							GitHub Personal Access Token (optional)
						</Label>
						<Input
							type="password"
							value={githubPat}
							onChange={(e) => handleGithubPatChange(e.target.value)}
							placeholder="ghp_..."
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Update your GitHub PAT if needed.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Repository Names</Label>
						<Input
							value={repoFullNames}
							onChange={(e) => handleRepoFullNamesChange(e.target.value)}
							placeholder="owner/repo1, owner/repo2"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Comma-separated list of repository full names.
						</p>
					</div>

					{/* Show parsed repositories as badges */}
					{repoFullNames.trim() && (
						<div className="rounded-lg border border-border bg-muted/50 p-3">
							<h4 className="text-[10px] sm:text-xs font-medium mb-2">Repositories:</h4>
							<div className="flex flex-wrap gap-2">
								{stringToArray(repoFullNames).map((repo) => (
									<Badge key={repo} variant="secondary" className="text-[10px]">
										{repo}
									</Badge>
								))}
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};
