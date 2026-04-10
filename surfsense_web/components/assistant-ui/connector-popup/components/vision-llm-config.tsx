"use client";

import type { FC } from "react";
import { Switch } from "@/components/ui/switch";

interface VisionLLMConfigProps {
	enabled: boolean;
	onEnabledChange: (enabled: boolean) => void;
}

export const VisionLLMConfig: FC<VisionLLMConfigProps> = ({ enabled, onEnabledChange }) => {
	return (
		<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
			<div className="flex items-center justify-between">
				<div className="space-y-1">
					<h3 className="font-medium text-sm sm:text-base">Enable Vision LLM</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Describes images using AI vision (costly, slower)
					</p>
				</div>
				<Switch checked={enabled} onCheckedChange={onEnabledChange} />
			</div>
		</div>
	);
};
