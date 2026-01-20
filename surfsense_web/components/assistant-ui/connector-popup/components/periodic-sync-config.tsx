"use client";

import { AlertCircle } from "lucide-react";
import type { FC } from "react";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

interface PeriodicSyncConfigProps {
	enabled: boolean;
	frequencyMinutes: string;
	onEnabledChange: (enabled: boolean) => void;
	onFrequencyChange: (frequency: string) => void;
	disabled?: boolean;
	disabledMessage?: string;
}

export const PeriodicSyncConfig: FC<PeriodicSyncConfigProps> = ({
	enabled,
	frequencyMinutes,
	onEnabledChange,
	onFrequencyChange,
	disabled = false,
	disabledMessage,
}) => {
	return (
		<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
			<div className="flex items-center justify-between">
				<div className="space-y-1">
					<h3 className="font-medium text-sm sm:text-base">Enable Periodic Sync</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Automatically re-index at regular intervals
					</p>
				</div>
				<Switch checked={enabled} onCheckedChange={onEnabledChange} disabled={disabled} />
			</div>

			{/* Show disabled message when periodic sync can't be enabled */}
			{disabled && disabledMessage && (
				<div className="mt-3 flex items-start gap-2 text-amber-600 dark:text-amber-400">
					<AlertCircle className="size-4 mt-0.5 shrink-0" />
					<p className="text-xs sm:text-sm">{disabledMessage}</p>
				</div>
			)}

			{enabled && (
				<div className="mt-4 pt-4 border-t border-slate-400/20 space-y-3">
					<div className="space-y-2">
						<Label htmlFor="frequency" className="text-xs sm:text-sm">
							Sync Frequency
						</Label>
						<Select value={frequencyMinutes} onValueChange={onFrequencyChange}>
							<SelectTrigger
								id="frequency"
								className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select frequency" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="5" className="text-xs sm:text-sm">
									Every 5 minutes
								</SelectItem>
								<SelectItem value="15" className="text-xs sm:text-sm">
									Every 15 minutes
								</SelectItem>
								<SelectItem value="60" className="text-xs sm:text-sm">
									Every hour
								</SelectItem>
								<SelectItem value="360" className="text-xs sm:text-sm">
									Every 6 hours
								</SelectItem>
								<SelectItem value="720" className="text-xs sm:text-sm">
									Every 12 hours
								</SelectItem>
								<SelectItem value="1440" className="text-xs sm:text-sm">
									Daily
								</SelectItem>
								<SelectItem value="10080" className="text-xs sm:text-sm">
									Weekly
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>
			)}
		</div>
	);
};
