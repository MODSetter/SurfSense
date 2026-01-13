"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { SearchSpace } from "../../types/layout.types";
import { SearchSpaceAvatar } from "./SearchSpaceAvatar";

interface IconRailProps {
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onAddSearchSpace: () => void;
	className?: string;
}

export function IconRail({
	searchSpaces,
	activeSearchSpaceId,
	onSearchSpaceSelect,
	onAddSearchSpace,
	className,
}: IconRailProps) {
	return (
		<div className={cn("flex h-full w-14 flex-col items-center", className)}>
			<ScrollArea className="w-full">
				<div className="flex flex-col items-center gap-2 px-1.5 py-3">
					{searchSpaces.map((searchSpace) => (
						<SearchSpaceAvatar
							key={searchSpace.id}
							name={searchSpace.name}
							isActive={searchSpace.id === activeSearchSpaceId}
							onClick={() => onSearchSpaceSelect(searchSpace.id)}
							size="md"
						/>
					))}

					<Tooltip>
						<TooltipTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								onClick={onAddSearchSpace}
								className="h-10 w-10 rounded-lg border-2 border-dashed border-muted-foreground/30 hover:border-muted-foreground/50"
							>
								<Plus className="h-5 w-5 text-muted-foreground" />
								<span className="sr-only">Add search space</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent side="right" sideOffset={8}>
							Add search space
						</TooltipContent>
					</Tooltip>
				</div>
			</ScrollArea>
		</div>
	);
}
