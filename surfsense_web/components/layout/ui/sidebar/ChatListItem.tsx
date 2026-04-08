"use client";

import { ArchiveIcon, MoreHorizontal, PenLine, RotateCcwIcon, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLongPress } from "@/hooks/use-long-press";
import { useIsMobile } from "@/hooks/use-mobile";
import { useTypewriter } from "@/hooks/use-typewriter";
import { cn } from "@/lib/utils";

interface ChatListItemProps {
	name: string;
	isActive?: boolean;
	archived?: boolean;
	dropdownOpen?: boolean;
	onDropdownOpenChange?: (open: boolean) => void;
	onClick?: () => void;
	onRename?: () => void;
	onArchive?: () => void;
	onDelete?: () => void;
}

export function ChatListItem({
	name,
	isActive,
	archived,
	dropdownOpen: controlledOpen,
	onDropdownOpenChange,
	onClick,
	onRename,
	onArchive,
	onDelete,
}: ChatListItemProps) {
	const t = useTranslations("sidebar");
	const isMobile = useIsMobile();
	const [internalOpen, setInternalOpen] = useState(false);
	const dropdownOpen = controlledOpen ?? internalOpen;
	const setDropdownOpen = onDropdownOpenChange ?? setInternalOpen;
	const animatedName = useTypewriter(name);

	const { handlers: longPressHandlers, wasLongPress } = useLongPress(
		useCallback(() => setDropdownOpen(true), [setDropdownOpen])
	);

	const handleClick = useCallback(() => {
		if (wasLongPress()) return;
		onClick?.();
	}, [onClick, wasLongPress]);

	return (
		<div className="group/item relative w-full">
			<button
				type="button"
				onClick={handleClick}
				{...(isMobile ? longPressHandlers : {})}
				className={cn(
					"flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-sm text-left",
					"group-hover/item:bg-accent group-hover/item:text-accent-foreground",
					"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
					isActive && "bg-accent text-accent-foreground"
				)}
			>
				<span className="truncate">{animatedName}</span>
			</button>

			{/* Actions dropdown - trigger hidden on mobile, long-press opens it instead */}
			<div
				className={cn(
					"pointer-events-none absolute right-0 top-0 bottom-0 flex items-center pr-1 pl-6 rounded-r-md",
					isActive
						? "bg-gradient-to-l from-accent from-60% to-transparent"
						: "bg-gradient-to-l from-sidebar from-60% to-transparent group-hover/item:from-accent",
					isMobile
						? "opacity-0"
						: isActive || dropdownOpen
							? "opacity-100"
							: "opacity-0 group-hover/item:opacity-100"
				)}
			>
				<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
					<DropdownMenuTrigger asChild>
						<Button
							variant="ghost"
							size="icon"
							className={cn(
								"pointer-events-auto h-6 w-6 hover:bg-transparent",
								dropdownOpen && "bg-accent hover:bg-accent"
							)}
						>
							<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
							<span className="sr-only">{t("more_options")}</span>
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" side="bottom">
						{onRename && (
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									onRename();
								}}
							>
								<PenLine className="mr-2 h-4 w-4" />
								<span>{t("rename") || "Rename"}</span>
							</DropdownMenuItem>
						)}
						{onArchive && (
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									onArchive();
								}}
							>
								{archived ? (
									<>
										<RotateCcwIcon className="mr-2 h-4 w-4" />
										<span>{t("unarchive") || "Restore"}</span>
									</>
								) : (
									<>
										<ArchiveIcon className="mr-2 h-4 w-4" />
										<span>{t("archive") || "Archive"}</span>
									</>
								)}
							</DropdownMenuItem>
						)}
						{onDelete && (
							<DropdownMenuItem
								onClick={(e) => {
									e.stopPropagation();
									onDelete();
								}}
							>
								<Trash2 className="mr-2 h-4 w-4" />
								<span>{t("delete")}</span>
							</DropdownMenuItem>
						)}
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</div>
	);
}
