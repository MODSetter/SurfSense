"use client";

import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface NavIconProps {
	icon: LucideIcon;
	label: string;
	isActive?: boolean;
	onClick?: () => void;
}

export function NavIcon({ icon: Icon, label, isActive, onClick }: NavIconProps) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					onClick={onClick}
					className={cn("h-10 w-10 rounded-lg", isActive && "bg-accent text-accent-foreground")}
				>
					<Icon className="h-5 w-5" />
					<span className="sr-only">{label}</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="right" sideOffset={8}>
				{label}
			</TooltipContent>
		</Tooltip>
	);
}
