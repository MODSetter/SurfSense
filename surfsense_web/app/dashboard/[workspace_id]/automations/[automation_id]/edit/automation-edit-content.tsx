"use client";
import { ShieldAlert } from "lucide-react";
import { useAutomation } from "@/hooks/use-automation";
import { AutomationBuilderForm } from "../../components/builder/automation-builder-form";
import { useAutomationPermissions } from "../../hooks/use-automation-permissions";
import { AutomationDetailLoading } from "../components/automation-detail-loading";
import { AutomationNotFound } from "../components/automation-not-found";
import { AutomationEditHeader } from "./components/automation-edit-header";

interface AutomationEditContentProps {
	workspaceId: number;
	automationId: number;
}

/**
 * Client orchestrator for the edit route. Mirrors detail-content's branch
 * structure but gates on ``canUpdate`` instead of ``canRead``: a user who
 * can read but not update is bounced to the access-denied panel.
 */
export function AutomationEditContent({ workspaceId, automationId }: AutomationEditContentProps) {
	const perms = useAutomationPermissions();
	const validId = Number.isInteger(automationId) && automationId > 0;
	const { data: automation, isLoading, error } = useAutomation(validId ? automationId : undefined);

	if (perms.loading) {
		return <AutomationDetailLoading />;
	}

	if (!perms.canUpdate) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
				<h2 className="mt-3 text-base font-semibold text-foreground">Access denied</h2>
				<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
					You don't have permission to edit automations in this workspace.
				</p>
			</div>
		);
	}

	if (!validId) {
		return <AutomationNotFound workspaceId={workspaceId} />;
	}

	if (isLoading) {
		return <AutomationDetailLoading />;
	}

	if (error || !automation) {
		return <AutomationNotFound workspaceId={workspaceId} error={error} />;
	}

	return (
		<AutomationBuilderForm
			mode="edit"
			workspaceId={workspaceId}
			automation={automation}
			renderModeSwitcher={(modeSwitcher) => (
				<AutomationEditHeader
					automation={automation}
					workspaceId={workspaceId}
					modeSwitcher={modeSwitcher}
				/>
			)}
		/>
	);
}
