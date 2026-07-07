"use client";

import { Plus, SquarePen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { NavItem, User, Workspace } from "../../types/layout.types";
import {
	NotificationsDropdown,
	type NotificationsDropdownData,
} from "../sidebar/NotificationsDropdown";
import { SidebarUserProfile } from "../sidebar/SidebarUserProfile";
import { WorkspaceAvatar } from "./WorkspaceAvatar";

interface IconRailProps {
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
	onWorkspaceDelete?: (workspace: Workspace) => void;
	onWorkspaceSettings?: (workspace: Workspace) => void;
	onAddWorkspace: () => void;
	isSingleRailMode?: boolean;
	onNewChat?: () => void;
	navItems?: NavItem[];
	onNavItemClick?: (item: NavItem) => void;
	user: User;
	onUserSettings?: () => void;
	onAnnouncements?: () => void;
	announcementUnreadCount?: number;
	notifications?: NotificationsDropdownData;
	onLogout?: () => void;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	className?: string;
}

export function IconRail({
	workspaces,
	activeWorkspaceId,
	onWorkspaceSelect,
	onWorkspaceDelete,
	onWorkspaceSettings,
	onAddWorkspace,
	isSingleRailMode = false,
	onNewChat,
	navItems = [],
	onNavItemClick,
	user,
	onUserSettings,
	onAnnouncements,
	announcementUnreadCount = 0,
	notifications,
	onLogout,
	theme,
	setTheme,
	className,
}: IconRailProps) {
	const actionItems = isSingleRailMode
		? [
				...(onNewChat
					? [
							{
								key: "new-chat",
								label: "New chat",
								onClick: onNewChat,
								icon: SquarePen,
								isActive: false,
							},
						]
					: []),
				...navItems.map((item) => ({
					key: item.url,
					label: item.title,
					onClick: () => onNavItemClick?.(item),
					icon: item.icon,
					isActive: !!item.isActive,
				})),
			]
		: [];

	return (
		<div className={cn("flex h-full w-14 min-h-0 flex-col items-center", className)}>
			<ScrollArea className="w-full min-h-0 flex-1">
				<div className="flex flex-col items-center gap-2 px-1.5 py-3">
					{workspaces.map((workspace) => (
						<WorkspaceAvatar
							key={workspace.id}
							name={workspace.name}
							isActive={workspace.id === activeWorkspaceId}
							isShared={workspace.memberCount > 1}
							isOwner={workspace.isOwner}
							onClick={() => onWorkspaceSelect(workspace.id)}
							onDelete={onWorkspaceDelete ? () => onWorkspaceDelete(workspace) : undefined}
							onSettings={onWorkspaceSettings ? () => onWorkspaceSettings(workspace) : undefined}
							size="md"
						/>
					))}

					<Tooltip>
						<TooltipTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								onClick={onAddWorkspace}
								className="h-10 w-10 rounded-lg border-2 border-dashed border-muted-foreground/30 hover:border-muted-foreground/50"
							>
								<Plus className="h-5 w-5 text-muted-foreground" />
								<span className="sr-only">Add workspace</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="right" sideOffset={8}>
							Add workspace
						</TooltipContent>
					</Tooltip>

					{actionItems.length > 0 && (
						<>
							<div className="my-1 h-px w-8 bg-border/60" />
							{actionItems.map(({ key, label, onClick, icon: Icon, isActive }) => (
								<Tooltip key={key}>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											onClick={onClick}
											className={cn(
												"h-10 w-10 rounded-lg",
												isActive && "bg-accent text-accent-foreground"
											)}
										>
											<Icon className="h-4 w-4" />
											<span className="sr-only">{label}</span>
										</Button>
									</TooltipTrigger>
									<TooltipContent side="right" sideOffset={8}>
										{label}
									</TooltipContent>
								</Tooltip>
							))}
						</>
					)}
				</div>
			</ScrollArea>
			<SidebarUserProfile
				user={user}
				onUserSettings={onUserSettings}
				onAnnouncements={onAnnouncements}
				announcementUnreadCount={announcementUnreadCount}
				onLogout={onLogout}
				isCollapsed
				theme={theme}
				setTheme={setTheme}
				topContent={
					notifications ? <NotificationsDropdown notifications={notifications} /> : undefined
				}
			/>
		</div>
	);
}
