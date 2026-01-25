"use client";

import { ArchiveIcon, MessageSquare, MoreHorizontal, RotateCcwIcon, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface ChatListItemProps {
	name: string;
	isActive?: boolean;
	archived?: boolean;
	onClick?: () => void;
	onArchive?: () => void;
	onDelete?: () => void;
}

export function ChatListItem({
	name,
	isActive,
	archived,
	onClick,
	onArchive,
	onDelete,
}: ChatListItemProps) {
	const t = useTranslations("sidebar");

	return (
		<div className="group/item relative w-full">
			<button
				type="button"
				onClick={onClick}
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

			{/* Actions dropdown */}
			<div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-100 md:opacity-0 md:group-hover/item:opacity-100 transition-opacity">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="ghost" size="icon" className="h-6 w-6">
							<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
							<span className="sr-only">{t("more_options")}</span>
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" side="right">
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
								className="text-destructive focus:text-destructive"
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
