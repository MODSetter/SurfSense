"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Globe, Loader2, Lock, Share2, Users } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
	type ChatVisibility,
	type ThreadRecord,
	updateThreadVisibility,
} from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";

interface ChatShareButtonProps {
	thread: ThreadRecord | null;
	onVisibilityChange?: (visibility: ChatVisibility) => void;
	className?: string;
}

const visibilityOptions: {
	value: ChatVisibility;
	label: string;
	description: string;
	icon: typeof Lock;
}[] = [
	{
		value: "PRIVATE",
		label: "Private",
		description: "Only you can access this chat",
		icon: Lock,
	},
	{
		value: "SEARCH_SPACE",
		label: "Search Space",
		description: "All members of this search space can access",
		icon: Users,
	},
];

export function ChatShareButton({ thread, onVisibilityChange, className }: ChatShareButtonProps) {
	const queryClient = useQueryClient();
	const [open, setOpen] = useState(false);
	const [isUpdating, setIsUpdating] = useState(false);

	const currentVisibility = thread?.visibility ?? "PRIVATE";
	const isOwnThread = thread?.created_by_id !== null; // If we have the thread, we can modify it

	const handleVisibilityChange = useCallback(
		async (newVisibility: ChatVisibility) => {
			if (!thread || newVisibility === currentVisibility) {
				setOpen(false);
				return;
			}

			setIsUpdating(true);
			try {
				await updateThreadVisibility(thread.id, newVisibility);

				// Refetch all thread queries to update sidebar immediately
				await queryClient.refetchQueries({
					predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === "threads",
				});

				onVisibilityChange?.(newVisibility);
				toast.success(
					newVisibility === "SEARCH_SPACE" ? "Chat shared with search space" : "Chat is now private"
				);
				setOpen(false);
			} catch (error) {
				console.error("Failed to update visibility:", error);
				toast.error("Failed to update sharing settings");
			} finally {
				setIsUpdating(false);
			}
		},
		[thread, currentVisibility, onVisibilityChange, queryClient]
	);

	// Don't show if no thread (new chat that hasn't been created yet)
	if (!thread) {
		return null;
	}

	const CurrentIcon = currentVisibility === "PRIVATE" ? Lock : Users;

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					variant="ghost"
					size="sm"
					className={cn(
						"h-7 md:h-9 gap-1.5 md:gap-2 px-2 md:px-3 rounded-lg md:rounded-xl",
						"border border-border/80 bg-background/50 backdrop-blur-sm",
						"hover:bg-muted/80 hover:border-border/30 transition-all duration-200",
						"text-xs md:text-sm font-medium text-foreground",
						"focus-visible:ring-0 focus-visible:ring-offset-0",
						className
					)}
				>
					<CurrentIcon className="size-3.5 md:size-4 text-muted-foreground" />
					<span className="hidden md:inline">
						{currentVisibility === "PRIVATE" ? "Private" : "Shared"}
					</span>
					<Share2 className="size-3 md:size-3.5 text-muted-foreground" />
				</Button>
			</PopoverTrigger>

			<PopoverContent
				className="w-[280px] md:w-[320px] p-0 rounded-lg md:rounded-xl shadow-lg border-border/60"
				align="end"
				sideOffset={8}
			>
				<div className="p-3 md:p-4 border-b border-border/30">
					<div className="flex items-center gap-2">
						<Share2 className="size-4 md:size-5 text-primary" />
						<div>
							<h4 className="text-sm font-semibold">Share Chat</h4>
							<p className="text-xs text-muted-foreground">
								Control who can access this conversation
							</p>
						</div>
					</div>
				</div>

				<div className="p-1.5 space-y-1">
					{/* Updating overlay */}
					{isUpdating && (
						<div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm rounded-xl">
							<div className="flex items-center gap-2 text-sm text-muted-foreground">
								<Loader2 className="size-4 animate-spin" />
								<span>Updating...</span>
							</div>
						</div>
					)}

					{visibilityOptions.map((option) => {
						const isSelected = currentVisibility === option.value;
						const Icon = option.icon;

						return (
							<button
								type="button"
								key={option.value}
								onClick={() => handleVisibilityChange(option.value)}
								disabled={isUpdating}
								className={cn(
									"w-full flex items-start gap-2.5 px-2.5 py-2 rounded-md transition-all",
									"hover:bg-accent/50 cursor-pointer",
									"focus:outline-none focus:ring-2 focus:ring-primary/20",
									isSelected && "bg-accent/80 ring-1 ring-primary/20"
								)}
							>
								<div
									className={cn(
										"mt-0.5 p-1.5 rounded-md shrink-0",
										isSelected ? "bg-primary/10" : "bg-muted"
									)}
								>
									<Icon
										className={cn(
											"size-3.5",
											isSelected ? "text-primary" : "text-muted-foreground"
										)}
									/>
								</div>
								<div className="flex-1 text-left min-w-0">
									<div className="flex items-center gap-1.5">
										<span className={cn("text-sm font-medium", isSelected && "text-primary")}>
											{option.label}
										</span>
										{isSelected && (
											<span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
												Current
											</span>
										)}
									</div>
									<p className="text-xs text-muted-foreground mt-0.5 leading-snug">
										{option.description}
									</p>
								</div>
							</button>
						);
					})}
				</div>

				{/* Info footer */}
				<div className="p-3 bg-muted/30 border-t border-border/30 rounded-b-xl">
					<div className="flex items-start gap-2">
						<Globe className="size-3.5 text-muted-foreground mt-0.5 shrink-0" />
						<p className="text-[11px] text-muted-foreground leading-relaxed">
							{currentVisibility === "PRIVATE"
								? "This chat is private. Only you can view and interact with it."
								: "This chat is shared. All search space members can view, continue the conversation, and delete it."}
						</p>
					</div>
				</div>
			</PopoverContent>
		</Popover>
	);
}
