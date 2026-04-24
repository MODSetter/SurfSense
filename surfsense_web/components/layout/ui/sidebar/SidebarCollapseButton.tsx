"use client";

import { PanelLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ShortcutKbd } from "@/components/ui/shortcut-kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePlatformShortcut } from "@/hooks/use-platform-shortcut";

interface SidebarCollapseButtonProps {
	isCollapsed: boolean;
	onToggle: () => void;
	disableTooltip?: boolean;
}

export function SidebarCollapseButton({
	isCollapsed,
	onToggle,
	disableTooltip = false,
}: SidebarCollapseButtonProps) {
	const t = useTranslations("sidebar");
	const { shortcutKeys } = usePlatformShortcut();

	const button = (
		<Button variant="ghost" size="icon" onClick={onToggle} className="h-8 w-8 shrink-0">
			<PanelLeft className="h-4 w-4" />
			<span className="sr-only">{isCollapsed ? t("expand_sidebar") : t("collapse_sidebar")}</span>
		</Button>
	);

	if (disableTooltip) {
		return button;
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>{button}</TooltipTrigger>
			<TooltipContent side={isCollapsed ? "right" : "bottom"}>
				<span className="flex items-center">
					{isCollapsed ? t("expand_sidebar") : t("collapse_sidebar")}
					<ShortcutKbd keys={shortcutKeys("Mod", "\\")} />
				</span>
			</TooltipContent>
		</Tooltip>
	);
}
