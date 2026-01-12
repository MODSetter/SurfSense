"use client";

import { PanelLeft, PanelLeftClose } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface SidebarCollapseButtonProps {
	isCollapsed: boolean;
	onToggle: () => void;
}

export function SidebarCollapseButton({ isCollapsed, onToggle }: SidebarCollapseButtonProps) {
	const t = useTranslations("sidebar");

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button variant="ghost" size="icon" onClick={onToggle} className="h-8 w-8 shrink-0">
					{isCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
					<span className="sr-only">
						{isCollapsed ? t("expand_sidebar") : t("collapse_sidebar")}
					</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side={isCollapsed ? "right" : "bottom"}>
				{isCollapsed ? `${t("expand_sidebar")} (⌘B)` : `${t("collapse_sidebar")} (⌘B)`}
			</TooltipContent>
		</Tooltip>
	);
}
