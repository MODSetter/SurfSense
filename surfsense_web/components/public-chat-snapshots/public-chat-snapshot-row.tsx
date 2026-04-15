"use client";

import { Copy, Dot, ExternalLink, MessageSquare, MoreHorizontal, Trash2 } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { PublicChatSnapshotDetail } from "@/contracts/types/chat-threads.types";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

function getInitials(name: string): string {
	const parts = name.trim().split(/\s+/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

interface PublicChatSnapshotRowProps {
	snapshot: PublicChatSnapshotDetail;
	canDelete: boolean;
	onCopy: (snapshot: PublicChatSnapshotDetail) => void;
	onDelete: (snapshot: PublicChatSnapshotDetail) => void;
	isDeleting?: boolean;
	memberMap: Map<string, { name: string; email?: string; avatarUrl?: string }>;
}

export function PublicChatSnapshotRow({
	snapshot,
	canDelete,
	onCopy,
	onDelete,
	isDeleting = false,
	memberMap,
}: PublicChatSnapshotRowProps) {
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const isDesktop = useMediaQuery("(min-width: 768px)");

	const handleCopyClick = useCallback(() => {
		onCopy(snapshot);
		toast.success("Link copied to clipboard");
	}, [onCopy, snapshot]);

	const formattedDate = new Date(snapshot.created_at).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});

	const member = snapshot.created_by_user_id ? memberMap.get(snapshot.created_by_user_id) : null;

	return (
		<Card className="group relative overflow-hidden transition-all duration-200 border-border/60 hover:shadow-md h-full">
			<CardContent className="p-4 flex flex-col gap-3 h-full">
				{/* Header: Title + Actions */}
				<div className="relative flex items-center">
					<h4
						className={cn(
							"text-sm font-semibold tracking-tight truncate",
							dropdownOpen ? "pr-8" : "sm:group-hover:pr-8"
						)}
						title={snapshot.thread_title}
					>
						{snapshot.thread_title}
					</h4>
					<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
						<DropdownMenuTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className={cn(
									"absolute right-0 h-6 w-6 shrink-0 hover:bg-transparent",
									dropdownOpen ? "opacity-100" : "sm:opacity-0 sm:group-hover:opacity-100"
								)}
							>
								<MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" className="w-40">
							<DropdownMenuItem onClick={handleCopyClick}>
								<Copy className="mr-2 h-4 w-4" />
								Copy link
							</DropdownMenuItem>
							<DropdownMenuItem asChild>
								<a href={snapshot.public_url} target="_blank" rel="noopener noreferrer">
									<ExternalLink className="mr-2 h-4 w-4" />
									Open link
								</a>
							</DropdownMenuItem>
							{canDelete && (
								<DropdownMenuItem onClick={() => onDelete(snapshot)} disabled={isDeleting}>
									<Trash2 className="mr-2 h-4 w-4" />
									Delete
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				</div>

				{/* Message count badge */}
				<div className="flex items-center gap-1.5">
					<Badge
						variant="secondary"
						className="text-[10px] px-1.5 py-0.5 border-0 text-muted-foreground bg-muted"
					>
						<MessageSquare className="h-2.5 w-2.5 mr-1" />
						{snapshot.message_count} messages
					</Badge>
				</div>

				{/* Footer: Date + Creator */}
				<div className="flex items-center gap-2 pt-2 border-t border-border/40 mt-auto">
					<span className="text-[11px] text-muted-foreground/60">{formattedDate}</span>
					{member && (
						<>
							<Dot className="h-4 w-4 text-muted-foreground/30" />
							<TooltipProvider>
								<Tooltip open={isDesktop ? undefined : false}>
									<TooltipTrigger asChild>
										<div className="flex items-center gap-1.5 cursor-default">
											<Avatar className="size-4.5 shrink-0">
												{member.avatarUrl && (
													<AvatarImage src={member.avatarUrl} alt={member.name} />
												)}
												<AvatarFallback className="text-[9px]">
													{getInitials(member.name)}
												</AvatarFallback>
											</Avatar>
											<span className="text-[11px] text-muted-foreground/60 truncate max-w-[120px]">
												{member.name}
											</span>
										</div>
									</TooltipTrigger>
									<TooltipContent side="bottom">{member.email || member.name}</TooltipContent>
								</Tooltip>
							</TooltipProvider>
						</>
					)}
				</div>
			</CardContent>
		</Card>
	);
}
