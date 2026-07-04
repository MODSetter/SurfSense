"use client";
import { ShieldAlert } from "lucide-react";
import { AutomationBuilderForm } from "../components/builder/automation-builder-form";
import { useAutomationPermissions } from "../hooks/use-automation-permissions";
import { AutomationNewHeader } from "./components/automation-new-header";

interface AutomationNewContentProps {
	workspaceId: number;
}

/**
 * Orchestrator for the create route. Gates on ``automations:create`` so users
 * who can't create don't even see the form; same panel as the detail page's
 * access-denied state for consistency. The builder defaults to the friendly
 * form with a raw-JSON escape hatch.
 *
 * Model eligibility is no longer gated here — the builder's own model pickers
 * list eligible (premium/BYOK) models, surface a per-slot notice when none
 * exist, and block submit until each slot resolves.
 */
export function AutomationNewContent({ workspaceId }: AutomationNewContentProps) {
	const perms = useAutomationPermissions();

	if (perms.loading) {
		return <div className="h-32 rounded-md border border-border/60 bg-muted/10 animate-pulse" />;
	}

	if (!perms.canCreate) {
		return (
			<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
				<ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
				<h2 className="mt-3 text-base font-semibold text-foreground">Access denied</h2>
				<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
					You don't have permission to create automations in this search space.
				</p>
			</div>
		);
	}

	return (
		<AutomationBuilderForm
			mode="create"
			workspaceId={workspaceId}
			renderModeSwitcher={(modeSwitcher) => (
				<AutomationNewHeader workspaceId={workspaceId} modeSwitcher={modeSwitcher} />
			)}
		/>
	);
}
