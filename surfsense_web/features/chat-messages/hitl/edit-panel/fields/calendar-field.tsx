"use client";

import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import type React from "react";
import { useCallback, useMemo, useState } from "react";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

function parseDateTimeValue(value: string): { date: Date | undefined; time: string } {
	if (!value) return { date: undefined, time: "09:00" };
	try {
		const d = new Date(value);
		if (Number.isNaN(d.getTime())) return { date: undefined, time: "09:00" };
		return {
			date: d,
			time: format(d, "HH:mm"),
		};
	} catch {
		return { date: undefined, time: "09:00" };
	}
}

function buildLocalDateTimeString(date: Date | undefined, time: string): string {
	if (!date) return "";
	const [hours, minutes] = time.split(":").map(Number);
	const combined = new Date(date);
	combined.setHours(hours ?? 9, minutes ?? 0, 0, 0);
	const y = combined.getFullYear();
	const m = String(combined.getMonth() + 1).padStart(2, "0");
	const d = String(combined.getDate()).padStart(2, "0");
	const h = String(combined.getHours()).padStart(2, "0");
	const min = String(combined.getMinutes()).padStart(2, "0");
	return `${y}-${m}-${d}T${h}:${min}:00`;
}

/**
 * Calendar popover + 24h time input. Emits a local ISO-like string
 * (``YYYY-MM-DDThh:mm:00``) on every change. Value is parsed back into
 * date + time on every render so the picker stays in sync with
 * controlled props.
 */
export function DateTimePickerField({
	id,
	value,
	onChange,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
}) {
	const parsed = useMemo(() => parseDateTimeValue(value), [value]);
	const [selectedDate, setSelectedDate] = useState<Date | undefined>(parsed.date);
	const [time, setTime] = useState(parsed.time);
	const [open, setOpen] = useState(false);

	const handleDateSelect = useCallback(
		(day: Date | undefined) => {
			setSelectedDate(day);
			onChange(buildLocalDateTimeString(day, time));
			setOpen(false);
		},
		[time, onChange]
	);

	const handleTimeChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const newTime = e.target.value;
			setTime(newTime);
			onChange(buildLocalDateTimeString(selectedDate, newTime));
		},
		[selectedDate, onChange]
	);

	const displayLabel = selectedDate
		? `${format(selectedDate, "MMM d, yyyy")} at ${time}`
		: "Pick date & time";

	return (
		<div className="flex gap-2">
			<Popover open={open} onOpenChange={setOpen}>
				<PopoverTrigger asChild>
					<button
						id={id}
						type="button"
						className="flex-1 flex items-center gap-2 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring"
					>
						<CalendarIcon className="size-3.5 text-muted-foreground shrink-0" />
						<span className={selectedDate ? "text-foreground" : "text-muted-foreground"}>
							{displayLabel}
						</span>
					</button>
				</PopoverTrigger>
				<PopoverContent className="w-auto p-0" align="start">
					<Calendar
						mode="single"
						selected={selectedDate}
						onSelect={handleDateSelect}
						defaultMonth={selectedDate}
					/>
				</PopoverContent>
			</Popover>
			<Input
				type="time"
				value={time}
				onChange={handleTimeChange}
				className="w-[120px] text-sm shrink-0 appearance-none [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
			/>
		</div>
	);
}
