"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	Bot,
	Edit2,
	FileText,
	Globe,
	Logs,
	type LucideIcon,
	MessageCircle,
	MessageSquare,
	Mic,
	MoreHorizontal,
	Plug,
	Plus,
	Settings,
	Shield,
	Trash2,
	Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import { permissionsAtom } from "@/atoms/permissions/permissions-query.atoms";
import {
	createRoleMutationAtom,
	deleteRoleMutationAtom,
	updateRoleMutationAtom,
} from "@/atoms/roles/roles-mutation.atoms";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import type { PermissionInfo } from "@/contracts/types/permissions.types";
import type {
	CreateRoleRequest,
	DeleteRoleRequest,
	Role,
	UpdateRoleRequest,
} from "@/contracts/types/roles.types";
import { rolesApiService } from "@/lib/apis/roles-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

const CATEGORY_CONFIG: Record<
	string,
	{ label: string; icon: LucideIcon; description: string; order: number }
> = {
	documents: {
		label: "Documents",
		icon: FileText,
		description: "Manage files, notes, and content",
		order: 1,
	},
	chats: {
		label: "AI Chats",
		icon: MessageSquare,
		description: "Create and manage AI conversations",
		order: 2,
	},
	comments: {
		label: "Comments",
		icon: MessageCircle,
		description: "Add annotations to documents",
		order: 3,
	},
	llm_configs: {
		label: "AI Models",
		icon: Bot,
		description: "Configure AI model settings",
		order: 4,
	},
	podcasts: {
		label: "Podcasts",
		icon: Mic,
		description: "Generate AI podcasts from content",
		order: 5,
	},
	connectors: {
		label: "Integrations",
		icon: Plug,
		description: "Connect external data sources",
		order: 6,
	},
	logs: {
		label: "Activity Logs",
		icon: Logs,
		description: "View and manage audit trail",
		order: 7,
	},
	members: {
		label: "Team Members",
		icon: Users,
		description: "Manage team membership",
		order: 8,
	},
	roles: {
		label: "Roles",
		icon: Shield,
		description: "Configure role permissions",
		order: 9,
	},
	settings: {
		label: "Settings",
		icon: Settings,
		description: "Manage search space settings",
		order: 10,
	},
	public_sharing: {
		label: "Public Chat Sharing",
		icon: Globe,
		description: "Share chats publicly via links",
		order: 11,
	},
};

const ACTION_LABELS: Record<string, string> = {
	create: "Create",
	read: "Read",
	update: "Update",
	delete: "Delete",
	invite: "Invite",
	view: "View",
	remove: "Remove",
	manage_roles: "Manage Roles",
};

const ROLE_PRESETS = {
	editor: {
		name: "Editor",
		description: "Create, read, and edit content. No delete or admin access.",
		permissions: [
			"documents:create",
			"documents:read",
			"documents:update",
			"chats:create",
			"chats:read",
			"chats:update",
			"comments:create",
			"comments:read",
			"llm_configs:create",
			"llm_configs:read",
			"llm_configs:update",
			"podcasts:create",
			"podcasts:read",
			"podcasts:update",
			"connectors:create",
			"connectors:read",
			"connectors:update",
			"logs:read",
			"members:invite",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
	viewer: {
		name: "Viewer",
		description: "Read-only access with ability to add comments",
		permissions: [
			"documents:read",
			"chats:read",
			"comments:create",
			"comments:read",
			"llm_configs:read",
			"podcasts:read",
			"connectors:read",
			"logs:read",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
	contributor: {
		name: "Contributor",
		description: "Can add and manage their own content",
		permissions: [
			"documents:create",
			"documents:read",
			"documents:update",
			"chats:create",
			"chats:read",
			"comments:create",
			"comments:read",
			"llm_configs:read",
			"podcasts:read",
			"connectors:read",
			"logs:read",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
};

type PermissionWithDescription = PermissionInfo;

// ============ Roles Manager (for Settings page) ============

export function RolesManager({ searchSpaceId }: { searchSpaceId: number }) {
	const { data: access = null } = useAtomValue(myAccessAtom);

	const hasPermission = useCallback(
		(permission: string) => {
			if (!access) return false;
			if (access.is_owner) return true;
			return access.permissions?.includes(permission) ?? false;
		},
		[access]
	);

	const { data: roles = [], isLoading: rolesLoading } = useQuery({
		queryKey: cacheKeys.roles.all(searchSpaceId.toString()),
		queryFn: () => rolesApiService.getRoles({ search_space_id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { data: permissionsData } = useAtomValue(permissionsAtom);
	const permissions = permissionsData?.permissions || [];
	const groupedPermissions = useMemo(() => {
		const groups: Record<string, typeof permissions> = {};
		for (const perm of permissions) {
			if (!groups[perm.category]) {
				groups[perm.category] = [];
			}
			groups[perm.category].push(perm);
		}
		return groups;
	}, [permissions]);

	const { mutateAsync: createRole } = useAtomValue(createRoleMutationAtom);
	const { mutateAsync: updateRole } = useAtomValue(updateRoleMutationAtom);
	const { mutateAsync: deleteRole } = useAtomValue(deleteRoleMutationAtom);

	const handleUpdateRole = useCallback(
		async (
			roleId: number,
			data: {
				name?: string;
				description?: string | null;
				permissions?: string[];
				is_default?: boolean;
			}
		): Promise<Role> => {
			const request: UpdateRoleRequest = {
				search_space_id: searchSpaceId,
				role_id: roleId,
				data: data,
			};
			return await updateRole(request);
		},
		[updateRole, searchSpaceId]
	);

	const handleDeleteRole = useCallback(
		async (roleId: number): Promise<boolean> => {
			const request: DeleteRoleRequest = {
				search_space_id: searchSpaceId,
				role_id: roleId,
			};
			await deleteRole(request);
			return true;
		},
		[deleteRole, searchSpaceId]
	);

	const handleCreateRole = useCallback(
		async (roleData: CreateRoleRequest["data"]): Promise<Role> => {
			const request: CreateRoleRequest = {
				search_space_id: searchSpaceId,
				data: roleData,
			};
			return await createRole(request);
		},
		[createRole, searchSpaceId]
	);

	return (
		<RolesContent
			roles={roles}
			groupedPermissions={groupedPermissions}
			loading={rolesLoading}
			onUpdateRole={handleUpdateRole}
			onDeleteRole={handleDeleteRole}
			onCreateRole={handleCreateRole}
			canUpdate={hasPermission("roles:update")}
			canDelete={hasPermission("roles:delete")}
			canCreate={hasPermission("roles:create")}
		/>
	);
}

// ============ Role Permissions Display ============

function RolePermissionsDialog({
	permissions,
	roleName,
	children,
}: {
	permissions: string[];
	roleName: string;
	children: React.ReactNode;
}) {
	const isFullAccess = permissions.includes("*");

	const grouped: Record<string, string[]> = {};
	if (!isFullAccess) {
		for (const perm of permissions) {
			const [category, action] = perm.split(":");
			if (!grouped[category]) grouped[category] = [];
			grouped[category].push(action);
		}
	}

	const sortedCategories = Object.keys(grouped).sort((a, b) => {
		const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
		const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
		return orderA - orderB;
	});

	const categoryCount = sortedCategories.length;

	return (
		<Dialog>
			<DialogTrigger asChild>{children}</DialogTrigger>
			<DialogContent className="w-[92vw] max-w-md p-0 gap-0">
				<DialogHeader className="p-4 md:p-5">
					<DialogTitle className="text-base">{roleName} — Permissions</DialogTitle>
					<DialogDescription className="text-xs">
						{isFullAccess
							? "This role has unrestricted access to all resources"
							: `${permissions.length} permissions across ${categoryCount} categories`}
					</DialogDescription>
				</DialogHeader>
				{isFullAccess ? (
					<div className="flex items-center gap-3 px-4 md:px-5 py-6">
						<div className="h-9 w-9 rounded-lg bg-muted/60 flex items-center justify-center shrink-0">
							<Shield className="h-4 w-4 text-muted-foreground" />
						</div>
						<div>
							<p className="text-sm font-medium">Full access</p>
							<p className="text-xs text-muted-foreground">
								All permissions granted across every category
							</p>
						</div>
					</div>
				) : (
					<ScrollArea className="max-h-[55vh]">
						<div className="divide-y divide-border/50">
							{sortedCategories.map((category) => {
								const actions = grouped[category];
								const config = CATEGORY_CONFIG[category] || {
									label: category,
									icon: FileText,
								};
								const IconComponent = config.icon;
								return (
									<div
										key={category}
										className="flex items-center justify-between gap-3 px-4 md:px-5 py-2.5"
									>
										<div className="flex items-center gap-2 shrink-0">
											<IconComponent className="h-3.5 w-3.5 text-muted-foreground" />
											<span className="text-sm text-muted-foreground">{config.label}</span>
										</div>
										<div className="flex flex-wrap justify-end gap-1">
											{actions.map((action) => (
												<span
													key={action}
													className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground text-[11px] font-medium"
												>
													{ACTION_LABELS[action] || action.replace(/_/g, " ")}
												</span>
											))}
										</div>
									</div>
								);
							})}
						</div>
					</ScrollArea>
				)}
			</DialogContent>
		</Dialog>
	);
}

function PermissionsBadge({ permissions }: { permissions: string[] }) {
	if (permissions.includes("*")) {
		return (
			<div className="px-2.5 py-1 rounded-md bg-muted/50 border border-border/60 text-muted-foreground">
				<span className="text-xs font-medium whitespace-nowrap">Full access</span>
			</div>
		);
	}
	return (
		<div className="px-2.5 py-1 rounded-md border border-border/60 bg-muted/50 text-muted-foreground">
			<span className="text-xs font-medium whitespace-nowrap">
				{permissions.length} permissions
			</span>
		</div>
	);
}

// ============ Roles Content ============

function RolesContent({
	roles,
	groupedPermissions,
	loading,
	onUpdateRole,
	onDeleteRole,
	onCreateRole,
	canUpdate,
	canDelete,
	canCreate,
}: {
	roles: Role[];
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	loading: boolean;
	onUpdateRole: (
		roleId: number,
		data: {
			name?: string;
			description?: string | null;
			permissions?: string[];
			is_default?: boolean;
		}
	) => Promise<Role>;
	onDeleteRole: (roleId: number) => Promise<boolean>;
	onCreateRole: (data: CreateRoleRequest["data"]) => Promise<Role>;
	canUpdate: boolean;
	canDelete: boolean;
	canCreate: boolean;
}) {
	const [showCreateRole, setShowCreateRole] = useState(false);
	const [editingRoleId, setEditingRoleId] = useState<number | null>(null);

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-primary" />
			</div>
		);
	}

	const editingRole = editingRoleId !== null ? roles.find((r) => r.id === editingRoleId) : null;

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="space-y-6"
		>
			{canCreate && (
				<div className="flex justify-end">
					<Button
						variant="outline"
						onClick={() => setShowCreateRole(true)}
						className="gap-2 bg-white text-black hover:bg-neutral-100 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
					>
						<Plus className="h-4 w-4" />
						Create Custom Role
					</Button>
				</div>
			)}

			<CreateRoleDialog
				open={showCreateRole}
				onOpenChange={setShowCreateRole}
				groupedPermissions={groupedPermissions}
				onCreateRole={onCreateRole}
			/>

			{editingRole && (
				<EditRoleDialog
					open={!!editingRole}
					onOpenChange={(open) => {
						if (!open) setEditingRoleId(null);
					}}
					role={editingRole}
					groupedPermissions={groupedPermissions}
					onUpdateRole={onUpdateRole}
				/>
			)}

			<div className="space-y-3">
				{roles.map((role, index) => (
					<motion.div
						key={role.id}
						initial={{ opacity: 0, y: 6 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: index * 0.04 }}
					>
						<RolePermissionsDialog permissions={role.permissions} roleName={role.name}>
							<button
								type="button"
								className="w-full text-left relative flex items-center gap-4 rounded-lg border border-border/60 p-4 transition-colors hover:bg-muted/30 cursor-pointer"
							>
								<div className="flex-1 min-w-0">
									<div className="flex items-center gap-2">
										<span className="font-medium text-sm">{role.name}</span>
										{role.is_system_role && (
											<span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
												System
											</span>
										)}
										{role.is_default && (
											<span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
												Default
											</span>
										)}
									</div>
									{role.description && (
										<p className="text-xs text-muted-foreground mt-0.5 truncate">
											{role.description}
										</p>
									)}
								</div>

								<div className="shrink-0">
									<PermissionsBadge permissions={role.permissions} />
								</div>

								{!role.is_system_role && (
									<div
										className="shrink-0"
										role="none"
										onClick={(e) => e.stopPropagation()}
										onKeyDown={(e) => e.stopPropagation()}
									>
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button variant="ghost" size="icon" className="h-8 w-8">
													<MoreHorizontal className="h-4 w-4" />
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end" onCloseAutoFocus={(e) => e.preventDefault()}>
												{canUpdate && (
													<DropdownMenuItem onClick={() => setEditingRoleId(role.id)}>
														<Edit2 className="h-4 w-4 mr-2" />
														Edit Role
													</DropdownMenuItem>
												)}
												{canDelete && (
													<>
														<DropdownMenuSeparator />
														<AlertDialog>
															<AlertDialogTrigger asChild>
																<DropdownMenuItem
																	className="text-destructive focus:text-destructive"
																	onSelect={(e) => e.preventDefault()}
																>
																	<Trash2 className="h-4 w-4 mr-2" />
																	Delete Role
																</DropdownMenuItem>
															</AlertDialogTrigger>
															<AlertDialogContent>
																<AlertDialogHeader>
																	<AlertDialogTitle>Delete role?</AlertDialogTitle>
																	<AlertDialogDescription>
																		This will permanently delete the &quot;{role.name}&quot; role.
																		Members with this role will lose their permissions.
																	</AlertDialogDescription>
																</AlertDialogHeader>
																<AlertDialogFooter>
																	<AlertDialogCancel>Cancel</AlertDialogCancel>
																	<AlertDialogAction
																		onClick={() => onDeleteRole(role.id)}
																		className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
																	>
																		Delete
																	</AlertDialogAction>
																</AlertDialogFooter>
															</AlertDialogContent>
														</AlertDialog>
													</>
												)}
											</DropdownMenuContent>
										</DropdownMenu>
									</div>
								)}
							</button>
						</RolePermissionsDialog>
					</motion.div>
				))}
			</div>
		</motion.div>
	);
}

// ============ Permissions Editor (shared by Create and Edit) ============

function PermissionsEditor({
	groupedPermissions,
	selectedPermissions,
	onTogglePermission,
	onToggleCategory,
}: {
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	selectedPermissions: string[];
	onTogglePermission: (perm: string) => void;
	onToggleCategory: (category: string) => void;
}) {
	const [expandedCategories, setExpandedCategories] = useState<string[]>([]);

	const sortedCategories = useMemo(() => {
		return Object.keys(groupedPermissions).sort((a, b) => {
			const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
			const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
			return orderA - orderB;
		});
	}, [groupedPermissions]);

	const toggleCategoryExpanded = useCallback((category: string) => {
		setExpandedCategories((prev) =>
			prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
		);
	}, []);

	const getCategoryStats = useCallback(
		(category: string) => {
			const perms = groupedPermissions[category] || [];
			const selected = perms.filter((p) => selectedPermissions.includes(p.value)).length;
			return {
				selected,
				total: perms.length,
				allSelected: selected === perms.length,
			};
		},
		[groupedPermissions, selectedPermissions]
	);

	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between">
				<Label className="text-sm font-medium">
					Permissions ({selectedPermissions.length} selected)
				</Label>
				<Button
					type="button"
					variant="ghost"
					size="sm"
					className="text-xs h-7"
					onClick={() =>
						setExpandedCategories(
							expandedCategories.length === sortedCategories.length ? [] : sortedCategories
						)
					}
				>
					{expandedCategories.length === sortedCategories.length ? "Collapse All" : "Expand All"}
				</Button>
			</div>

			<div className="space-y-1.5">
				{sortedCategories.map((category) => {
					const config = CATEGORY_CONFIG[category] || {
						label: category,
						icon: FileText,
						description: "",
						order: 99,
					};
					const IconComponent = config.icon;
					const stats = getCategoryStats(category);
					const isExpanded = expandedCategories.includes(category);
					const perms = groupedPermissions[category] || [];

					return (
						<div key={category} className="rounded-lg border border-border/60 overflow-hidden">
							<button
								type="button"
								className="w-full flex items-center justify-between px-3 py-2.5 cursor-pointer hover:bg-muted/40 transition-colors"
								onClick={() => toggleCategoryExpanded(category)}
							>
								<div className="flex items-center gap-2.5">
									<IconComponent className="h-4 w-4 text-muted-foreground shrink-0" />
									<span className="font-medium text-sm">{config.label}</span>
									<span className="text-[11px] text-muted-foreground tabular-nums">
										{stats.selected}/{stats.total}
									</span>
								</div>
								<div className="flex items-center gap-2">
									<Checkbox
										checked={stats.allSelected}
										onCheckedChange={() => onToggleCategory(category)}
										onClick={(e) => e.stopPropagation()}
										aria-label={`Select all ${config.label} permissions`}
									/>
									<motion.div
										animate={{ rotate: isExpanded ? 180 : 0 }}
										transition={{ duration: 0.2 }}
									>
										<svg
											className="h-4 w-4 text-muted-foreground"
											fill="none"
											viewBox="0 0 24 24"
											stroke="currentColor"
											aria-hidden="true"
										>
											<title>Toggle</title>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2}
												d="M19 9l-7 7-7-7"
											/>
										</svg>
									</motion.div>
								</div>
							</button>

							{isExpanded && (
								<motion.div
									initial={{ height: 0, opacity: 0 }}
									animate={{ height: "auto", opacity: 1 }}
									exit={{ height: 0, opacity: 0 }}
									transition={{ duration: 0.2 }}
									className="border-t border-border/60"
								>
									<div className="p-2 space-y-0.5">
										{perms.map((perm) => {
											const action = perm.value.split(":")[1];
											const actionLabel = ACTION_LABELS[action] || action.replace(/_/g, " ");
											const isSelected = selectedPermissions.includes(perm.value);

											return (
												<button
													key={perm.value}
													type="button"
													className={cn(
														"w-full flex items-center justify-between gap-3 px-2.5 py-2 rounded-md cursor-pointer transition-colors",
														isSelected ? "bg-muted/60 hover:bg-muted/80" : "hover:bg-muted/40"
													)}
													onClick={() => onTogglePermission(perm.value)}
												>
													<div className="flex-1 min-w-0 text-left">
														<span className="text-sm font-medium">{actionLabel}</span>
														<p className="text-xs text-muted-foreground truncate">
															{perm.description}
														</p>
													</div>
													<Checkbox
														checked={isSelected}
														onCheckedChange={() => onTogglePermission(perm.value)}
														onClick={(e) => e.stopPropagation()}
														className="shrink-0"
													/>
												</button>
											);
										})}
									</div>
								</motion.div>
							)}
						</div>
					);
				})}
			</div>
		</div>
	);
}

// ============ Create Role Dialog ============

function CreateRoleDialog({
	open,
	onOpenChange,
	groupedPermissions,
	onCreateRole,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	onCreateRole: (data: CreateRoleRequest["data"]) => Promise<Role>;
}) {
	const [creating, setCreating] = useState(false);
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
	const [isDefault, setIsDefault] = useState(false);

	const handleClose = () => {
		onOpenChange(false);
		setName("");
		setDescription("");
		setSelectedPermissions([]);
		setIsDefault(false);
	};

	const handleCreate = async () => {
		if (!name.trim()) {
			toast.error("Please enter a role name");
			return;
		}

		setCreating(true);
		try {
			await onCreateRole({
				name: name.trim(),
				description: description.trim() || null,
				permissions: selectedPermissions,
				is_default: isDefault,
			});
			handleClose();
		} catch (error) {
			console.error("Failed to create role:", error);
		} finally {
			setCreating(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms = groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) => selectedPermissions.includes(p));

			if (allSelected) {
				setSelectedPermissions((prev) => prev.filter((p) => !categoryPerms.includes(p)));
			} else {
				setSelectedPermissions((prev) => [...new Set([...prev, ...categoryPerms])]);
			}
		},
		[groupedPermissions, selectedPermissions]
	);

	const applyPreset = useCallback(
		(presetKey: keyof typeof ROLE_PRESETS) => {
			const preset = ROLE_PRESETS[presetKey];
			setSelectedPermissions(preset.permissions);
			if (!name.trim()) {
				setName(preset.name);
				setDescription(preset.description);
			}
			toast.success(`Applied ${preset.name} preset`);
		},
		[name]
	);

	return (
		<Dialog open={open} onOpenChange={(v) => (v ? onOpenChange(true) : handleClose())}>
			<DialogContent className="!flex !flex-col w-[92vw] max-w-[92vw] sm:max-w-2xl p-0 gap-0 max-h-[85vh] overflow-hidden">
				<DialogHeader className="px-5 pt-5 pb-4 shrink-0">
					<DialogTitle className="text-lg">Create Custom Role</DialogTitle>
					<DialogDescription className="text-sm text-muted-foreground">
						Define permissions for a new role in this search space
					</DialogDescription>
				</DialogHeader>
				<div className="flex-1 min-h-0 overflow-y-auto">
					<div className="px-5 py-5 space-y-5">
						<div className="space-y-2">
							<Label className="text-sm font-medium">Start from a template</Label>
							<div className="grid grid-cols-3 gap-2">
								{Object.entries(ROLE_PRESETS).map(([key, preset]) => (
									<button
										key={key}
										type="button"
										onClick={() => applyPreset(key as keyof typeof ROLE_PRESETS)}
										className={cn(
											"p-3 rounded-lg border text-left transition-colors hover:bg-muted/40",
											selectedPermissions.length > 0 &&
												preset.permissions.every((p) => selectedPermissions.includes(p))
												? "border-foreground/30 bg-muted/40"
												: "border-border/60"
										)}
									>
										<span className="font-medium text-sm">{preset.name}</span>
										<p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
											{preset.description}
										</p>
									</button>
								))}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-3">
							<div className="space-y-1.5">
								<Label htmlFor="role-name">Role Name *</Label>
								<Input
									id="role-name"
									placeholder="e.g., Content Manager"
									value={name}
									onChange={(e) => setName(e.target.value)}
								/>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="role-description">Description</Label>
								<Input
									id="role-description"
									placeholder="Brief description of this role"
									value={description}
									onChange={(e) => setDescription(e.target.value)}
								/>
							</div>
						</div>

						<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/40">
							<Checkbox
								id="is-default"
								checked={isDefault}
								onCheckedChange={(checked) => setIsDefault(checked === true)}
							/>
							<div className="flex-1">
								<Label htmlFor="is-default" className="cursor-pointer font-medium text-sm">
									Set as default role
								</Label>
								<p className="text-xs text-muted-foreground">
									New members without a specific role will be assigned this role
								</p>
							</div>
						</div>

						<PermissionsEditor
							groupedPermissions={groupedPermissions}
							selectedPermissions={selectedPermissions}
							onTogglePermission={togglePermission}
							onToggleCategory={toggleCategory}
						/>
					</div>
				</div>
				<div className="flex items-center justify-end gap-3 px-5 py-3 shrink-0">
					<Button variant="outline" onClick={handleClose}>
						Cancel
					</Button>
					<Button onClick={handleCreate} disabled={creating || !name.trim()}>
						{creating ? (
							<>
								<Spinner size="sm" className="mr-2" />
								Creating
							</>
						) : (
							"Create Role"
						)}
					</Button>
				</div>
			</DialogContent>
		</Dialog>
	);
}

// ============ Edit Role Dialog ============

function EditRoleDialog({
	open,
	onOpenChange,
	role,
	groupedPermissions,
	onUpdateRole,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	role: Role;
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	onUpdateRole: (
		roleId: number,
		data: {
			name?: string;
			description?: string | null;
			permissions?: string[];
			is_default?: boolean;
		}
	) => Promise<Role>;
}) {
	const [saving, setSaving] = useState(false);
	const [name, setName] = useState(role.name);
	const [description, setDescription] = useState(role.description || "");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>(role.permissions);
	const [isDefault, setIsDefault] = useState(role.is_default);

	useEffect(() => {
		if (open) {
			setName(role.name);
			setDescription(role.description || "");
			setSelectedPermissions(role.permissions);
			setIsDefault(role.is_default);
		}
	}, [open, role]);

	const handleSave = async () => {
		if (!name.trim()) {
			toast.error("Please enter a role name");
			return;
		}

		setSaving(true);
		try {
			await onUpdateRole(role.id, {
				name: name.trim(),
				description: description.trim() || null,
				permissions: selectedPermissions,
				is_default: isDefault,
			});
			toast.success("Role updated successfully");
			onOpenChange(false);
		} catch (error) {
			console.error("Failed to update role:", error);
			toast.error("Failed to update role");
		} finally {
			setSaving(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms = groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) => selectedPermissions.includes(p));

			if (allSelected) {
				setSelectedPermissions((prev) => prev.filter((p) => !categoryPerms.includes(p)));
			} else {
				setSelectedPermissions((prev) => [...new Set([...prev, ...categoryPerms])]);
			}
		},
		[groupedPermissions, selectedPermissions]
	);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!flex !flex-col w-[92vw] max-w-[92vw] sm:max-w-2xl p-0 gap-0 max-h-[85vh] overflow-hidden">
				<DialogHeader className="px-5 py-4 shrink-0">
					<DialogTitle className="text-base">Edit Role</DialogTitle>
					<DialogDescription className="text-xs">
						Modify permissions for &quot;{role.name}&quot;
					</DialogDescription>
				</DialogHeader>
				<div className="flex-1 min-h-0 overflow-y-auto">
					<div className="px-5 py-5 space-y-5">
						<div className="grid grid-cols-2 gap-3">
							<div className="space-y-1.5">
								<Label htmlFor="edit-role-name">Role Name *</Label>
								<Input
									id="edit-role-name"
									placeholder="e.g., Content Manager"
									value={name}
									onChange={(e) => setName(e.target.value)}
								/>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="edit-role-description">Description</Label>
								<Input
									id="edit-role-description"
									placeholder="Brief description of this role"
									value={description}
									onChange={(e) => setDescription(e.target.value)}
								/>
							</div>
						</div>

						<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/40">
							<Checkbox
								id="edit-is-default"
								checked={isDefault}
								onCheckedChange={(checked) => setIsDefault(checked === true)}
							/>
							<div className="flex-1">
								<Label htmlFor="edit-is-default" className="cursor-pointer font-medium text-sm">
									Set as default role
								</Label>
								<p className="text-xs text-muted-foreground">
									New members without a specific role will be assigned this role
								</p>
							</div>
						</div>

						<PermissionsEditor
							groupedPermissions={groupedPermissions}
							selectedPermissions={selectedPermissions}
							onTogglePermission={togglePermission}
							onToggleCategory={toggleCategory}
						/>
					</div>
				</div>
				<div className="flex items-center justify-end gap-3 px-5 py-3 border-t shrink-0">
					<Button variant="outline" onClick={() => onOpenChange(false)}>
						Cancel
					</Button>
					<Button onClick={handleSave} disabled={saving || !name.trim()}>
						{saving ? (
							<>
								<Spinner size="sm" className="mr-2" />
								Saving...
							</>
						) : (
							"Save Changes"
						)}
					</Button>
				</div>
			</DialogContent>
		</Dialog>
	);
}
