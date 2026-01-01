"use client";

import { KeyRound } from "lucide-react";
import { useState, useEffect } from "react";
import type { FC } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface NotionConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const NotionConfig: FC<NotionConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const [integrationToken, setIntegrationToken] = useState<string>(
		(connector.config?.NOTION_INTEGRATION_TOKEN as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");

	// Update integration token and name when connector changes
	useEffect(() => {
		const token = (connector.config?.NOTION_INTEGRATION_TOKEN as string) || "";
		setIntegrationToken(token);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const handleIntegrationTokenChange = (value: string) => {
		setIntegrationToken(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				NOTION_INTEGRATION_TOKEN: value,
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
						placeholder="My Notion Connector"
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
						Notion Integration Token
					</Label>
					<Input
						type="password"
						value={integrationToken}
						onChange={(e) => handleIntegrationTokenChange(e.target.value)}
						placeholder="Begins with secret_..."
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Update your Notion Integration Token if needed.
					</p>
				</div>
			</div>
		</div>
	);
};
