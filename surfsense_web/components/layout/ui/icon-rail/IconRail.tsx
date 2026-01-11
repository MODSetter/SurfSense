"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { Workspace } from "../../types/layout.types";
import { WorkspaceAvatar } from "./WorkspaceAvatar";

interface IconRailProps {
	workspaces: Workspace[];
	activeWorkspaceId: number | null;
	onWorkspaceSelect: (id: number) => void;
	onAddWorkspace: () => void;
	className?: string;
}

export function IconRail({
	workspaces,
	activeWorkspaceId,
	onWorkspaceSelect,
	onAddWorkspace,
	className,
}: IconRailProps) {
	return (
		<div className={cn("flex h-full w-14 flex-col items-center", className)}>
			<ScrollArea className="w-full">
				<div className="flex flex-col items-center gap-2 px-1.5 py-3">
					{workspaces.map((workspace) => (
						<WorkspaceAvatar
							key={workspace.id}
							name={workspace.name}
							isActive={workspace.id === activeWorkspaceId}
							onClick={() => onWorkspaceSelect(workspace.id)}
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
				</div>
			</ScrollArea>
		</div>
	);
}
