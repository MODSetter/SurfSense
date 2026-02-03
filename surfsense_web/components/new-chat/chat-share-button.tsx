"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { Globe, User, Users } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { currentThreadAtom, setThreadVisibilityAtom } from "@/atoms/chat/current-thread.atom";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import { createPublicChatSnapshotMutationAtom } from "@/atoms/public-chat-snapshots/public-chat-snapshots-mutation.atoms";
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

	// Snapshot creation mutation
	const { mutateAsync: createSnapshot, isPending: isCreatingSnapshot } = useAtomValue(
		createPublicChatSnapshotMutationAtom
	);

	// Permission check for public sharing
	const { data: access } = useAtomValue(myAccessAtom);
	const canCreatePublicLink = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("public_sharing:create") ?? false;
	}, [access]);

	// Use Jotai visibility if available (synced from chat page), otherwise fall back to thread prop
	const currentVisibility = currentThreadState.visibility ?? thread?.visibility ?? "PRIVATE";

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

	const handleCreatePublicLink = useCallback(async () => {
		if (!thread) return;

		try {
			await createSnapshot({ thread_id: thread.id });
			setOpen(false);
		} catch (error) {
			console.error("Failed to create public link:", error);
		}
	}, [thread, createSnapshot]);

	// Don't show if no thread (new chat that hasn't been created yet)
	if (!thread) {
		return null;
	}

	const CurrentIcon = currentVisibility === "PRIVATE" ? User : Users;
	const buttonLabel = currentVisibility === "PRIVATE" ? "Private" : "Shared";

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
							<span className="hidden md:inline text-sm">{buttonLabel}</span>
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
					{/* Visibility Options */}
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

					{canCreatePublicLink && (
						<>
							{/* Divider */}
							<div className="border-t border-border my-1" />

							{/* Public Link Option */}
							<button
								type="button"
								onClick={handleCreatePublicLink}
								disabled={isCreatingSnapshot}
								className={cn(
									"w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-all",
									"hover:bg-accent/50 cursor-pointer",
									"focus:outline-none",
									"disabled:opacity-50 disabled:cursor-not-allowed"
								)}
							>
								<div className="size-7 rounded-md shrink-0 grid place-items-center bg-muted">
									<Globe className="size-4 block text-muted-foreground" />
								</div>
								<div className="flex-1 text-left min-w-0">
									<div className="flex items-center gap-1.5">
										<span className="text-sm font-medium">
											{isCreatingSnapshot ? "Creating link..." : "Create public link"}
										</span>
									</div>
									<p className="text-xs text-muted-foreground mt-0.5 leading-snug">
										Creates a shareable snapshot of this chat
									</p>
								</div>
							</button>
						</>
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
}
