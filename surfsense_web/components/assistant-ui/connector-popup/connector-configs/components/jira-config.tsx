"use client";

import { KeyRound } from "lucide-react";
import { useState, useEffect } from "react";
import type { FC } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface JiraConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const JiraConfig: FC<JiraConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const [baseUrl, setBaseUrl] = useState<string>(
		(connector.config?.JIRA_BASE_URL as string) || ""
	);
	const [email, setEmail] = useState<string>(
		(connector.config?.JIRA_EMAIL as string) || ""
	);
	const [apiToken, setApiToken] = useState<string>(
		(connector.config?.JIRA_API_TOKEN as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");

	// Update values when connector changes
	useEffect(() => {
		const url = (connector.config?.JIRA_BASE_URL as string) || "";
		const emailVal = (connector.config?.JIRA_EMAIL as string) || "";
		const token = (connector.config?.JIRA_API_TOKEN as string) || "";
		setBaseUrl(url);
		setEmail(emailVal);
		setApiToken(token);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const handleBaseUrlChange = (value: string) => {
		setBaseUrl(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				JIRA_BASE_URL: value,
			});
		}
	};

	const handleEmailChange = (value: string) => {
		setEmail(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				JIRA_EMAIL: value,
			});
		}
	};

	const handleApiTokenChange = (value: string) => {
		setApiToken(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				JIRA_API_TOKEN: value,
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
						placeholder="My Jira Connector"
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
						<Label className="text-xs sm:text-sm">Jira Base URL</Label>
						<Input
							type="url"
							value={baseUrl}
							onChange={(e) => handleBaseUrlChange(e.target.value)}
							placeholder="https://your-domain.atlassian.net"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							The base URL of your Jira instance.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">Email Address</Label>
						<Input
							type="email"
							value={email}
							onChange={(e) => handleEmailChange(e.target.value)}
							placeholder="your-email@example.com"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							The email address associated with your Atlassian account.
						</p>
					</div>

					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" />
							API Token
						</Label>
						<Input
							type="password"
							value={apiToken}
							onChange={(e) => handleApiTokenChange(e.target.value)}
							placeholder="Your API Token"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							Update your Jira API Token if needed.
						</p>
					</div>
				</div>
			</div>
		</div>
	);
};

