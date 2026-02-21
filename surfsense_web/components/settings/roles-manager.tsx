"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	Bot,
	Check,
	Crown,
	Edit2,
	FileText,
	Globe,
	type LucideIcon,
	MessageCircle,
	MessageSquare,
	Mic,
	MoreHorizontal,
	Plug,
	Plus,
	Logs,
	Settings,
	Shield,
	ShieldCheck,
	Trash2,
	Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	createRoleMutationAtom,
	deleteRoleMutationAtom,
	updateRoleMutationAtom,
} from "@/atoms/roles/roles-mutation.atoms";
import { permissionsAtom } from "@/atoms/permissions/permissions-query.atoms";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
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

const ACTION_DISPLAY: Record<string, { label: string; color: string }> = {
	create: { label: "Create", color: "text-emerald-600 bg-emerald-500/10" },
	read: { label: "View", color: "text-blue-600 bg-blue-500/10" },
	update: { label: "Edit", color: "text-amber-600 bg-amber-500/10" },
	delete: { label: "Delete", color: "text-red-600 bg-red-500/10" },
	invite: { label: "Invite", color: "text-violet-600 bg-violet-500/10" },
	view: { label: "View", color: "text-blue-600 bg-blue-500/10" },
	remove: { label: "Remove", color: "text-red-600 bg-red-500/10" },
	manage_roles: {
		label: "Manage Roles",
		color: "text-violet-600 bg-violet-500/10",
	},
};

const ROLE_PRESETS = {
	editor: {
		name: "Editor",
		description:
			"Can create, read, and update content, but cannot delete or manage team settings",
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

	const {
		data: roles = [],
		isLoading: rolesLoading,
	} = useQuery({
		queryKey: cacheKeys.roles.all(searchSpaceId.toString()),
		queryFn: () =>
			rolesApiService.getRoles({ search_space_id: searchSpaceId }),
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

function RolePermissionsDisplay({
	permissions,
}: {
	permissions: string[];
}) {
	if (permissions.includes("*")) {
		return (
			<div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
				<div className="h-10 w-10 rounded-full bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center shrink-0">
					<Crown className="h-5 w-5 text-white" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="text-sm font-semibold">Full Access</p>
					<p className="text-xs text-muted-foreground">
						All permissions granted
					</p>
				</div>
			</div>
		);
	}

	const grouped: Record<string, string[]> = {};
	for (const perm of permissions) {
		const [category, action] = perm.split(":");
		if (!grouped[category]) grouped[category] = [];
		grouped[category].push(action);
	}

	const sortedCategories = Object.keys(grouped).sort((a, b) => {
		const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
		const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
		return orderA - orderB;
	});

	const categoryCount = sortedCategories.length;

	return (
		<Dialog>
			<DialogTrigger asChild>
				<button
					type="button"
					className="w-full flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer text-left"
				>
					<div className="flex items-center gap-3">
						<div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
							<ShieldCheck className="h-5 w-5 text-primary" />
						</div>
						<div>
							<p className="text-sm font-semibold">
								{permissions.length} Permissions
							</p>
							<p className="text-xs text-muted-foreground">
								Across {categoryCount}{" "}
								{categoryCount === 1 ? "category" : "categories"}
							</p>
						</div>
					</div>
					<div className="text-xs text-muted-foreground">View details</div>
				</button>
			</DialogTrigger>
			<DialogContent className="w-[92vw] max-w-md p-0 gap-0">
				<DialogHeader className="p-4 md:p-5 border-b">
					<DialogTitle className="flex items-center gap-2 text-base">
						<ShieldCheck className="h-4 w-4 text-primary" />
						Role Permissions
					</DialogTitle>
					<DialogDescription className="text-xs">
						{permissions.length} permissions across {categoryCount} categories
					</DialogDescription>
				</DialogHeader>
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
										<span className="text-sm text-muted-foreground">
											{config.label}
										</span>
									</div>
									<div className="flex flex-wrap justify-end gap-1">
										{actions.map((action) => (
											<span
												key={action}
												className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium"
											>
												{ACTION_LABELS[action] ||
													action.replace(/_/g, " ")}
											</span>
										))}
									</div>
								</div>
							);
						})}
					</div>
				</ScrollArea>
			</DialogContent>
		</Dialog>
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

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="space-y-6"
		>
			{canCreate && !showCreateRole && (
				<motion.div
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					className="flex justify-end"
				>
					<Button onClick={() => setShowCreateRole(true)} className="gap-2">
						<Plus className="h-4 w-4" />
						Create Custom Role
					</Button>
				</motion.div>
			)}

			{showCreateRole && (
				<CreateRoleSection
					groupedPermissions={groupedPermissions}
					onCreateRole={onCreateRole}
					onCancel={() => setShowCreateRole(false)}
				/>
			)}

			{editingRoleId !== null &&
				(() => {
					const roleToEdit = roles.find((r) => r.id === editingRoleId);
					if (!roleToEdit) return null;
					return (
						<EditRoleSection
							role={roleToEdit}
							groupedPermissions={groupedPermissions}
							onUpdateRole={onUpdateRole}
							onCancel={() => setEditingRoleId(null)}
						/>
					);
				})()}

			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
				{roles.map((role, index) => (
					<motion.div
						key={role.id}
						initial={{ opacity: 0, scale: 0.95 }}
						animate={{ opacity: 1, scale: 1 }}
						transition={{ delay: index * 0.05 }}
					>
						<Card
							className={cn(
								"relative overflow-hidden transition-all hover:shadow-lg",
								role.is_system_role && "ring-1 ring-primary/20"
							)}
						>
							{role.is_system_role && (
								<div className="absolute top-0 right-0 px-2 py-1 bg-primary/10 text-primary text-xs font-medium rounded-bl-lg">
									System Role
								</div>
							)}
							<CardHeader>
								<div className="flex items-start justify-between">
									<div className="flex items-center gap-3">
										<div
											className={cn(
												"h-10 w-10 rounded-lg flex items-center justify-center",
												role.name === "Owner" && "bg-amber-500/20",
												role.name === "Editor" && "bg-blue-500/20",
												role.name === "Viewer" && "bg-gray-500/20",
												!["Owner", "Editor", "Viewer"].includes(
													role.name
												) && "bg-primary/20"
											)}
										>
											<ShieldCheck
												className={cn(
													"h-5 w-5",
													role.name === "Owner" && "text-amber-600",
													role.name === "Editor" && "text-blue-600",
													role.name === "Viewer" && "text-gray-600",
													!["Owner", "Editor", "Viewer"].includes(
														role.name
													) && "text-primary"
												)}
											/>
										</div>
										<div>
											<CardTitle className="text-lg">
												{role.name}
											</CardTitle>
											{role.is_default && (
												<Badge
													variant="outline"
													className="text-xs mt-1"
												>
													Default
												</Badge>
											)}
										</div>
									</div>
									{!role.is_system_role && (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button
													variant="ghost"
													size="icon"
													className="h-8 w-8"
												>
													<MoreHorizontal className="h-4 w-4" />
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent
												align="end"
												onCloseAutoFocus={(e) =>
													e.preventDefault()
												}
											>
												{canUpdate && (
													<DropdownMenuItem
														onClick={() =>
															setEditingRoleId(role.id)
														}
													>
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
																	onSelect={(e) =>
																		e.preventDefault()
																	}
																>
																	<Trash2 className="h-4 w-4 mr-2" />
																	Delete Role
																</DropdownMenuItem>
															</AlertDialogTrigger>
															<AlertDialogContent>
																<AlertDialogHeader>
																	<AlertDialogTitle>
																		Delete role?
																	</AlertDialogTitle>
																	<AlertDialogDescription>
																		This will permanently
																		delete the &quot;
																		{role.name}&quot; role.
																		Members with this role
																		will lose their
																		permissions.
																	</AlertDialogDescription>
																</AlertDialogHeader>
																<AlertDialogFooter>
																	<AlertDialogCancel>
																		Cancel
																	</AlertDialogCancel>
																	<AlertDialogAction
																		onClick={() =>
																			onDeleteRole(
																				role.id
																			)
																		}
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
									)}
								</div>
								{role.description && (
									<CardDescription className="mt-2">
										{role.description}
									</CardDescription>
								)}
							</CardHeader>
							<CardContent>
								<RolePermissionsDisplay
									permissions={role.permissions}
								/>
							</CardContent>
						</Card>
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
			prev.includes(category)
				? prev.filter((c) => c !== category)
				: [...prev, category]
		);
	}, []);

	const getCategoryStats = useCallback(
		(category: string) => {
			const perms = groupedPermissions[category] || [];
			const selected = perms.filter((p) =>
				selectedPermissions.includes(p.value)
			).length;
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
							expandedCategories.length === sortedCategories.length
								? []
								: sortedCategories
						)
					}
				>
					{expandedCategories.length === sortedCategories.length
						? "Collapse All"
						: "Expand All"}
				</Button>
			</div>

			<div className="space-y-2">
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
						<div
							key={category}
							className="rounded-lg border bg-card overflow-hidden"
						>
							<button
								type="button"
								className={cn(
									"w-full flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 transition-colors",
									stats.allSelected && "bg-primary/5"
								)}
								onClick={() => toggleCategoryExpanded(category)}
							>
								<div className="flex items-center gap-3">
									<div
										className={cn(
											"h-8 w-8 rounded-lg flex items-center justify-center",
											stats.selected > 0
												? "bg-primary/10"
												: "bg-muted"
										)}
									>
										<IconComponent
											className={cn(
												"h-4 w-4",
												stats.selected > 0
													? "text-primary"
													: "text-muted-foreground"
											)}
										/>
									</div>
									<div>
										<div className="flex items-center gap-2">
											<span className="font-medium text-sm">
												{config.label}
											</span>
											<Badge
												variant={
													stats.selected > 0
														? "default"
														: "secondary"
												}
												className="text-xs h-5"
											>
												{stats.selected}/{stats.total}
											</Badge>
										</div>
										<p className="text-xs text-muted-foreground hidden md:block">
											{config.description}
										</p>
									</div>
								</div>
								<div className="flex items-center gap-2">
									<Checkbox
										checked={stats.allSelected}
										onCheckedChange={() =>
											onToggleCategory(category)
										}
										onClick={(e) => e.stopPropagation()}
										aria-label={`Select all ${config.label} permissions`}
									/>
									<motion.div
										animate={{
											rotate: isExpanded ? 180 : 0,
										}}
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
									className="border-t"
								>
									<div className="p-3 space-y-1">
										{perms.map((perm) => {
											const action =
												perm.value.split(":")[1];
											const actionConfig =
												ACTION_DISPLAY[action] || {
													label: action,
													color: "text-gray-600 bg-gray-500/10",
												};
											const isSelected =
												selectedPermissions.includes(
													perm.value
												);

											return (
												<button
													key={perm.value}
													type="button"
													className={cn(
														"w-full flex items-center justify-between p-2 rounded-md cursor-pointer transition-colors",
														isSelected
															? "bg-primary/10 hover:bg-primary/15"
															: "hover:bg-muted/50"
													)}
													onClick={() =>
														onTogglePermission(
															perm.value
														)
													}
												>
													<div className="flex items-center gap-3 flex-1 min-w-0">
														<Checkbox
															checked={isSelected}
															onCheckedChange={() =>
																onTogglePermission(
																	perm.value
																)
															}
															onClick={(e) =>
																e.stopPropagation()
															}
														/>
														<div className="flex-1 min-w-0">
															<div className="flex items-center gap-2">
																<span
																	className={cn(
																		"text-xs font-medium px-2 py-0.5 rounded",
																		actionConfig.color
																	)}
																>
																	{
																		actionConfig.label
																	}
																</span>
															</div>
															<p className="text-xs text-muted-foreground mt-0.5 truncate">
																{
																	perm.description
																}
															</p>
														</div>
													</div>
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

// ============ Create Role Section ============

function CreateRoleSection({
	groupedPermissions,
	onCreateRole,
	onCancel,
}: {
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	onCreateRole: (data: CreateRoleRequest["data"]) => Promise<Role>;
	onCancel: () => void;
}) {
	const [creating, setCreating] = useState(false);
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
	const [isDefault, setIsDefault] = useState(false);

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
			onCancel();
		} catch (error) {
			console.error("Failed to create role:", error);
		} finally {
			setCreating(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm)
				? prev.filter((p) => p !== perm)
				: [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms =
				groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) =>
				selectedPermissions.includes(p)
			);

			if (allSelected) {
				setSelectedPermissions((prev) =>
					prev.filter((p) => !categoryPerms.includes(p))
				);
			} else {
				setSelectedPermissions((prev) => [
					...new Set([...prev, ...categoryPerms]),
				]);
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
		<motion.div
			initial={{ opacity: 0, y: -10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="mb-6"
		>
			<Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
				<CardHeader className="pb-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-3">
							<div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
								<Plus className="h-5 w-5 text-primary" />
							</div>
							<div>
								<CardTitle className="text-lg">
									Create Custom Role
								</CardTitle>
								<CardDescription className="text-sm">
									Define permissions for a new role in this
									search space
								</CardDescription>
							</div>
						</div>
						<Button variant="ghost" size="icon" onClick={onCancel}>
							<Trash2 className="h-4 w-4" />
						</Button>
					</div>
				</CardHeader>
				<CardContent className="space-y-6">
					{/* Quick Start with Presets */}
					<div className="space-y-3">
						<Label className="text-sm font-medium">
							Quick Start with a Template
						</Label>
						<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
							{Object.entries(ROLE_PRESETS).map(
								([key, preset]) => (
									<button
										key={key}
										type="button"
										onClick={() =>
											applyPreset(
												key as keyof typeof ROLE_PRESETS
											)
										}
										className={cn(
											"p-4 rounded-lg border-2 text-left transition-all hover:border-primary/50 hover:bg-primary/5",
											selectedPermissions.length > 0 &&
												preset.permissions.every((p) =>
													selectedPermissions.includes(
														p
													)
												)
												? "border-primary bg-primary/10"
												: "border-border"
										)}
									>
										<div className="flex items-center gap-2 mb-1">
											<ShieldCheck
												className={cn(
													"h-4 w-4",
													key === "editor" &&
														"text-blue-600",
													key === "viewer" &&
														"text-gray-600",
													key === "contributor" &&
														"text-emerald-600"
												)}
											/>
											<span className="font-medium text-sm">
												{preset.name}
											</span>
										</div>
										<p className="text-xs text-muted-foreground">
											{preset.description}
										</p>
									</button>
								)
							)}
						</div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label htmlFor="role-name">Role Name *</Label>
							<Input
								id="role-name"
								placeholder="e.g., Content Manager"
								value={name}
								onChange={(e) => setName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="role-description">
								Description
							</Label>
							<Input
								id="role-description"
								placeholder="Brief description of this role"
								value={description}
								onChange={(e) => setDescription(e.target.value)}
							/>
						</div>
					</div>

					<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
						<Checkbox
							id="is-default"
							checked={isDefault}
							onCheckedChange={(checked) =>
								setIsDefault(checked === true)
							}
						/>
						<div className="flex-1">
							<Label
								htmlFor="is-default"
								className="cursor-pointer font-medium"
							>
								Set as default role
							</Label>
							<p className="text-xs text-muted-foreground">
								New members without a specific role will be
								assigned this role
							</p>
						</div>
					</div>

					<PermissionsEditor
						groupedPermissions={groupedPermissions}
						selectedPermissions={selectedPermissions}
						onTogglePermission={togglePermission}
						onToggleCategory={toggleCategory}
					/>

					<div className="flex items-center justify-end gap-3 pt-4 border-t">
						<Button variant="outline" onClick={onCancel}>
							Cancel
						</Button>
						<Button
							onClick={handleCreate}
							disabled={creating || !name.trim()}
						>
							{creating ? (
								<>
									<Spinner size="sm" className="mr-2" />
									Creating...
								</>
							) : (
								<>
									<Check className="h-4 w-4 mr-2" />
									Create Role
								</>
							)}
						</Button>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}

// ============ Edit Role Section ============

function EditRoleSection({
	role,
	groupedPermissions,
	onUpdateRole,
	onCancel,
}: {
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
	onCancel: () => void;
}) {
	const [saving, setSaving] = useState(false);
	const [name, setName] = useState(role.name);
	const [description, setDescription] = useState(role.description || "");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>(
		role.permissions
	);
	const [isDefault, setIsDefault] = useState(role.is_default);

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
			onCancel();
		} catch (error) {
			console.error("Failed to update role:", error);
			toast.error("Failed to update role");
		} finally {
			setSaving(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm)
				? prev.filter((p) => p !== perm)
				: [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms =
				groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) =>
				selectedPermissions.includes(p)
			);

			if (allSelected) {
				setSelectedPermissions((prev) =>
					prev.filter((p) => !categoryPerms.includes(p))
				);
			} else {
				setSelectedPermissions((prev) => [
					...new Set([...prev, ...categoryPerms]),
				]);
			}
		},
		[groupedPermissions, selectedPermissions]
	);

	return (
		<motion.div
			initial={{ opacity: 0, y: -10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="mb-6"
		>
			<Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
				<CardHeader className="pb-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-3">
							<div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
								<Edit2 className="h-5 w-5 text-primary" />
							</div>
							<div>
								<CardTitle className="text-lg">
									Edit Role
								</CardTitle>
								<CardDescription className="text-sm">
									Modify permissions for &quot;{role.name}
									&quot;
								</CardDescription>
							</div>
						</div>
						<Button variant="ghost" size="icon" onClick={onCancel}>
							<Trash2 className="h-4 w-4" />
						</Button>
					</div>
				</CardHeader>
				<CardContent className="space-y-6">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label htmlFor="edit-role-name">
								Role Name *
							</Label>
							<Input
								id="edit-role-name"
								placeholder="e.g., Content Manager"
								value={name}
								onChange={(e) => setName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="edit-role-description">
								Description
							</Label>
							<Input
								id="edit-role-description"
								placeholder="Brief description of this role"
								value={description}
								onChange={(e) => setDescription(e.target.value)}
							/>
						</div>
					</div>

					<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
						<Checkbox
							id="edit-is-default"
							checked={isDefault}
							onCheckedChange={(checked) =>
								setIsDefault(checked === true)
							}
						/>
						<div className="flex-1">
							<Label
								htmlFor="edit-is-default"
								className="cursor-pointer font-medium"
							>
								Set as default role
							</Label>
							<p className="text-xs text-muted-foreground">
								New members without a specific role will be
								assigned this role
							</p>
						</div>
					</div>

					<PermissionsEditor
						groupedPermissions={groupedPermissions}
						selectedPermissions={selectedPermissions}
						onTogglePermission={togglePermission}
						onToggleCategory={toggleCategory}
					/>

					<div className="flex items-center justify-end gap-3 pt-4 border-t">
						<Button variant="outline" onClick={onCancel}>
							Cancel
						</Button>
						<Button
							onClick={handleSave}
							disabled={saving || !name.trim()}
						>
							{saving ? (
								<>
									<Spinner size="sm" className="mr-2" />
									Saving...
								</>
							) : (
								<>
									<Check className="h-4 w-4 mr-2" />
									Save Changes
								</>
							)}
						</Button>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
