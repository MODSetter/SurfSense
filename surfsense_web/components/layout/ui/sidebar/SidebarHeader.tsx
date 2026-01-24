"use client";

import { ChevronsUpDown, Logs, Settings, Users } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
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
import type { SearchSpace } from "../../types/layout.types";

interface SidebarHeaderProps {
	searchSpace: SearchSpace | null;
	isCollapsed?: boolean;
	onSettings?: () => void;
	onManageMembers?: () => void;
	className?: string;
}

export function SidebarHeader({
	searchSpace,
	isCollapsed,
	onSettings,
	onManageMembers,
	className,
}: SidebarHeaderProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;

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
						<span className="truncate text-base">
							{searchSpace?.name ?? t("select_search_space")}
						</span>
						<ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="start" className="w-56">
					<DropdownMenuItem onClick={onManageMembers}>
						<Users className="mr-2 h-4 w-4" />
						{t("manage_members")}
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/${searchSpaceId}/logs`)}>
						<Logs className="mr-2 h-4 w-4" />
						{t("logs")}
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={onSettings}>
						<Settings className="mr-2 h-4 w-4" />
						{t("search_space_settings")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
