"use client";

import { Info, KeyRound } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface ClickUpConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const ClickUpConfig: FC<ClickUpConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	// Check if this is an OAuth connector (has access_token or _token_encrypted flag)
	const isOAuth = !!(connector.config?.access_token || connector.config?._token_encrypted);

	const [apiToken, setApiToken] = useState<string>(
		(connector.config?.CLICKUP_API_TOKEN as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");

	// Update values when connector changes (only for legacy connectors)
	useEffect(() => {
		if (!isOAuth) {
			const token = (connector.config?.CLICKUP_API_TOKEN as string) || "";
			setApiToken(token);
		}
		setName(connector.name || "");
	}, [connector.config, connector.name, isOAuth]);

	const handleApiTokenChange = (value: string) => {
		setApiToken(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				CLICKUP_API_TOKEN: value,
			});
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	// For OAuth connectors, show simple info message
	if (isOAuth) {
		const workspaceName = (connector.config?.workspace_name as string) || "Unknown Workspace";
		return (
			<div className="space-y-6">
				{/* OAuth Info */}
				<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
					<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
						<Info className="size-4" />
					</div>
					<div className="text-xs sm:text-sm">
						<p className="font-medium text-xs sm:text-sm">Connected via OAuth</p>
						<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
							Workspace:{" "}
							<code className="bg-muted px-1 py-0.5 rounded text-inherit">{workspaceName}</code>
						</p>
						<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
							To update your connection, reconnect this connector.
						</p>
					</div>
				</div>
			</div>
		);
	}

	// For legacy API token connectors, show the form
	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">Connector Name</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder="My ClickUp Connector"
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

				<div className="space-y-2">
					<Label className="flex items-center gap-2 text-xs sm:text-sm">
						<KeyRound className="h-4 w-4" />
						ClickUp API Token
					</Label>
					<Input
						type="password"
						value={apiToken}
						onChange={(e) => handleApiTokenChange(e.target.value)}
						placeholder="pk_..."
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Update your ClickUp API Token if needed. For better security and automatic token
						refresh, consider disconnecting and reconnecting using OAuth 2.0.
					</p>
				</div>
			</div>
		</div>
	);
};
