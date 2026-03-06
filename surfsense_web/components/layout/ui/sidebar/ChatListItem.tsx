"use client";

import { useCallback, useState } from "react";
import {
	ArchiveIcon,
	MessageSquare,
	MoreHorizontal,
	PenLine,
	RotateCcwIcon,
	Trash2,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useIsMobile } from "@/hooks/use-mobile";
import { useLongPress } from "@/hooks/use-long-press";
import { cn } from "@/lib/utils";

interface ChatListItemProps {
	name: string;
	isActive?: boolean;
	archived?: boolean;
	onClick?: () => void;
	onRename?: () => void;
	onArchive?: () => void;
	onDelete?: () => void;
}

export function ChatListItem({
	name,
	isActive,
	archived,
	onClick,
	onRename,
	onArchive,
	onDelete,
}: ChatListItemProps) {
	const t = useTranslations("sidebar");
	const isMobile = useIsMobile();
	const [dropdownOpen, setDropdownOpen] = useState(false);

	const { handlers: longPressHandlers, wasLongPress } = useLongPress(
		useCallback(() => setDropdownOpen(true), [])
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
					"flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-sm text-left transition-colors",
					"[&>span:last-child]:truncate",
					"hover:bg-accent hover:text-accent-foreground",
					"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
					isActive && "bg-accent text-accent-foreground"
				)}
			>
				<MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
				<span className="w-[calc(100%-3rem)] ">{name}</span>
			</button>

			{/* Actions dropdown - trigger hidden on mobile, long-press opens it instead */}
			<div className={cn(
				"absolute right-1 top-1/2 -translate-y-1/2 transition-opacity",
				isMobile
					? "opacity-0 pointer-events-none"
					: "opacity-0 group-hover/item:opacity-100"
			)}>
				<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
					<DropdownMenuTrigger asChild>
						<Button variant="ghost" size="icon" className="h-6 w-6">
							<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
							<span className="sr-only">{t("more_options")}</span>
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" side="right">
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
						{onArchive && onDelete && <DropdownMenuSeparator />}
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
