"use client";

import { PanelLeft } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ShortcutKbd } from "@/components/ui/shortcut-kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePlatformShortcut } from "@/hooks/use-platform-shortcut";
import { cn } from "@/lib/utils";

interface SidebarCollapseButtonProps {
	isCollapsed: boolean;
	onToggle: () => void;
	disableTooltip?: boolean;
	className?: string;
	iconClassName?: string;
}

export function SidebarCollapseButton({
	isCollapsed,
	onToggle,
	disableTooltip = false,
	className,
	iconClassName,
}: SidebarCollapseButtonProps) {
	const t = useTranslations("sidebar");
	const { shortcutKeys } = usePlatformShortcut();

	const button = (
		<Button
			variant="ghost"
			size="icon"
			onClick={onToggle}
			className={cn(
				"h-8 w-8 shrink-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground",
				className
			)}
		>
			<PanelLeft className={cn("h-4 w-4", iconClassName)} />
			<span className="sr-only">{isCollapsed ? t("expand_sidebar") : t("collapse_sidebar")}</span>
		</Button>
	);

	if (disableTooltip) {
		return button;
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>{button}</TooltipTrigger>
			<TooltipContent side="bottom" avoidCollisions={false}>
				<span className="flex items-center">
					{isCollapsed ? t("expand_sidebar") : t("collapse_sidebar")}
					<ShortcutKbd keys={shortcutKeys("Mod", "\\")} />
				</span>
			</TooltipContent>
		</Tooltip>
	);
}
