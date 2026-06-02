"use client";
import { CalendarClock, CalendarOff, Dot, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { type BuilderSchedule, scheduleToCron } from "@/lib/automations/builder-schema";
import { describeCron } from "@/lib/automations/describe-cron";
import {
	DEFAULT_SCHEDULE,
	FREQUENCY_OPTIONS,
	fromCron,
	type ScheduleFrequency,
	type ScheduleModel,
	toCron,
	WEEKDAY_OPTIONS,
} from "@/lib/automations/schedule-builder";
import { cn } from "@/lib/utils";
import { Field } from "./form-field";
import { TimezoneCombobox } from "./timezone-combobox";

interface ScheduleSectionProps {
	schedule: BuilderSchedule | null;
	timezone: string;
	errors: Record<string, string>;
	onScheduleChange: (schedule: BuilderSchedule | null) => void;
	onTimezoneChange: (timezone: string) => void;
}

function pad(value: number): string {
	return value.toString().padStart(2, "0");
}

export function ScheduleSection({
	schedule,
	timezone,
	errors,
	onScheduleChange,
	onTimezoneChange,
}: ScheduleSectionProps) {
	if (schedule === null) {
		return (
			<div className="rounded-lg border border-dashed border-border/60 bg-muted/20 px-4 py-6 text-center">
				<CalendarOff className="mx-auto h-7 w-7 text-muted-foreground" aria-hidden />
				<p className="mt-2 text-sm text-foreground">No schedule</p>
				<p className="mt-0.5 text-xs text-muted-foreground">
					This automation won't run automatically until you add one.
				</p>
				<Button
					type="button"
					variant="outline"
					size="sm"
					className="mt-3"
					onClick={() => onScheduleChange({ mode: "preset", model: { ...DEFAULT_SCHEDULE } })}
				>
					<Plus className="mr-1.5 h-4 w-4" />
					Add a schedule
				</Button>
			</div>
		);
	}

	const cron = scheduleToCron(schedule);
	const label = describeCron(cron);

	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-accent px-3 py-2">
				<div className="flex items-center gap-2 text-sm min-w-0">
					<CalendarClock className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
					<span className="font-medium text-foreground truncate">{label}</span>
					<Dot className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
					<span className="text-muted-foreground shrink-0">{timezone}</span>
				</div>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
					aria-label="Remove schedule"
					onClick={() => onScheduleChange(null)}
				>
					<X className="h-4 w-4" />
				</Button>
			</div>

			{schedule.mode === "preset" ? (
				<PresetEditor
					model={schedule.model}
					onChange={(model) => onScheduleChange({ mode: "preset", model })}
					onSwitchToCron={() => onScheduleChange({ mode: "cron", cron: toCron(schedule.model) })}
				/>
			) : (
				<CronEditor
					cron={schedule.cron}
					error={errors.schedule}
					onChange={(value) => onScheduleChange({ mode: "cron", cron: value })}
					onSwitchToPreset={() =>
						onScheduleChange({
							mode: "preset",
							model: fromCron(schedule.cron) ?? { ...DEFAULT_SCHEDULE },
						})
					}
				/>
			)}

			<Field label="Timezone">
				<TimezoneCombobox value={timezone} onChange={onTimezoneChange} />
			</Field>
		</div>
	);
}

interface PresetEditorProps {
	model: ScheduleModel;
	onChange: (model: ScheduleModel) => void;
	onSwitchToCron: () => void;
}

function PresetEditor({ model, onChange, onSwitchToCron }: PresetEditorProps) {
	const weeklyNoDays = model.frequency === "weekly" && model.daysOfWeek.length === 0;

	return (
		<div className="space-y-3">
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<Field label="Frequency">
					<Select
						value={model.frequency}
						onValueChange={(value) => onChange({ ...model, frequency: value as ScheduleFrequency })}
					>
						<SelectTrigger className="w-full">
							<SelectValue />
						</SelectTrigger>
						<SelectContent matchTriggerWidth={false} className="w-auto min-w-64">
							{FREQUENCY_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</Field>

				{model.frequency === "hourly" ? (
					<Field label="At minute">
						<Input
							type="number"
							min={0}
							max={59}
							value={model.minute}
							onChange={(e) => onChange({ ...model, minute: clampInt(e.target.value, 0, 59) })}
						/>
					</Field>
				) : (
					<Field label="At time">
						<Input
							type="time"
							value={`${pad(model.hour)}:${pad(model.minute)}`}
							onChange={(e) => {
								const [h, m] = e.target.value.split(":");
								onChange({
									...model,
									hour: clampInt(h, 0, 23),
									minute: clampInt(m, 0, 59),
								});
							}}
						/>
					</Field>
				)}
			</div>

			{model.frequency === "weekly" && (
				<Field label="On days" error={weeklyNoDays ? "Pick at least one day" : undefined}>
					<div className="flex flex-wrap gap-1.5">
						{WEEKDAY_OPTIONS.map((day) => {
							const active = model.daysOfWeek.includes(day.value);
							return (
								<button
									key={day.value}
									type="button"
									aria-pressed={active}
									onClick={() =>
										onChange({ ...model, daysOfWeek: toggleDay(model.daysOfWeek, day.value) })
									}
									className={cn(
										"rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
										active
											? "border-primary bg-primary text-primary-foreground"
											: "border-border/60 bg-background text-muted-foreground hover:bg-muted"
									)}
								>
									{day.short}
								</button>
							);
						})}
					</div>
				</Field>
			)}

			{model.frequency === "monthly" && (
				<Field label="Day of month" hint={"1\u201331."}>
					<Input
						type="number"
						min={1}
						max={31}
						value={model.dayOfMonth}
						onChange={(e) => onChange({ ...model, dayOfMonth: clampInt(e.target.value, 1, 31) })}
						className="w-24"
					/>
				</Field>
			)}

			<button
				type="button"
				onClick={onSwitchToCron}
				className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
			>
				Advanced: enter a schedule expression
			</button>
		</div>
	);
}

interface CronEditorProps {
	cron: string;
	error?: string;
	onChange: (cron: string) => void;
	onSwitchToPreset: () => void;
}

function CronEditor({ cron, error, onChange, onSwitchToPreset }: CronEditorProps) {
	const trimmed = cron.trim();
	const label = trimmed ? describeCron(trimmed) : null;

	return (
		<div className="space-y-2">
			<Field
				label="Schedule expression"
				hint="Five-field cron, e.g. 0 9 * * 1-5 (minute hour day month weekday)."
				error={error}
			>
				<Input
					value={cron}
					placeholder="0 9 * * 1-5"
					className="font-mono"
					onChange={(e) => onChange(e.target.value)}
				/>
			</Field>
			{label && label !== trimmed && <p className="text-xs text-muted-foreground">Runs: {label}</p>}
			<button
				type="button"
				onClick={onSwitchToPreset}
				className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
			>
				Use the simple picker
			</button>
		</div>
	);
}

function clampInt(raw: string, min: number, max: number): number {
	const value = Number.parseInt(raw, 10);
	if (Number.isNaN(value)) return min;
	return Math.min(max, Math.max(min, value));
}

function toggleDay(days: number[], value: number): number[] {
	return days.includes(value)
		? days.filter((day) => day !== value)
		: [...days, value].sort((a, b) => a - b);
}
