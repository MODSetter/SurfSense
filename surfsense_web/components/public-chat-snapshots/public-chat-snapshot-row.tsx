"use client";

import { Check, Copy, ExternalLink, MessageSquare, Trash2 } from "lucide-react";
import Image from "next/image";
import { useCallback, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { PublicChatSnapshotDetail } from "@/contracts/types/chat-threads.types";

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
	const [copied, setCopied] = useState(false);
	const copyTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null);

	const handleCopyClick = useCallback(() => {
		onCopy(snapshot);
		setCopied(true);
		if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
		copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
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
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0 flex-1">
						<h4
							className="text-sm font-semibold tracking-tight truncate"
							title={snapshot.thread_title}
						>
							{snapshot.thread_title}
						</h4>
					</div>
					<div className="flex items-center gap-0.5 shrink-0 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-150">
						<TooltipProvider>
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										asChild
										className="h-7 w-7 text-muted-foreground hover:text-foreground"
									>
										<a href={snapshot.public_url} target="_blank" rel="noopener noreferrer">
											<ExternalLink className="h-3 w-3" />
										</a>
									</Button>
								</TooltipTrigger>
								<TooltipContent>Open link</TooltipContent>
							</Tooltip>
						</TooltipProvider>
						{canDelete && (
							<TooltipProvider>
								<Tooltip>
									<TooltipTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											onClick={() => onDelete(snapshot)}
											disabled={isDeleting}
											className="h-7 w-7 text-muted-foreground hover:text-destructive"
										>
											<Trash2 className="h-3 w-3" />
										</Button>
									</TooltipTrigger>
									<TooltipContent>Delete</TooltipContent>
								</Tooltip>
							</TooltipProvider>
						)}
					</div>
				</div>

				{/* Message count badge */}
				<div className="flex items-center gap-1.5">
					<Badge
						variant="outline"
						className="text-[10px] px-1.5 py-0.5 border-muted-foreground/20 text-muted-foreground"
					>
						<MessageSquare className="h-2.5 w-2.5 mr-1" />
						{snapshot.message_count} messages
					</Badge>
				</div>

				{/* Public URL – selectable fallback for manual copy */}
				<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5">
					<div className="min-w-0 flex-1 overflow-x-auto scrollbar-hide">
						<p
							className="text-[10px] font-mono text-muted-foreground whitespace-nowrap select-all cursor-text"
							title={snapshot.public_url}
						>
							{snapshot.public_url}
						</p>
					</div>
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									onClick={handleCopyClick}
									className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
								>
									{copied ? (
										<Check className="h-3 w-3 text-green-500" />
									) : (
										<Copy className="h-3 w-3" />
									)}
								</Button>
							</TooltipTrigger>
							<TooltipContent>{copied ? "Copied!" : "Copy link"}</TooltipContent>
						</Tooltip>
					</TooltipProvider>
				</div>

				{/* Footer: Date + Creator */}
				<div className="flex items-center gap-2 pt-2 border-t border-border/40 mt-auto">
					<span className="text-[11px] text-muted-foreground/60">{formattedDate}</span>
					{member && (
						<>
							<span className="text-muted-foreground/30">·</span>
							<TooltipProvider>
								<Tooltip>
									<TooltipTrigger asChild>
										<div className="flex items-center gap-1.5 cursor-default">
											{member.avatarUrl ? (
												<Image
													src={member.avatarUrl}
													alt={member.name}
													width={18}
													height={18}
													className="h-4.5 w-4.5 rounded-full object-cover shrink-0"
												/>
											) : (
												<div className="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5 shrink-0">
													<span className="text-[9px] font-semibold text-primary">
														{getInitials(member.name)}
													</span>
												</div>
											)}
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
