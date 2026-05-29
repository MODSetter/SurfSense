"use client";
import { Lock } from "lucide-react";
import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { ModelEligibilityViolation } from "@/contracts/types/automation.types";

interface AutomationModelGateAlertProps {
	searchSpaceId: number;
	violations: ModelEligibilityViolation[];
	className?: string;
}

// Model selection for automations is managed under the roles tab, so every
// blocked slot deep-links there (the label still names which slot to fix).
const SETTINGS_TAB = "roles";
const KIND_LABEL: Record<ModelEligibilityViolation["kind"], string> = {
	llm: "Agent model",
	image: "Image model",
	vision: "Vision model",
};

/**
 * Warns that the search space's models aren't billable for automations.
 *
 * Automations may only use premium global models or your own (BYOK) models —
 * free models and Auto mode are blocked so every run is metered in premium
 * credits. Surfaced wherever a user can start creating an automation.
 */
export function AutomationModelGateAlert({
	searchSpaceId,
	violations,
	className,
}: AutomationModelGateAlertProps) {
	if (violations.length === 0) return null;

	return (
		<Alert variant="warning" className={className}>
			<Lock aria-hidden />
			<AlertTitle>Automations need a premium or your own model</AlertTitle>
			<AlertDescription>
				<p>
					Automations run unattended, so every run must use a premium model or your own (BYOK)
					model. Update these in your model settings, then create your automation.
				</p>
				<ul className="mt-1 list-inside list-disc">
					{violations.map((violation) => (
						<li key={violation.kind}>
							<Link
								href={`/dashboard/${searchSpaceId}/search-space-settings/${SETTINGS_TAB}`}
								className="font-medium text-foreground underline underline-offset-2 hover:no-underline"
							>
								{KIND_LABEL[violation.kind]}
							</Link>
							<span className="text-muted-foreground"> — {violation.reason}</span>
						</li>
					))}
				</ul>
			</AlertDescription>
		</Alert>
	);
}
