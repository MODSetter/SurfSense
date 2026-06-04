"use client";
import { AlertCircle, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAutomations } from "@/hooks/use-automations";
import { AutomationsEmptyState } from "./components/automations-empty-state";
import { AutomationsHeader } from "./components/automations-header";
import { AutomationsTable } from "./components/automations-table";
import { useAutomationPermissions } from "./hooks/use-automation-permissions";

interface AutomationsContentProps {
	searchSpaceId: number;
}

/**
 * Client orchestrator for the automations list page. Pulls the active
 * search space's first page (via ``useAutomations`` → ``automationsListAtom``)
 * and the user's permissions, then decides between empty / loading / table.
 *
 * Read access is mandatory; anything else is hidden behind RBAC. The
 * permissions hook is co-located in this slice so adding/removing
 * surfaces is a one-file change.
 */
export function AutomationsContent({ searchSpaceId }: AutomationsContentProps) {
	const { automations, total, loading, error } = useAutomations();
	const perms = useAutomationPermissions();

	if (perms.loading) {
		// Permissions gate the entire page; defer everything until we know.
		return (
			<>
				<AutomationsHeader searchSpaceId={searchSpaceId} total={0} loading canCreate={false} />
				<AutomationsTable
					automations={[]}
					searchSpaceId={searchSpaceId}
					loading
					canUpdate={false}
					canDelete={false}
				/>
			</>
		);
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

	if (error) {
		return (
			<>
				<AutomationsHeader
					searchSpaceId={searchSpaceId}
					total={0}
					loading={false}
					canCreate={perms.canCreate}
				/>
				<Alert variant="destructive">
					<AlertCircle aria-hidden />
					<AlertDescription>Couldn't load automations {error.message}</AlertDescription>
				</Alert>
			</>
		);
	}

	if (!loading && automations.length === 0) {
		return (
			<>
				<AutomationsHeader
					searchSpaceId={searchSpaceId}
					total={0}
					loading={false}
					canCreate={perms.canCreate}
					showCreateCta={false}
				/>
				<AutomationsEmptyState searchSpaceId={searchSpaceId} canCreate={perms.canCreate} />
			</>
		);
	}

	return (
		<>
			<AutomationsHeader
				searchSpaceId={searchSpaceId}
				total={total}
				loading={loading}
				canCreate={perms.canCreate}
			/>
			<AutomationsTable
				automations={automations}
				searchSpaceId={searchSpaceId}
				loading={loading}
				canUpdate={perms.canUpdate}
				canDelete={perms.canDelete}
			/>
		</>
	);
}
