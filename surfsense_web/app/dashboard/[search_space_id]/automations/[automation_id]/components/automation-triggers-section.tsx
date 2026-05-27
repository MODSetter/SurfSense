"use client";
import { CalendarClock, MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Trigger } from "@/contracts/types/automation.types";
import { TriggerCard } from "./trigger-card";

interface AutomationTriggersSectionProps {
	triggers: Trigger[];
	automationId: number;
	searchSpaceId: number;
	canUpdate: boolean;
	canDelete: boolean;
	canCreate: boolean;
}

/**
 * The Triggers card. Lists each attached trigger with its own enable
 * toggle and remove button. Adding a new trigger is intent-driven (via
 * chat) for v1 — same philosophy as creating an automation, so the
 * empty/add CTA links to a new chat rather than opening a form.
 */
export function AutomationTriggersSection({
	triggers,
	automationId,
	searchSpaceId,
	canUpdate,
	canDelete,
	canCreate,
}: AutomationTriggersSectionProps) {
	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
				<div className="space-y-1">
					<CardTitle className="text-base font-semibold">Triggers</CardTitle>
					<p className="text-xs text-muted-foreground">
						When this automation fires. v1 supports scheduled triggers only.
					</p>
				</div>
				{canCreate && (
					<Button asChild variant="outline" size="sm">
						<Link href={`/dashboard/${searchSpaceId}/new-chat`}>
							<MessageSquarePlus className="mr-2 h-4 w-4" />
							Add via chat
						</Link>
					</Button>
				)}
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
