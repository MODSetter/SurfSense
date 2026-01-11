"use client";

import { ChevronsUpDown, LayoutGrid, Settings, UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { Workspace } from "../../types/layout.types";

interface SidebarHeaderProps {
	workspace: Workspace | null;
	isCollapsed?: boolean;
	onSettings?: () => void;
	onInviteMembers?: () => void;
	onSeeAllWorkspaces?: () => void;
	className?: string;
}

export function SidebarHeader({
	workspace,
	isCollapsed,
	onSettings,
	onInviteMembers,
	onSeeAllWorkspaces,
	className,
}: SidebarHeaderProps) {
	const t = useTranslations("sidebar");

	return (
		<div className={cn("flex shrink-0 items-center", className)}>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						variant="ghost"
						className={cn(
							"flex h-auto items-center justify-between gap-2 overflow-hidden py-1.5 font-semibold",
							isCollapsed ? "w-10" : "w-50"
						)}
					>
						<span className="truncate text-base">{workspace?.name ?? t("select_workspace")}</span>
						<ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="start" className="w-56">
					<DropdownMenuItem onClick={onInviteMembers}>
						<UserPlus className="mr-2 h-4 w-4" />
						{t("invite_members")}
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={onSettings}>
						<Settings className="mr-2 h-4 w-4" />
						{t("workspace_settings")}
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={onSeeAllWorkspaces}>
						<LayoutGrid className="mr-2 h-4 w-4" />
						{t("see_all_workspaces")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
