"use client";
import { Dot } from "lucide-react";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { AutomationDefinition } from "@/contracts/types/automation.types";
import { ExecutionSummary } from "./execution-summary";
import { InputsSchemaPreview } from "./inputs-schema-preview";
import { PlanStepCard } from "./plan-step-card";

interface AutomationDefinitionSectionProps {
	definition: AutomationDefinition;
}

/**
 * User-facing read view of the saved automation definition. Editing happens on
 * the sibling /edit route; this card should summarize behavior, not expose the
 * raw persisted schema.
 */
export function AutomationDefinitionSection({ definition }: AutomationDefinitionSectionProps) {
	const hasTags = definition.metadata.tags.length > 0;
	const hasInputs = !!definition.inputs;
	const [advancedOpen, setAdvancedOpen] = useState(false);
	const stepCount = `${definition.plan.length} step${definition.plan.length === 1 ? "" : "s"}`;

	return (
		<Card className="border-border/60 bg-accent">
			<CardHeader className="pb-4">
				<CardTitle className="text-base font-semibold">Automation details</CardTitle>
			</CardHeader>
			<CardContent className="space-y-6">
				{definition.goal && (
					<Field label="Goal">
						<p className="text-sm text-foreground">{definition.goal}</p>
					</Field>
				)}

				{hasTags && (
					<Field label="Tags">
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

				{hasInputs && (
					<Field label="Inputs">
						{definition.inputs && <InputsSchemaPreview inputs={definition.inputs} />}
					</Field>
				)}

				<Field
					label={
						<span className="inline-flex items-center">
							Plan
							<Dot className="h-4 w-4 text-muted-foreground" aria-hidden />
							{stepCount}
						</span>
					}
				>
					<div className="space-y-2">
						{definition.plan.map((step, idx) => (
							<PlanStepCard key={step.step_id} step={step} index={idx} />
						))}
					</div>
					<Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen} className="mt-3">
						<CollapsibleTrigger className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
							{advancedOpen ? "Hide advanced options" : "Advanced options"}
						</CollapsibleTrigger>
						<CollapsibleContent>
							<div className="mt-3 rounded-md border border-border/60 bg-background/30 p-3">
								<div className="mb-2 text-sm font-medium text-muted-foreground">
									Execution defaults
								</div>
								<ExecutionSummary execution={definition.execution} />
							</div>
						</CollapsibleContent>
					</Collapsible>
				</Field>
			</CardContent>
		</Card>
	);
}

function Field({
	label,
	children,
}: {
	label: React.ReactNode;
	children: React.ReactNode;
}) {
	return (
		<div className="space-y-2">
			<div className="text-sm font-medium text-muted-foreground">{label}</div>
			{children}
		</div>
	);
}
