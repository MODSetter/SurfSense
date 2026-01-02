"use client";

import { KeyRound } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface LumaConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const LumaConfig: FC<LumaConfigProps> = ({ connector, onConfigChange, onNameChange }) => {
	const [apiKey, setApiKey] = useState<string>((connector.config?.LUMA_API_KEY as string) || "");
	const [name, setName] = useState<string>(connector.name || "");

	// Update API key and name when connector changes
	useEffect(() => {
		const key = (connector.config?.LUMA_API_KEY as string) || "";
		setApiKey(key);
		setName(connector.name || "");
	}, [connector.config, connector.name]);

	const handleApiKeyChange = (value: string) => {
		setApiKey(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				LUMA_API_KEY: value,
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
						placeholder="My Luma Connector"
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
						Luma API Key
					</Label>
					<Input
						type="password"
						value={apiKey}
						onChange={(e) => handleApiKeyChange(e.target.value)}
						placeholder="Your API Key"
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						Update your Luma API Key if needed.
					</p>
				</div>
			</div>
		</div>
	);
};
