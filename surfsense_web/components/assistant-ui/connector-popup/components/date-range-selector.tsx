"use client";

import { addDays, format, subDays, subYears } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";

interface DateRangeSelectorProps {
	startDate: Date | undefined;
	endDate: Date | undefined;
	onStartDateChange: (date: Date | undefined) => void;
	onEndDateChange: (date: Date | undefined) => void;
	allowFutureDates?: boolean; // Allow future dates for calendar connectors
	lastIndexedAt?: string | null; // Last sync timestamp to show in default placeholder
}

export const DateRangeSelector: FC<DateRangeSelectorProps> = ({
	startDate,
	endDate,
	onStartDateChange,
	onEndDateChange,
	allowFutureDates = false,
	lastIndexedAt,
}) => {
	const startDatePlaceholder = lastIndexedAt
		? `From ${formatRelativeDate(lastIndexedAt)}`
		: "Default (1 year)";

	const handleLast30Days = () => {
		const today = new Date();
		onStartDateChange(subDays(today, 30));
		onEndDateChange(today);
	};

	const handleNext30Days = () => {
		const today = new Date();
		onStartDateChange(today);
		onEndDateChange(addDays(today, 30));
	};

	const handleLastYear = () => {
		const today = new Date();
		onStartDateChange(subYears(today, 1));
		onEndDateChange(today);
	};

	const handleClearDates = () => {
		onStartDateChange(undefined);
		onEndDateChange(undefined);
	};

	return (
		<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
			<h3 className="font-medium text-sm sm:text-base mb-4">Select Date Range</h3>
			<p className="text-xs sm:text-sm text-muted-foreground mb-6">
				{allowFutureDates
					? "Choose the date range to sync your data. You can select future dates to index upcoming events."
					: "Choose how far back you want to sync your data. You can always re-index later with different dates."}
			</p>

			<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
				{/* Start Date */}
				<div className="space-y-2">
					<Label htmlFor="start-date" className="text-xs sm:text-sm">
						Start Date
					</Label>
					<Popover>
						<PopoverTrigger asChild>
							<Button
								id="start-date"
								variant="outline"
								className={cn(
									"w-full justify-start text-left font-normal bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm",
									!startDate && "text-muted-foreground"
								)}
							>
								<CalendarIcon className="mr-2 h-4 w-4" />
								{startDate ? format(startDate, "PPP") : startDatePlaceholder}
							</Button>
						</PopoverTrigger>
						<PopoverContent className="w-auto p-0 z-[100]" align="start">
							<Calendar
								mode="single"
								selected={startDate}
								onSelect={onStartDateChange}
								disabled={allowFutureDates ? false : (date) => date > new Date()}
							/>
						</PopoverContent>
					</Popover>
				</div>

				{/* End Date */}
				<div className="space-y-2">
					<Label htmlFor="end-date" className="text-xs sm:text-sm">
						End Date
					</Label>
					<Popover>
						<PopoverTrigger asChild>
							<Button
								id="end-date"
								variant="outline"
								className={cn(
									"w-full justify-start text-left font-normal bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm",
									!endDate && "text-muted-foreground"
								)}
							>
								<CalendarIcon className="mr-2 h-4 w-4" />
								{endDate ? format(endDate, "PPP") : "Default (Today)"}
							</Button>
						</PopoverTrigger>
						<PopoverContent className="w-auto p-0 z-[100]" align="start">
							<Calendar
								mode="single"
								selected={endDate}
								onSelect={onEndDateChange}
								disabled={
									allowFutureDates
										? (date) => (startDate ? date < startDate : false)
										: (date) => date > new Date() || (startDate ? date < startDate : false)
								}
							/>
						</PopoverContent>
					</Popover>
				</div>
			</div>

			{/* Quick date range buttons */}
			<div className="flex flex-wrap gap-2 mt-4">
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={handleClearDates}
					className="text-xs sm:text-sm bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
				>
					Clear Dates
				</Button>
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={handleLast30Days}
					className="text-xs sm:text-sm bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
				>
					Last 30 Days
				</Button>
				{allowFutureDates && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={handleNext30Days}
						className="text-xs sm:text-sm bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
					>
						Next 30 Days
					</Button>
				)}
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={handleLastYear}
					className="text-xs sm:text-sm bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 hover:bg-slate-400/10 dark:hover:bg-slate-400/10"
				>
					Last Year
				</Button>
			</div>
		</div>
	);
};
