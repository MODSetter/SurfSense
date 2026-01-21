"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { User, Users } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom, setThreadVisibilityAtom } from "@/atoms/chat/current-thread.atom";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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
	icon: typeof User;
}[] = [
	{
		value: "PRIVATE",
		label: "Private",
		description: "Only you can access this chat",
		icon: User,
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

	// Use Jotai atom for visibility (single source of truth)
	const currentThreadState = useAtomValue(currentThreadAtom);
	const setThreadVisibility = useSetAtom(setThreadVisibilityAtom);

	// Use Jotai visibility if available (synced from chat page), otherwise fall back to thread prop
	const currentVisibility = currentThreadState.visibility ?? thread?.visibility ?? "PRIVATE";
	const isOwnThread = thread?.created_by_id !== null; // If we have the thread, we can modify it

	const handleVisibilityChange = useCallback(
		async (newVisibility: ChatVisibility) => {
			if (!thread || newVisibility === currentVisibility) {
				setOpen(false);
				return;
			}

			// Update Jotai atom immediately for instant UI feedback
			setThreadVisibility(newVisibility);

			try {
				await updateThreadVisibility(thread.id, newVisibility);

				// Refetch threads list to update sidebar
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
				// Revert Jotai state on error
				setThreadVisibility(thread.visibility ?? "PRIVATE");
				toast.error("Failed to update sharing settings");
			}
		},
		[thread, currentVisibility, onVisibilityChange, queryClient, setThreadVisibility]
	);

	// Don't show if no thread (new chat that hasn't been created yet)
	if (!thread) {
		return null;
	}

	const CurrentIcon = currentVisibility === "PRIVATE" ? User : Users;

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>
						<Button
							variant="outline"
							size="icon"
							className={cn(
								"h-8 w-8 md:w-auto md:px-3 md:gap-2 relative bg-muted hover:bg-muted/80 border-0",
								className
							)}
						>
							<CurrentIcon className="h-4 w-4" />
							<span className="hidden md:inline text-sm">
								{currentVisibility === "PRIVATE" ? "Private" : "Shared"}
							</span>
						</Button>
					</PopoverTrigger>
				</TooltipTrigger>
				<TooltipContent>Share settings</TooltipContent>
			</Tooltip>

			<PopoverContent
				className="w-[280px] md:w-[320px] p-0 rounded-lg shadow-lg border-border/60"
				align="end"
				sideOffset={8}
				onCloseAutoFocus={(e) => e.preventDefault()}
			>
				<div className="p-1.5 space-y-1">
					{visibilityOptions.map((option) => {
						const isSelected = currentVisibility === option.value;
						const Icon = option.icon;

						return (
							<button
								type="button"
								key={option.value}
								onClick={() => handleVisibilityChange(option.value)}
								className={cn(
									"w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-all",
									"hover:bg-accent/50 cursor-pointer",
									"focus:outline-none",
									isSelected && "bg-accent/80"
								)}
							>
								<div
									className={cn(
										"size-7 rounded-md shrink-0 grid place-items-center",
										isSelected ? "bg-primary/10" : "bg-muted"
									)}
								>
									<Icon
										className={cn(
											"size-4 block",
											isSelected ? "text-primary" : "text-muted-foreground"
										)}
									/>
								</div>
								<div className="flex-1 text-left min-w-0">
									<div className="flex items-center gap-1.5">
										<span className={cn("text-sm font-medium", isSelected && "text-primary")}>
											{option.label}
										</span>
									</div>
									<p className="text-xs text-muted-foreground mt-0.5 leading-snug">
										{option.description}
									</p>
								</div>
							</button>
						);
					})}
				</div>
			</PopoverContent>
		</Popover>
	);
}
