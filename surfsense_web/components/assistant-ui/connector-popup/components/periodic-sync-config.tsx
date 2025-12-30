"use client";

import { type FC } from "react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

interface PeriodicSyncConfigProps {
	enabled: boolean;
	frequencyMinutes: string;
	onEnabledChange: (enabled: boolean) => void;
	onFrequencyChange: (frequency: string) => void;
}

export const PeriodicSyncConfig: FC<PeriodicSyncConfigProps> = ({
	enabled,
	frequencyMinutes,
	onEnabledChange,
	onFrequencyChange,
}) => {
	return (
		<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-6">
			<div className="flex items-center justify-between">
				<div className="space-y-1">
					<h3 className="font-medium">Enable Periodic Sync</h3>
					<p className="text-sm text-muted-foreground">
						Automatically re-index at regular intervals
					</p>
				</div>
				<Switch checked={enabled} onCheckedChange={onEnabledChange} />
			</div>

			{enabled && (
				<div className="mt-4 pt-4 border-t border-border/100 space-y-3">
					<div className="space-y-2">
						<Label htmlFor="frequency">Sync Frequency</Label>
						<Select value={frequencyMinutes} onValueChange={onFrequencyChange}>
							<SelectTrigger
								id="frequency"
								className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20"
							>
								<SelectValue placeholder="Select frequency" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="15">Every 15 minutes</SelectItem>
								<SelectItem value="60">Every hour</SelectItem>
								<SelectItem value="360">Every 6 hours</SelectItem>
								<SelectItem value="720">Every 12 hours</SelectItem>
								<SelectItem value="1440">Daily</SelectItem>
								<SelectItem value="10080">Weekly</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>
			)}
		</div>
	);
};

