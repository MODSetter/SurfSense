"use client";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { BuilderExecution } from "@/lib/automations/builder-schema";
import { Field } from "./form-field";

interface AdvancedSectionProps {
	execution: BuilderExecution;
	tags: string[];
	onExecutionChange: (patch: Partial<BuilderExecution>) => void;
	onTagsChange: (tags: string[]) => void;
}

const BACKOFF_OPTIONS: ReadonlyArray<{ value: BuilderExecution["retryBackoff"]; label: string }> = [
	{ value: "exponential", label: "Exponential" },
	{ value: "linear", label: "Linear" },
	{ value: "none", label: "None" },
];

const CONCURRENCY_OPTIONS: ReadonlyArray<{
	value: BuilderExecution["concurrency"];
	label: string;
}> = [
	{ value: "drop_if_running", label: "Skip if already running" },
	{ value: "queue", label: "Queue the next run" },
	{ value: "always", label: "Always run" },
];

function clampInt(raw: string, min: number, fallback: number): number {
	const value = Number.parseInt(raw, 10);
	if (Number.isNaN(value)) return fallback;
	return Math.max(min, value);
}

export function AdvancedSection({
	execution,
	tags,
	onExecutionChange,
	onTagsChange,
}: AdvancedSectionProps) {
	const [tagsText, setTagsText] = useState(tags.join(", "));

	function commitTags(text: string) {
		const next = text
			.split(",")
			.map((tag) => tag.trim())
			.filter(Boolean);
		onTagsChange(next);
	}

	return (
		<div className="space-y-4">
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<Field label="Timeout (seconds)" hint="Wall-clock cap for the whole run">
					<Input
						type="number"
						min={1}
						value={execution.timeoutSeconds}
						onChange={(e) =>
							onExecutionChange({ timeoutSeconds: clampInt(e.target.value, 1, 600) })
						}
					/>
				</Field>
				<Field label="Max retries" hint="Per-step retry budget">
					<Input
						type="number"
						min={0}
						value={execution.maxRetries}
						onChange={(e) => onExecutionChange({ maxRetries: clampInt(e.target.value, 0, 2) })}
					/>
				</Field>
				<Field label="Retry backoff">
					<Select
						value={execution.retryBackoff}
						onValueChange={(value) =>
							onExecutionChange({ retryBackoff: value as BuilderExecution["retryBackoff"] })
						}
					>
						<SelectTrigger className="w-full">
							<SelectValue />
						</SelectTrigger>
						<SelectContent matchTriggerWidth={false} className="w-auto min-w-48">
							{BACKOFF_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</Field>
				<Field label="If already running">
					<Select
						value={execution.concurrency}
						onValueChange={(value) =>
							onExecutionChange({ concurrency: value as BuilderExecution["concurrency"] })
						}
					>
						<SelectTrigger className="w-full">
							<SelectValue />
						</SelectTrigger>
						<SelectContent matchTriggerWidth={false} className="w-auto min-w-64">
							{CONCURRENCY_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</Field>
			</div>

			<Field label="Tags" hint="Comma-separated. Optional.">
				<Input
					value={tagsText}
					placeholder="research, weekly"
					onChange={(e) => setTagsText(e.target.value)}
					onBlur={(e) => commitTags(e.target.value)}
				/>
			</Field>
		</div>
	);
}
