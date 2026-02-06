"use client";

import { Settings, Trash2, Users } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SearchSpaceAvatarProps {
	name: string;
	isActive?: boolean;
	isShared?: boolean;
	isOwner?: boolean;
	onClick?: () => void;
	onDelete?: () => void;
	onSettings?: () => void;
	size?: "sm" | "md";
	disableTooltip?: boolean;
}

/**
 * Generates a consistent color based on search space name
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1", // indigo
		"#22c55e", // green
		"#f59e0b", // amber
		"#ef4444", // red
		"#8b5cf6", // violet
		"#06b6d4", // cyan
		"#ec4899", // pink
		"#14b8a6", // teal
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from search space name (max 2 chars)
 */
function getInitials(name: string): string {
	const words = name.trim().split(/\s+/);
	if (words.length >= 2) {
		return (words[0][0] + words[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

export function SearchSpaceAvatar({
	name,
	isActive,
	isShared,
	isOwner = true,
	onClick,
	onDelete,
	onSettings,
	size = "md",
	disableTooltip = false,
}: SearchSpaceAvatarProps) {
	const t = useTranslations("searchSpace");
	const tCommon = useTranslations("common");
	const bgColor = stringToColor(name);
	const initials = getInitials(name);
	const sizeClasses = size === "sm" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

	// Long-press state for mobile
	const [longPressMenuOpen, setLongPressMenuOpen] = useState(false);
	const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
	const touchMoved = useRef(false);

	const handleTouchStart = useCallback(() => {
		touchMoved.current = false;
		longPressTimer.current = setTimeout(() => {
			if (!touchMoved.current) {
				setLongPressMenuOpen(true);
			}
		}, 500);
	}, []);

	const handleTouchMove = useCallback(() => {
		touchMoved.current = true;
		if (longPressTimer.current) {
			clearTimeout(longPressTimer.current);
			longPressTimer.current = null;
		}
	}, []);

	const handleTouchEnd = useCallback(() => {
		if (longPressTimer.current) {
			clearTimeout(longPressTimer.current);
			longPressTimer.current = null;
		}
	}, []);

	const tooltipContent = (
		<div className="flex flex-col">
			<span>{name}</span>
			{isShared && (
				<span className="text-xs text-muted-foreground">
					{isOwner ? tCommon("owner") : tCommon("shared")}
				</span>
			)}
		</div>
	);

	const avatarButton = (
		<button
			type="button"
			onClick={onClick}
			className={cn(
				"relative flex items-center justify-center rounded-lg font-semibold text-white transition-all",
				"hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
				sizeClasses,
				isActive && "ring-2 ring-primary ring-offset-1 ring-offset-background"
			)}
			style={{ backgroundColor: bgColor }}
		>
			{initials}
			{/* Shared indicator badge */}
			{isShared && (
				<span
					className={cn(
						"absolute -top-1 -right-1 flex items-center justify-center rounded-full bg-blue-500 text-white shadow-sm",
						size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"
					)}
					title={tCommon("shared")}
				>
					<Users className={cn(size === "sm" ? "h-2 w-2" : "h-2.5 w-2.5")} />
				</span>
			)}
		</button>
	);

	const menuItems = (
		<>
			{onSettings && (
				<DropdownMenuItem onClick={onSettings}>
					<Settings className="mr-2 h-4 w-4" />
					{tCommon("settings")}
				</DropdownMenuItem>
			)}
			{onSettings && onDelete && <DropdownMenuSeparator />}
			{onDelete && isOwner && (
				<DropdownMenuItem variant="destructive" onClick={onDelete}>
					<Trash2 className="mr-2 h-4 w-4" />
					{tCommon("delete")}
				</DropdownMenuItem>
			)}
			{onDelete && !isOwner && (
				<DropdownMenuItem variant="destructive" onClick={onDelete}>
					<Trash2 className="mr-2 h-4 w-4" />
					{t("leave")}
				</DropdownMenuItem>
			)}
		</>
	);

	// If delete or settings handlers are provided, wrap with context menu
	if (onDelete || onSettings) {
		// Mobile: use long-press triggered DropdownMenu
		if (disableTooltip) {
			return (
				<DropdownMenu open={longPressMenuOpen} onOpenChange={setLongPressMenuOpen}>
					<DropdownMenuTrigger asChild>
						<div
							className="inline-block"
							onTouchStart={handleTouchStart}
							onTouchMove={handleTouchMove}
							onTouchEnd={handleTouchEnd}
							onTouchCancel={handleTouchEnd}
						>
							{avatarButton}
						</div>
					</DropdownMenuTrigger>
					<DropdownMenuContent className="w-48">
						{menuItems}
					</DropdownMenuContent>
				</DropdownMenu>
			);
		}

		// Desktop: use right-click ContextMenu + Tooltip
		return (
			<ContextMenu>
				<Tooltip>
					<TooltipTrigger asChild>
						<ContextMenuTrigger asChild>
							<div className="inline-block">{avatarButton}</div>
						</ContextMenuTrigger>
					</TooltipTrigger>
					<TooltipContent side="right" sideOffset={8}>
						{tooltipContent}
					</TooltipContent>
				</Tooltip>
				<ContextMenuContent className="w-48">
					{onSettings && (
						<ContextMenuItem onClick={onSettings}>
							<Settings className="mr-2 h-4 w-4" />
							{tCommon("settings")}
						</ContextMenuItem>
					)}
					{onSettings && onDelete && <ContextMenuSeparator />}
					{onDelete && isOwner && (
						<ContextMenuItem variant="destructive" onClick={onDelete}>
							<Trash2 className="mr-2 h-4 w-4" />
							{tCommon("delete")}
						</ContextMenuItem>
					)}
					{onDelete && !isOwner && (
						<ContextMenuItem variant="destructive" onClick={onDelete}>
							<Trash2 className="mr-2 h-4 w-4" />
							{t("leave")}
						</ContextMenuItem>
					)}
				</ContextMenuContent>
			</ContextMenu>
		);
	}

	// No context menu needed
	if (disableTooltip) {
		return avatarButton;
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>{avatarButton}</TooltipTrigger>
			<TooltipContent side="right" sideOffset={8}>
				{tooltipContent}
			</TooltipContent>
		</Tooltip>
	);
}
