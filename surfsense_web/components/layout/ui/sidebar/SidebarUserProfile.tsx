"use client";

import { ChevronUp, LogOut, Settings } from "lucide-react";
import { useTranslations } from "next-intl";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { User } from "../../types/layout.types";

interface SidebarUserProfileProps {
	user: User;
	onUserSettings?: () => void;
	onLogout?: () => void;
	isCollapsed?: boolean;
}

/**
 * Generates a consistent color based on email
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1",
		"#8b5cf6",
		"#a855f7",
		"#d946ef",
		"#ec4899",
		"#f43f5e",
		"#ef4444",
		"#f97316",
		"#eab308",
		"#84cc16",
		"#22c55e",
		"#14b8a6",
		"#06b6d4",
		"#0ea5e9",
		"#3b82f6",
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from email
 */
function getInitials(email: string): string {
	const name = email.split("@")[0];
	const parts = name.split(/[._-]/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function SidebarUserProfile({
	user,
	onUserSettings,
	onLogout,
	isCollapsed = false,
}: SidebarUserProfileProps) {
	const t = useTranslations("sidebar");
	const bgColor = stringToColor(user.email);
	const initials = getInitials(user.email);
	const displayName = user.name || user.email.split("@")[0];

	// Collapsed view - just show avatar with dropdown
	if (isCollapsed) {
		return (
			<div className="border-t p-2">
				<DropdownMenu>
					<Tooltip>
						<TooltipTrigger asChild>
							<DropdownMenuTrigger asChild>
								<button
									type="button"
									className={cn(
										"flex h-10 w-full items-center justify-center rounded-md",
										"hover:bg-accent transition-colors",
										"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
									)}
								>
									<div
										className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold text-white"
										style={{ backgroundColor: bgColor }}
									>
										{initials}
									</div>
									<span className="sr-only">{displayName}</span>
								</button>
							</DropdownMenuTrigger>
						</TooltipTrigger>
						<TooltipContent side="right">{displayName}</TooltipContent>
					</Tooltip>

					<DropdownMenuContent className="w-56" side="right" align="end" sideOffset={8}>
						<DropdownMenuLabel className="font-normal">
							<div className="flex items-center gap-2">
								<div
									className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold text-white"
									style={{ backgroundColor: bgColor }}
								>
									{initials}
								</div>
								<div className="flex-1 min-w-0">
									<p className="truncate text-sm font-medium">{displayName}</p>
									<p className="truncate text-xs text-muted-foreground">{user.email}</p>
								</div>
							</div>
						</DropdownMenuLabel>

						<DropdownMenuSeparator />

						<DropdownMenuItem onClick={onUserSettings}>
							<Settings className="mr-2 h-4 w-4" />
							{t("user_settings")}
						</DropdownMenuItem>

						<DropdownMenuSeparator />

						<DropdownMenuItem onClick={onLogout}>
							<LogOut className="mr-2 h-4 w-4" />
							{t("logout")}
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		);
	}

	// Expanded view
	return (
		<div className="border-t">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<button
						type="button"
						className={cn(
							"flex w-full items-center gap-2 px-2 py-3 text-left",
							"hover:bg-accent transition-colors",
							"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						)}
					>
						{/* Avatar */}
						<div
							className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold text-white"
							style={{ backgroundColor: bgColor }}
						>
							{initials}
						</div>

						{/* Name and email */}
						<div className="flex-1 min-w-0">
							<p className="truncate text-sm font-medium">{displayName}</p>
							<p className="truncate text-xs text-muted-foreground">{user.email}</p>
						</div>

						{/* Chevron icon */}
						<ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
					</button>
				</DropdownMenuTrigger>

				<DropdownMenuContent className="w-56" side="top" align="start" sideOffset={4}>
					<DropdownMenuLabel className="font-normal">
						<div className="flex items-center gap-2">
							<div
								className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold text-white"
								style={{ backgroundColor: bgColor }}
							>
								{initials}
							</div>
							<div className="flex-1 min-w-0">
								<p className="truncate text-sm font-medium">{displayName}</p>
								<p className="truncate text-xs text-muted-foreground">{user.email}</p>
							</div>
						</div>
					</DropdownMenuLabel>

					<DropdownMenuSeparator />

					<DropdownMenuItem onClick={onUserSettings}>
						<Settings className="mr-2 h-4 w-4" />
						{t("user_settings")}
					</DropdownMenuItem>

					<DropdownMenuSeparator />

					<DropdownMenuItem onClick={onLogout}>
						<LogOut className="mr-2 h-4 w-4" />
						{t("logout")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
