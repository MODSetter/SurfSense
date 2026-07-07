"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { toast } from "sonner";
import { updateWorkspaceApiAccessMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { ApiKeyContent } from "../../user-settings/components/ApiKeyContent";

/**
 * One-stop API key management for the playground: the workspace API-access
 * toggle (otherwise buried in workspace settings) plus the personal API key
 * manager (otherwise buried in user settings).
 */
export function ApiKeysSection({ workspaceId }: { workspaceId: number }) {
	const {
		data: workspace,
		isLoading,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});
	const { mutateAsync: updateWorkspaceApiAccess } = useAtomValue(
		updateWorkspaceApiAccessMutationAtom
	);
	const [saving, setSaving] = useState(false);

	const handleToggle = async (enabled: boolean) => {
		try {
			setSaving(true);
			await updateWorkspaceApiAccess({ id: workspaceId, api_access_enabled: enabled });
			await refetch();
		} catch (error) {
			console.error("Error updating API access:", error);
			toast.error(error instanceof Error ? error.message : "Failed to update API access");
		} finally {
			setSaving(false);
		}
	};

	const apiAccessEnabled = !!workspace?.api_access_enabled;

	return (
		<div className="space-y-6">
			<div>
				<h1 className="text-xl font-semibold text-foreground md:text-2xl">API Keys</h1>
				<p className="mt-1 text-sm text-muted-foreground">
					Enable API access for this workspace and manage the keys that use it.
				</p>
			</div>

			<div className="flex items-center justify-between gap-4 rounded-lg border border-border/60 px-4 py-3">
				<div className="space-y-1">
					<Label htmlFor="playground-api-access">API key access</Label>
					<p className="text-xs text-muted-foreground">
						Allow API keys to access this workspace.
						{!isLoading && !apiAccessEnabled && " Currently disabled — keys won't work here."}
					</p>
				</div>
				{isLoading ? (
					<Skeleton className="h-5 w-9 rounded-full" />
				) : (
					<Switch
						id="playground-api-access"
						checked={apiAccessEnabled}
						disabled={saving}
						onCheckedChange={handleToggle}
					/>
				)}
			</div>

			<ApiKeyContent />
		</div>
	);
}
