"use client";
import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { BuilderTask } from "@/lib/automations/builder-schema";
import { Field } from "./form-field";
import { MentionTaskInput } from "./mention-task-input";

interface TaskItemProps {
	index: number;
	total: number;
	task: BuilderTask;
	searchSpaceId: number;
	error?: string;
	onChange: (patch: Partial<BuilderTask>) => void;
	onMoveUp: () => void;
	onMoveDown: () => void;
	onRemove: () => void;
}

function parseOptionalInt(raw: string): number | null {
	const trimmed = raw.trim();
	if (trimmed === "") return null;
	const value = Number.parseInt(trimmed, 10);
	return Number.isNaN(value) ? null : value;
}

export function TaskItem({
	index,
	total,
	task,
	searchSpaceId,
	error,
	onChange,
	onMoveUp,
	onMoveDown,
	onRemove,
}: TaskItemProps) {
	return (
		<div className="rounded-lg border border-border/60 bg-background p-3 space-y-3">
			<div className="flex items-center justify-between gap-2">
				<span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
					<span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-foreground">
						{index + 1}
					</span>
					Task {index + 1}
				</span>
				<div className="flex items-center gap-0.5">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground"
						disabled={index === 0}
						aria-label="Move task up"
						onClick={onMoveUp}
					>
						<ChevronUp className="h-4 w-4" />
					</Button>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground"
						disabled={index === total - 1}
						aria-label="Move task down"
						onClick={onMoveDown}
					>
						<ChevronDown className="h-4 w-4" />
					</Button>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground hover:text-destructive"
						disabled={total === 1}
						aria-label="Remove task"
						onClick={onRemove}
					>
						<Trash2 className="h-4 w-4" />
					</Button>
				</div>
			</div>

			<Field
				error={error}
				hint="Type @ to reference files, folders, or connectors for extra context."
			>
				<MentionTaskInput
					searchSpaceId={searchSpaceId}
					value={task.query}
					mentions={task.mentions}
					placeholder="What should the agent do? e.g. Summarize new docs in @Marketing since the last run."
					onChange={(query, mentions) => onChange({ query, mentions })}
				/>
			</Field>

			<Accordion type="single" collapsible>
				<AccordionItem value="advanced" className="border-b-0">
					<AccordionTrigger className="py-1.5 text-xs text-muted-foreground hover:no-underline">
						Advanced
					</AccordionTrigger>
					<AccordionContent className="pb-1">
						<div className="grid grid-cols-2 gap-3">
							<Field label="Max retries" hint="Leave blank to use the default.">
								<Input
									type="number"
									min={0}
									max={10}
									value={task.maxRetries ?? ""}
									placeholder="default"
									onChange={(e) => onChange({ maxRetries: parseOptionalInt(e.target.value) })}
								/>
							</Field>
							<Field label="Timeout (seconds)" hint="Leave blank to use the default.">
								<Input
									type="number"
									min={1}
									value={task.timeoutSeconds ?? ""}
									placeholder="default"
									onChange={(e) => onChange({ timeoutSeconds: parseOptionalInt(e.target.value) })}
								/>
							</Field>
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</div>
	);
}
