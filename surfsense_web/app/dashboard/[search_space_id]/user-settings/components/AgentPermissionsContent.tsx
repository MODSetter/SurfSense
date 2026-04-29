"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { AlertTriangle, Check, Plus, ShieldCheck, Trash2, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
	type AgentPermissionAction,
	type AgentPermissionRule,
	type AgentPermissionRuleCreate,
	agentPermissionsApiService,
} from "@/lib/apis/agent-permissions-api.service";
import { AppError } from "@/lib/error";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";

const ACTION_DESCRIPTIONS: Record<AgentPermissionAction, string> = {
	allow: "Always run without prompting",
	deny: "Block silently",
	ask: "Pause and ask for approval",
};

const ACTION_BADGE: Record<AgentPermissionAction, { label: string; className: string }> = {
	allow: { label: "Allow", className: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30" },
	deny: { label: "Deny", className: "bg-destructive/10 text-destructive border-destructive/30" },
	ask: { label: "Ask", className: "bg-amber-500/10 text-amber-600 border-amber-500/30" },
};

const EMPTY_FORM: AgentPermissionRuleCreate = {
	permission: "",
	pattern: "*",
	action: "ask",
	user_id: null,
	thread_id: null,
};

function permissionRulesQueryKey(searchSpaceId: number) {
	return ["agent-permission-rules", searchSpaceId] as const;
}

function ScopeBadge({ rule }: { rule: AgentPermissionRule }) {
	if (rule.thread_id !== null) {
		return (
			<Badge variant="outline" className="text-[10px]">
				Thread #{rule.thread_id}
			</Badge>
		);
	}
	if (rule.user_id !== null) {
		return (
			<Badge variant="outline" className="text-[10px]">
				User-specific
			</Badge>
		);
	}
	return (
		<Badge variant="outline" className="text-[10px]">
			Search space
		</Badge>
	);
}

export function AgentPermissionsContent() {
	const searchSpaceIdRaw = useAtomValue(activeSearchSpaceIdAtom);
	const searchSpaceId = searchSpaceIdRaw ? Number(searchSpaceIdRaw) : null;

	const { data: flags } = useAtomValue(agentFlagsAtom);
	const featureEnabled = !!flags?.enable_permission && !flags?.disable_new_agent_stack;

	const queryClient = useQueryClient();

	const {
		data: rules,
		isLoading,
		isError,
		error,
	} = useQuery({
		queryKey: searchSpaceId
			? permissionRulesQueryKey(searchSpaceId)
			: ["agent-permission-rules", "none"],
		queryFn: () => agentPermissionsApiService.list(searchSpaceId as number),
		enabled: !!searchSpaceId && featureEnabled,
		staleTime: 60 * 1000,
	});

	const createMutation = useMutation({
		mutationFn: (payload: AgentPermissionRuleCreate) =>
			agentPermissionsApiService.create(searchSpaceId as number, payload),
		onSuccess: () => {
			toast.success("Rule created.");
			queryClient.invalidateQueries({
				queryKey: permissionRulesQueryKey(searchSpaceId as number),
			});
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to create rule.");
		},
	});

	const updateMutation = useMutation({
		mutationFn: (params: { ruleId: number; action: AgentPermissionAction; pattern?: string }) =>
			agentPermissionsApiService.update(searchSpaceId as number, params.ruleId, {
				action: params.action,
				pattern: params.pattern,
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: permissionRulesQueryKey(searchSpaceId as number),
			});
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to update rule.");
		},
	});

	const deleteMutation = useMutation({
		mutationFn: (ruleId: number) =>
			agentPermissionsApiService.remove(searchSpaceId as number, ruleId),
		onSuccess: () => {
			toast.success("Rule deleted.");
			queryClient.invalidateQueries({
				queryKey: permissionRulesQueryKey(searchSpaceId as number),
			});
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to delete rule.");
		},
	});

	const [showForm, setShowForm] = useState(false);
	const [formData, setFormData] = useState<AgentPermissionRuleCreate>(EMPTY_FORM);
	const [deleteTarget, setDeleteTarget] = useState<number | null>(null);

	const sortedRules = useMemo(() => rules ?? [], [rules]);

	const handleCreate = useCallback(async () => {
		if (!formData.permission.trim()) {
			toast.error("Permission is required.");
			return;
		}
		try {
			await createMutation.mutateAsync({
				...formData,
				permission: formData.permission.trim(),
				pattern: formData.pattern.trim() || "*",
			});
			setShowForm(false);
			setFormData(EMPTY_FORM);
		} catch (err) {
			if (err instanceof AppError && err.message) {
				// already toasted by onError
			}
		}
	}, [createMutation, formData]);

	const handleConfirmDelete = useCallback(async () => {
		if (deleteTarget === null) return;
		try {
			await deleteMutation.mutateAsync(deleteTarget);
		} finally {
			setDeleteTarget(null);
		}
	}, [deleteMutation, deleteTarget]);

	if (!featureEnabled) {
		return (
			<Alert className="border-dashed">
				<ShieldCheck className="size-4" />
				<AlertTitle>Permission middleware is disabled</AlertTitle>
				<AlertDescription>
					Flip{" "}
					<code className="rounded bg-muted px-1 text-[10px]">SURFSENSE_ENABLE_PERMISSION</code> on
					the backend to manage allow/deny/ask rules from this panel.
				</AlertDescription>
			</Alert>
		);
	}

	if (!searchSpaceId) {
		return (
			<p className="text-sm text-muted-foreground">Open a search space to manage agent rules.</p>
		);
	}

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner className="size-6" />
			</div>
		);
	}

	if (isError) {
		return (
			<div className="rounded-lg border border-dashed border-destructive/40 p-8 text-center">
				<AlertTriangle className="mx-auto size-8 text-destructive/60" />
				<p className="mt-2 text-sm text-destructive">Failed to load rules</p>
				<p className="text-xs text-muted-foreground">
					{error instanceof Error ? error.message : "Unknown error."}
				</p>
			</div>
		);
	}

	return (
		<div className="min-w-0 space-y-6 overflow-hidden">
			<div className="flex items-start justify-between gap-3">
				<div className="space-y-1">
					<p className="text-sm text-muted-foreground">
						Tell the agent which tools to allow, deny, or ask before running. Rules use wildcard
						patterns and are evaluated at the most specific scope first.
					</p>
				</div>
				{!showForm && (
					<Button
						size="sm"
						onClick={() => {
							setShowForm(true);
							setFormData(EMPTY_FORM);
						}}
						className="shrink-0 gap-1.5"
					>
						<Plus className="size-3.5" />
						New rule
					</Button>
				)}
			</div>

			{showForm && (
				<div className="rounded-lg border border-border/60 bg-card p-6">
					<div className="space-y-4">
						<h3 className="text-sm font-semibold tracking-tight">New permission rule</h3>

						<div className="grid grid-cols-2 gap-3">
							<div className="space-y-2">
								<Label htmlFor="permission-name">Permission</Label>
								<Input
									id="permission-name"
									value={formData.permission}
									placeholder="e.g. tool:create_linear_issue or tool:*"
									onChange={(e) => setFormData((p) => ({ ...p, permission: e.target.value }))}
								/>
								<p className="text-[11px] text-muted-foreground">
									Match a tool capability. Use <code className="font-mono">*</code> for wildcards.
								</p>
							</div>

							<div className="space-y-2">
								<Label htmlFor="pattern">Argument pattern</Label>
								<Input
									id="pattern"
									value={formData.pattern}
									placeholder="*"
									onChange={(e) => setFormData((p) => ({ ...p, pattern: e.target.value }))}
								/>
								<p className="text-[11px] text-muted-foreground">
									Wildcard against the canonical argument (e.g. <code>prod-*</code>).
								</p>
							</div>
						</div>

						<div className="space-y-2">
							<Label>Action</Label>
							<Select
								value={formData.action}
								onValueChange={(value) =>
									setFormData((p) => ({ ...p, action: value as AgentPermissionAction }))
								}
							>
								<SelectTrigger>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="allow">Allow — run without asking</SelectItem>
									<SelectItem value="ask">Ask — pause for approval</SelectItem>
									<SelectItem value="deny">Deny — block silently</SelectItem>
								</SelectContent>
							</Select>
							<p className="text-[11px] text-muted-foreground">
								{ACTION_DESCRIPTIONS[formData.action]}
							</p>
						</div>

						<div className="flex items-center justify-end gap-2 pt-2">
							<Button
								variant="ghost"
								size="sm"
								onClick={() => {
									setShowForm(false);
									setFormData(EMPTY_FORM);
								}}
								disabled={createMutation.isPending}
							>
								Cancel
							</Button>
							<Button
								size="sm"
								onClick={handleCreate}
								disabled={createMutation.isPending || !formData.permission.trim()}
								className="relative"
							>
								<span className={createMutation.isPending ? "opacity-0" : ""}>Create</span>
								{createMutation.isPending && <Spinner className="absolute size-3.5" />}
							</Button>
						</div>
					</div>
				</div>
			)}

			{sortedRules.length === 0 && !showForm && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<ShieldCheck className="mx-auto size-8 text-muted-foreground/40" />
					<p className="mt-2 text-sm text-muted-foreground">No rules yet</p>
					<p className="text-xs text-muted-foreground/60">
						Without rules the agent uses the deployment default for every tool.
					</p>
				</div>
			)}

			{sortedRules.length > 0 && (
				<div className="space-y-2">
					{sortedRules.map((rule) => {
						const badge = ACTION_BADGE[rule.action];
						const isUpdating =
							updateMutation.isPending && updateMutation.variables?.ruleId === rule.id;
						const isDeleting = deleteMutation.isPending && deleteMutation.variables === rule.id;

						return (
							<div
								key={rule.id}
								className="group flex flex-col gap-3 rounded-lg border border-border/60 bg-card p-4"
							>
								<div className="flex items-start justify-between gap-3">
									<div className="flex min-w-0 flex-1 flex-col gap-1.5">
										<div className="flex flex-wrap items-center gap-1.5">
											<code className="truncate rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
												{rule.permission}
											</code>
											{rule.pattern !== "*" && (
												<span className="text-xs text-muted-foreground">
													→ <code className="font-mono">{rule.pattern}</code>
												</span>
											)}
											<ScopeBadge rule={rule} />
										</div>
										<p className="text-[11px] text-muted-foreground">
											Created {formatRelativeDate(rule.created_at)}
										</p>
									</div>

									<div className="flex shrink-0 items-center gap-1">
										<Select
											value={rule.action}
											onValueChange={(value) =>
												updateMutation.mutate({
													ruleId: rule.id,
													action: value as AgentPermissionAction,
												})
											}
											disabled={isUpdating || isDeleting}
										>
											<SelectTrigger
												className={cn("h-8 gap-1 border px-2 text-[11px]", badge.className)}
											>
												<SelectValue>
													<span className="flex items-center gap-1">
														{rule.action === "allow" && <Check className="size-3" />}
														{rule.action === "deny" && <X className="size-3" />}
														{badge.label}
													</span>
												</SelectValue>
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="allow">Allow</SelectItem>
												<SelectItem value="ask">Ask</SelectItem>
												<SelectItem value="deny">Deny</SelectItem>
											</SelectContent>
										</Select>

										<Button
											size="sm"
											variant="ghost"
											className="size-8 p-0 text-muted-foreground hover:text-destructive"
											onClick={() => setDeleteTarget(rule.id)}
											disabled={isUpdating || isDeleting}
											aria-label="Delete rule"
										>
											<Trash2 className="size-3.5" />
										</Button>
									</div>
								</div>
							</div>
						);
					})}
				</div>
			)}

			<AlertDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Delete this rule?</AlertDialogTitle>
						<AlertDialogDescription>
							The agent will fall back to deployment defaults for matching tool calls.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							onClick={(e) => {
								e.preventDefault();
								handleConfirmDelete();
							}}
							disabled={deleteMutation.isPending}
						>
							{deleteMutation.isPending ? "Deleting…" : "Delete"}
						</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
