"use client";
import { CalendarClock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Trigger } from "@/contracts/types/automation.types";
import { TriggerCard } from "./trigger-card";

interface AutomationTriggersSectionProps {
	triggers: Trigger[];
	automationId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

/**
 * The Triggers card. Lists each attached trigger with its own enable
 * toggle and remove button. v1 attaches triggers at automation-creation
 * time only; there is no in-place "add trigger" affordance here.
 */
export function AutomationTriggersSection({
	triggers,
	automationId,
	canUpdate,
	canDelete,
}: AutomationTriggersSectionProps) {
	return (
		<Card className="border-border/60 bg-accent">
			<CardHeader className="pb-4">
				<CardTitle className="text-base font-semibold">Triggers</CardTitle>
				<p className="text-xs text-muted-foreground">When this automation runs</p>
			</CardHeader>
			<CardContent>
				{triggers.length === 0 ? (
					<div className="rounded-md border border-dashed border-border/60 bg-muted/20 px-4 py-8 text-center">
						<CalendarClock className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden />
						<p className="mt-2 text-sm font-medium text-foreground">No triggers attached</p>
						<p className="mt-1 text-xs text-muted-foreground">
							This automation can still be invoked, but nothing will fire it on its own.
						</p>
					</div>
				) : (
					<div className="space-y-3">
						{triggers.map((trigger) => (
							<TriggerCard
								key={trigger.id}
								trigger={trigger}
								automationId={automationId}
								canUpdate={canUpdate}
								canDelete={canDelete}
							/>
						))}
					</div>
				)}
			</CardContent>
		</Card>
	);
}
