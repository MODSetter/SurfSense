"use client";
import { ShieldAlert } from "lucide-react";
import { useAutomationPermissions } from "../hooks/use-automation-permissions";
import { AutomationJsonForm } from "./components/automation-json-form";
import { AutomationNewHeader } from "./components/automation-new-header";

interface AutomationNewContentProps {
	searchSpaceId: number;
}

/**
 * Orchestrator for the raw-JSON create route. Gates on
 * ``automations:create`` so users who can't create don't even see the
 * form; same panel as the detail page's access-denied state for
 * consistency.
 */
export function AutomationNewContent({ searchSpaceId }: AutomationNewContentProps) {
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
		<>
			<AutomationNewHeader searchSpaceId={searchSpaceId} />
			<AutomationJsonForm searchSpaceId={searchSpaceId} />
		</>
	);
}
