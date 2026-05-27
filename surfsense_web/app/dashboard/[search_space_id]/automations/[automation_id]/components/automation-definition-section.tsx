"use client";
import { ListOrdered, Settings2, Tag, Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AutomationDefinition } from "@/contracts/types/automation.types";
import { ExecutionSummary } from "./execution-summary";
import { InputsSchemaPreview } from "./inputs-schema-preview";
import { PlanStepCard } from "./plan-step-card";

interface AutomationDefinitionSectionProps {
	definition: AutomationDefinition;
}

/**
 * The Definition card. Read-only in v1 — editing definitions happens via
 * chat (re-run create_automation with a refined intent) or, later, via
 * the raw-JSON path. Layout is top-down:
 *   goal → tags → execution defaults → inputs schema (if any) → plan
 *
 * The schema_version is rendered as a small badge next to the section
 * title so it's discoverable but doesn't fight for attention.
 */
export function AutomationDefinitionSection({ definition }: AutomationDefinitionSectionProps) {
	const hasTags = definition.metadata.tags.length > 0;
	const hasInputs = !!definition.inputs;

	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
				<CardTitle className="text-base font-semibold">Definition</CardTitle>
				<span className="text-xs font-mono text-muted-foreground border border-border/60 rounded px-1.5 py-0.5">
					v{definition.schema_version}
				</span>
			</CardHeader>
			<CardContent className="space-y-6">
				{definition.goal && (
					<Field icon={Target} label="Goal">
						<p className="text-sm text-foreground">{definition.goal}</p>
					</Field>
				)}

				{hasTags && (
					<Field icon={Tag} label="Tags">
						<div className="flex flex-wrap gap-1.5">
							{definition.metadata.tags.map((tag) => (
								<span
									key={tag}
									className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
								>
									{tag}
								</span>
							))}
						</div>
					</Field>
				)}

				<Field icon={Settings2} label="Execution defaults">
					<ExecutionSummary execution={definition.execution} />
				</Field>

				{hasInputs && (
					<Field icon={Settings2} label="Inputs schema">
						{definition.inputs && <InputsSchemaPreview inputs={definition.inputs} />}
					</Field>
				)}

				<Field
					icon={ListOrdered}
					label={`Plan · ${definition.plan.length} step${definition.plan.length === 1 ? "" : "s"}`}
				>
					<div className="space-y-2">
						{definition.plan.map((step, idx) => (
							<PlanStepCard key={step.step_id} step={step} index={idx} />
						))}
					</div>
				</Field>
			</CardContent>
		</Card>
	);
}

function Field({
	icon: Icon,
	label,
	children,
}: {
	icon: typeof Target;
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div className="space-y-2">
			<div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
				<Icon className="h-3.5 w-3.5" aria-hidden />
				{label}
			</div>
			{children}
		</div>
	);
}
