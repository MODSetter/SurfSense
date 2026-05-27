"use client";
import { ShieldAlert } from "lucide-react";
import { useAutomation } from "@/hooks/use-automation";
import { useAutomationPermissions } from "../hooks/use-automation-permissions";
import { AutomationDefinitionSection } from "./components/automation-definition-section";
import { AutomationDetailHeader } from "./components/automation-detail-header";
import { AutomationDetailLoading } from "./components/automation-detail-loading";
import { AutomationNotFound } from "./components/automation-not-found";
import { AutomationTriggersSection } from "./components/automation-triggers-section";

interface AutomationDetailContentProps {
	searchSpaceId: number;
	automationId: number;
}

/**
 * Client orchestrator for one automation's detail view. Branches:
 *   - permissions loading → skeleton
 *   - no read permission → access denied panel
 *   - bad id (NaN) → not-found panel
 *   - detail fetching → skeleton
 *   - detail error / null → not-found panel (we don't distinguish 404
 *     from 403 in the UI)
 *   - detail loaded → header + definition + triggers
 *
 * Each child component is gated independently on the relevant permission
 * so the orchestrator stays thin.
 */
export function AutomationDetailContent({
	searchSpaceId,
	automationId,
}: AutomationDetailContentProps) {
	const perms = useAutomationPermissions();
	const validId = Number.isInteger(automationId) && automationId > 0;
	const { data: automation, isLoading, error } = useAutomation(validId ? automationId : undefined);

	if (perms.loading) {
		return <AutomationDetailLoading />;
	}

	if (!perms.canRead) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
				<h2 className="mt-3 text-base font-semibold text-foreground">Access denied</h2>
				<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
					You don't have permission to view automations in this search space.
				</p>
			</div>
		);
	}

	if (!validId) {
		return <AutomationNotFound searchSpaceId={searchSpaceId} />;
	}

	if (isLoading) {
		return <AutomationDetailLoading />;
	}

	if (error || !automation) {
		return <AutomationNotFound searchSpaceId={searchSpaceId} error={error} />;
	}

	return (
		<>
			<AutomationDetailHeader
				automation={automation}
				searchSpaceId={searchSpaceId}
				canUpdate={perms.canUpdate}
				canDelete={perms.canDelete}
			/>

			<AutomationDefinitionSection definition={automation.definition} />

			<AutomationTriggersSection
				triggers={automation.triggers}
				automationId={automation.id}
				searchSpaceId={searchSpaceId}
				canUpdate={perms.canUpdate}
				canDelete={perms.canDelete}
				canCreate={perms.canCreate}
			/>
		</>
	);
}
