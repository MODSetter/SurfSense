"use client";

import { Calendar, Clock } from "lucide-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

interface ComposioCalendarConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

interface CalendarIndexingOptions {
	max_events: number;
	include_recurring: boolean;
	include_past_events: boolean;
	days_ahead: number;
}

const DEFAULT_CALENDAR_OPTIONS: CalendarIndexingOptions = {
	max_events: 500,
	include_recurring: true,
	include_past_events: true,
	days_ahead: 365,
};

export const ComposioCalendarConfig: FC<ComposioCalendarConfigProps> = ({ connector, onConfigChange }) => {
	const isIndexable = connector.config?.is_indexable as boolean;

	// Initialize with existing options from connector config
	const existingOptions =
		(connector.config?.calendar_options as CalendarIndexingOptions | undefined) || DEFAULT_CALENDAR_OPTIONS;

	const [calendarOptions, setCalendarOptions] = useState<CalendarIndexingOptions>(existingOptions);

	// Update options when connector config changes
	useEffect(() => {
		const options =
			(connector.config?.calendar_options as CalendarIndexingOptions | undefined) ||
			DEFAULT_CALENDAR_OPTIONS;
		setCalendarOptions(options);
	}, [connector.config]);

	const updateConfig = (options: CalendarIndexingOptions) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				calendar_options: options,
			});
		}
	};

	const handleOptionChange = (key: keyof CalendarIndexingOptions, value: number | boolean) => {
		const newOptions = { ...calendarOptions, [key]: value };
		setCalendarOptions(newOptions);
		updateConfig(newOptions);
	};

	// Only show configuration if the connector is indexable
	if (!isIndexable) {
		return <div className="space-y-6" />;
	}

	return (
		<div className="space-y-6">
			{/* Calendar Indexing Options */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<div className="flex items-center gap-2">
						<Calendar className="size-4 text-blue-500" />
						<h3 className="font-medium text-sm sm:text-base">Calendar Indexing Options</h3>
					</div>
					<p className="text-xs sm:text-sm text-muted-foreground">
						Configure how events are indexed from your Google Calendar.
					</p>
				</div>

				{/* Max events to index */}
				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="max-events" className="text-sm font-medium">
								Max events to index
							</Label>
							<p className="text-xs text-muted-foreground">
								Maximum number of events to index per sync
							</p>
						</div>
						<Select
							value={calendarOptions.max_events.toString()}
							onValueChange={(value) =>
								handleOptionChange("max_events", parseInt(value, 10))
							}
						>
							<SelectTrigger
								id="max-events"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select limit" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="100" className="text-xs sm:text-sm">
									100 events
								</SelectItem>
								<SelectItem value="250" className="text-xs sm:text-sm">
									250 events
								</SelectItem>
								<SelectItem value="500" className="text-xs sm:text-sm">
									500 events
								</SelectItem>
								<SelectItem value="1000" className="text-xs sm:text-sm">
									1000 events
								</SelectItem>
								<SelectItem value="2500" className="text-xs sm:text-sm">
									2500 events
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* Days ahead */}
				<div className="space-y-2 pt-2 border-t border-slate-400/20">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<div className="flex items-center gap-1.5">
								<Clock className="size-3.5 text-muted-foreground" />
								<Label htmlFor="days-ahead" className="text-sm font-medium">
									Future events range
								</Label>
							</div>
							<p className="text-xs text-muted-foreground">
								How far ahead to index future events
							</p>
						</div>
						<Select
							value={calendarOptions.days_ahead.toString()}
							onValueChange={(value) =>
								handleOptionChange("days_ahead", parseInt(value, 10))
							}
						>
							<SelectTrigger
								id="days-ahead"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder="Select range" />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="30" className="text-xs sm:text-sm">
									30 days
								</SelectItem>
								<SelectItem value="90" className="text-xs sm:text-sm">
									90 days
								</SelectItem>
								<SelectItem value="180" className="text-xs sm:text-sm">
									180 days
								</SelectItem>
								<SelectItem value="365" className="text-xs sm:text-sm">
									1 year
								</SelectItem>
								<SelectItem value="730" className="text-xs sm:text-sm">
									2 years
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* Include recurring events toggle */}
				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="include-recurring" className="text-sm font-medium">
							Include recurring events
						</Label>
						<p className="text-xs text-muted-foreground">
							Index individual instances of recurring events
						</p>
					</div>
					<Switch
						id="include-recurring"
						checked={calendarOptions.include_recurring}
						onCheckedChange={(checked) =>
							handleOptionChange("include_recurring", checked)
						}
					/>
				</div>

				{/* Include past events toggle */}
				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="include-past" className="text-sm font-medium">
							Include past events
						</Label>
						<p className="text-xs text-muted-foreground">
							Index events from before the selected date range
						</p>
					</div>
					<Switch
						id="include-past"
						checked={calendarOptions.include_past_events}
						onCheckedChange={(checked) =>
							handleOptionChange("include_past_events", checked)
						}
					/>
				</div>
			</div>
		</div>
	);
};

