"use client";

import type { FC } from "react";
import { Switch } from "@/components/ui/switch";

interface SummaryConfigProps {
	enabled: boolean;
	onEnabledChange: (enabled: boolean) => void;
}

export const SummaryConfig: FC<SummaryConfigProps> = ({ enabled, onEnabledChange }) => {
	return (
		<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
			<div className="flex items-center justify-between">
				<div className="space-y-1">
					<h3 className="font-medium text-sm sm:text-base">Enable AI Summary</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Improves search quality but adds latency during indexing
					</p>
				</div>
				<Switch checked={enabled} onCheckedChange={onEnabledChange} />
			</div>
		</div>
	);
};
