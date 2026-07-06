"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
	updateWorkspaceApiAccessMutationAtom,
	updateWorkspaceMutationAtom,
} from "@/atoms/workspaces/workspace-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface GeneralSettingsManagerProps {
	workspaceId: number;
}

export function GeneralSettingsManager({ workspaceId }: GeneralSettingsManagerProps) {
	const t = useTranslations("workspaceSettings");
	const tCommon = useTranslations("common");
	const {
		data: workspace,
		isLoading: loading,
		isError,
		refetch: fetchWorkspace,
	} = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	const { mutateAsync: updateWorkspace } = useAtomValue(updateWorkspaceMutationAtom);
	const { mutateAsync: updateWorkspaceApiAccess } = useAtomValue(
		updateWorkspaceApiAccessMutationAtom
	);

	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [saving, setSaving] = useState(false);
	const [savingApiAccess, setSavingApiAccess] = useState(false);
	const [isExporting, setIsExporting] = useState(false);
	const hasWorkspace = !!workspace;
	const workspaceName = workspace?.name;
	const workspaceDescription = workspace?.description;

	const handleExportKB = useCallback(async () => {
		if (isExporting) return;
		setIsExporting(true);
		try {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/workspaces/${workspaceId}/export`),
				{ method: "GET" }
			);
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
				throw new Error(errorData.detail || "Export failed");
			}
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "knowledge-base.zip";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			toast.success("Knowledge base exported");
		} catch (err) {
			console.error("KB export failed:", err);
			toast.error(err instanceof Error ? err.message : "Export failed");
		} finally {
			setIsExporting(false);
		}
	}, [workspaceId, isExporting]);

	// Initialize state from fetched workspace
	useEffect(() => {
		if (hasWorkspace) {
			setName(workspaceName || "");
			setDescription(workspaceDescription || "");
		}
	}, [hasWorkspace, workspaceName, workspaceDescription]);

	// Derive hasChanges during render
	const hasChanges =
		!!workspace &&
		((workspace.name || "") !== name || (workspace.description || "") !== description);

	const handleSave = async () => {
		try {
			setSaving(true);

			await updateWorkspace({
				id: workspaceId,
				data: {
					name: name.trim(),
					description: description.trim() || undefined,
				},
			});

			await fetchWorkspace();
		} catch (error: unknown) {
			console.error("Error saving workspace details:", error);
			toast.error(error instanceof Error ? error.message : "Failed to save workspace details");
		} finally {
			setSaving(false);
		}
	};

	const onSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		handleSave();
	};

	const handleApiAccessToggle = useCallback(
		async (enabled: boolean) => {
			try {
				setSavingApiAccess(true);
				await updateWorkspaceApiAccess({
					id: workspaceId,
					api_access_enabled: enabled,
				});
				await fetchWorkspace();
			} catch (error) {
				console.error("Error updating API access:", error);
				toast.error(error instanceof Error ? error.message : "Failed to update API access");
			} finally {
				setSavingApiAccess(false);
			}
		},
		[fetchWorkspace, workspaceId, updateWorkspaceApiAccess]
	);

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<div className="flex flex-col gap-6">
					<Skeleton className="h-10 md:h-12 w-full" />
					<Skeleton className="h-10 md:h-12 w-full" />
				</div>
			</div>
		);
	}

	if (isError) {
		return (
			<div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
				<p className="text-sm text-destructive">Failed to load settings.</p>
				<Button variant="outline" size="sm" onClick={() => fetchWorkspace()}>
					Retry
				</Button>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			<form onSubmit={onSubmit} className="space-y-6">
				<div className="flex flex-col gap-6">
					<div className="space-y-2">
						<Label htmlFor="workspace-name">{t("general_name_label")}</Label>
						<Input
							id="workspace-name"
							maxLength={100}
							placeholder={t("general_name_placeholder")}
							value={name}
							onChange={(e) => setName(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("general_name_description")}</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="workspace-description">
							{t("general_description_label")}{" "}
							<span className="text-muted-foreground font-normal">({tCommon("optional")})</span>
						</Label>
						<Input
							id="workspace-description"
							placeholder={t("general_description_placeholder")}
							value={description}
							onChange={(e) => setDescription(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">{t("general_description_description")}</p>
					</div>
				</div>

				<div className="flex justify-end">
					<Button
						type="submit"
						variant="outline"
						disabled={!hasChanges || saving || !name.trim()}
						className="relative gap-2 bg-white text-black hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-black"
					>
						<span className={saving ? "opacity-0" : ""}>{t("general_save")}</span>
						{saving && <Spinner size="sm" className="absolute" />}
					</Button>
				</div>
			</form>

			<div className="border-t pt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div className="space-y-1">
					<Label htmlFor="api-access-enabled">API key access</Label>
					<p className="text-xs text-muted-foreground">Allow API keys to access this workspace.</p>
				</div>
				<Switch
					id="api-access-enabled"
					checked={!!workspace?.api_access_enabled}
					disabled={savingApiAccess}
					onCheckedChange={handleApiAccessToggle}
				/>
			</div>

			<div className="border-t pt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div className="space-y-1">
					<Label>Export knowledge base</Label>
					<p className="text-xs text-muted-foreground">
						Download all documents in this workspace as a ZIP of markdown files.
					</p>
				</div>
				<Button
					type="button"
					variant="secondary"
					size="sm"
					disabled={isExporting}
					onClick={handleExportKB}
					className="relative w-fit shrink-0"
				>
					<span className={isExporting ? "opacity-0" : ""}>Export</span>
					{isExporting && <Spinner size="sm" className="absolute" />}
				</Button>
			</div>
		</div>
	);
}
